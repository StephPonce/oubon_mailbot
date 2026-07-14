"""
TikTok Token Storage in Database

Stores OAuth tokens in PostgreSQL to survive deployments.
SECURITY: Tokens are never exposed to API responses.

NOTE(saas-launch): This table is INTENTIONALLY platform-wide (no user_id).
TikTok Ads API, TikTok Shop Open Platform, and TikTok Commerce Partner all
require each advertiser/seller to have their own approved TikTok developer
account — SaaS tenants cannot simply OAuth into TikTok like they can with
Gmail. Oubon's platform-wide TikTok credentials are used to pull trending-
product / hashtag signals from TikTok into the discovery pipeline for all
tenants. Ad automation and TikTok Shop deployment remain Oubon-only
features. Do not tenantize this without first re-evaluating whether other
tenants can actually get TikTok API access. See docs/CLEANUP_PASS4.md.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone
import os
import logging

logger = logging.getLogger(__name__)

# T161: use the SHARED metadata (was its own declarative_base(), so tiktok_tokens
# was missing from the startup create_all() and wouldn't exist on a fresh DB).
from ospra_os.database.base import Base

# T8: encrypt tokens at rest with the shared Fernet infra. decrypt_field is
# legacy-tolerant, so pre-encryption plaintext rows read fine and get
# re-encrypted on the next save_token().
from ospra_os.security.credential_encryption import encrypt_field, decrypt_field


class TikTokToken(Base):
    """Store TikTok OAuth tokens in database"""
    __tablename__ = "tiktok_tokens"

    id = Column(Integer, primary_key=True)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    obtained_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_in = Column(Integer, nullable=False)  # seconds

    @property
    def expires_at(self):
        """Calculate expiration time (naive UTC, matching the column)."""
        return self.obtained_at + timedelta(seconds=self.expires_in)

    @property
    def is_expired(self):
        """Check if token is expired.

        obtained_at is a naive DateTime column, so expires_at is naive.
        Comparing it against the AWARE datetime.now(timezone.utc) raised
        TypeError on EVERY real token load — the same bug aliexpress_tokens
        already documents. Compare naive-to-naive.
        """
        return datetime.utcnow() >= self.expires_at

    @property
    def needs_refresh(self):
        """Check if token needs refresh (7 days before expiry)."""
        refresh_threshold = self.expires_at - timedelta(days=7)
        return datetime.utcnow() >= refresh_threshold


# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ospra_os.db")
# Render uses postgres:// but SQLAlchemy needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database tables"""
    try:
        # T161: scope to this table — Base is now the shared 59-table metadata.
        Base.metadata.create_all(bind=engine, tables=[TikTokToken.__table__])
        logger.info("TikTok token storage initialized")
    except Exception as e:
        logger.error(f"Failed to initialize TikTok token storage: {e}")


def save_token(access_token: str, refresh_token: str, expires_in: int):
    """
    Save or update token in database

    SECURITY: This is the ONLY way tokens should be stored.
    Never return tokens to API responses.

    Args:
        access_token: OAuth access token
        refresh_token: OAuth refresh token
        expires_in: Token lifetime in seconds
    """
    db = SessionLocal()
    try:
        # Check if token already exists (only keep one)
        existing = db.query(TikTokToken).first()

        # T8: encrypt before persisting (refresh_token may be None).
        enc_access = encrypt_field(access_token)
        enc_refresh = encrypt_field(refresh_token) if refresh_token else refresh_token

        if existing:
            # Update existing token (naive UTC, matching the column + expiry math)
            existing.access_token = enc_access
            existing.refresh_token = enc_refresh
            existing.obtained_at = datetime.utcnow()
            existing.expires_in = expires_in
        else:
            # Create new token
            token = TikTokToken(
                access_token=enc_access,
                refresh_token=enc_refresh,
                expires_in=expires_in
            )
            db.add(token)

        db.commit()
        logger.info("Saved TikTok token to database")
        return True
    except Exception as e:
        logger.error(f"Failed to save TikTok token: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def load_token() -> dict:
    """
    Load token from database

    SECURITY: Only use this server-side. Never expose to API responses.

    Returns:
        dict with access_token, refresh_token, obtained_at, expires_in
        None if token not found or expired
    """
    db = SessionLocal()
    try:
        token = db.query(TikTokToken).first()

        if not token:
            return None

        # Return token data (T8: decrypt on read; legacy plaintext passes through)
        return {
            "access_token": decrypt_field(token.access_token),
            "refresh_token": decrypt_field(token.refresh_token) if token.refresh_token else token.refresh_token,
            "obtained_at": token.obtained_at.isoformat(),
            "expires_in": token.expires_in,
            "expires_at": token.expires_at.isoformat(),
            "is_expired": token.is_expired,
            "needs_refresh": token.needs_refresh
        }
    finally:
        db.close()


def get_access_token() -> str:
    """
    Get current access token

    SECURITY: Only use this server-side for API calls.
    Never expose to client responses.

    Returns:
        Access token string or None if not available
    """
    token_data = load_token()
    if token_data and not token_data["is_expired"]:
        return token_data["access_token"]
    return None


def get_token_status() -> dict:
    """
    Get status of TikTok token (safe for API responses)

    Returns status WITHOUT exposing the actual token.
    """
    token_data = load_token()

    if not token_data:
        return {
            "status": "not_authorized",
            "message": "No TikTok token found. Please authorize at /auth/tiktok/authorize"
        }

    if token_data["is_expired"]:
        return {
            "status": "expired",
            "message": "Token expired. Please re-authorize.",
            "obtained_at": token_data["obtained_at"],
            "expires_at": token_data["expires_at"]
        }

    expires_at = datetime.fromisoformat(token_data["expires_at"])
    now = datetime.utcnow()  # naive, matching the naive expires_at isoformat

    expires_in_seconds = int((expires_at - now).total_seconds())
    expires_in_days = expires_in_seconds / 86400

    return {
        "status": "valid",
        "obtained_at": token_data["obtained_at"],
        "expires_at": token_data["expires_at"],
        "expires_in_seconds": expires_in_seconds,
        "expires_in_days": round(expires_in_days, 1),
        "needs_refresh": token_data["needs_refresh"],
        # SECURITY: Only show token exists, never the actual value
        "token_configured": True
    }


# Initialize database on import
try:
    init_db()
except Exception:
    pass  # May fail if database not yet configured
