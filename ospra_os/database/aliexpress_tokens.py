"""
AliExpress Token Storage in Database

Stores OAuth tokens in PostgreSQL to survive deployments.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta, timezone
import os

# T161: use the SHARED metadata. This module previously created its own
# declarative_base(), so its table registered on a separate metadata and was
# NOT created by the app's normal Base.metadata.create_all() on startup — on a
# fresh DB, saving an AliExpress token would fail with "no such table". Sharing
# the one Base puts aliexpress_tokens into the metadata create_all() actually uses.
from ospra_os.database.base import Base


class AliExpressToken(Base):
    """Store AliExpress OAuth tokens in database"""
    __tablename__ = "aliexpress_tokens"

    id = Column(Integer, primary_key=True)
    api_type = Column(String(50), unique=True)  # "dropship" or "affiliate"
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    obtained_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_in = Column(Integer, nullable=False)  # seconds

    @property
    def expires_at(self):
        """Calculate expiration time (naive UTC, matching the column)."""
        return self.obtained_at + timedelta(seconds=self.expires_in)

    # Adversarial-review fix (re-audit follow-up): `obtained_at` is a naive
    # DateTime column, so `expires_at` is naive — comparing it against the
    # AWARE datetime.now(timezone.utc) raised
    # `TypeError: can't compare offset-naive and offset-aware datetimes`
    # on EVERY load of a real token row. That crash silently disabled both
    # the DS self-heal and the proactive refresh job (load_token caught it
    # and returned None). Compare naive-to-naive.

    @property
    def is_expired(self):
        """Check if token is expired"""
        return datetime.utcnow() >= self.expires_at

    @property
    def needs_refresh(self):
        """Check if token needs refresh (7 days before expiry)"""
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
    # T161: scope to THIS table. Base is now the shared metadata (59+ tables), so
    # an unscoped create_all() here would try to build the entire schema from this
    # token module. Only ensure our own table exists.
    Base.metadata.create_all(bind=engine, tables=[AliExpressToken.__table__])
    print("[SUCCESS] AliExpress token storage initialized")


def save_token(api_type: str, access_token: str, refresh_token: str, expires_in: int):
    """
    Save or update token in database

    Args:
        api_type: "dropship" or "affiliate"
        access_token: OAuth access token
        refresh_token: OAuth refresh token
        expires_in: Token lifetime in seconds
    """
    db = SessionLocal()
    try:
        # Check if token already exists
        existing = db.query(AliExpressToken).filter_by(api_type=api_type).first()

        if existing:
            # Update existing token
            existing.access_token = access_token
            existing.refresh_token = refresh_token
            existing.obtained_at = datetime.now(timezone.utc)
            existing.expires_in = expires_in
        else:
            # Create new token
            token = AliExpressToken(
                api_type=api_type,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in
            )
            db.add(token)

        db.commit()
        print(f"[SUCCESS] Saved {api_type} token to database")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save token: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def load_token(api_type: str) -> dict:
    """
    Load token from database

    Args:
        api_type: "dropship" or "affiliate"

    Returns:
        dict with access_token, refresh_token, obtained_at, expires_in
        None if token not found or expired
    """
    db = SessionLocal()
    try:
        token = db.query(AliExpressToken).filter_by(api_type=api_type).first()

        if not token:
            return None

        # Return token data
        return {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "obtained_at": token.obtained_at.isoformat(),
            "expires_in": token.expires_in,
            "expires_at": token.expires_at.isoformat(),
            "is_expired": token.is_expired,
            "needs_refresh": token.needs_refresh
        }
    finally:
        db.close()


def get_token_status() -> dict:
    """
    Get status of all tokens

    Returns:
        dict with status of dropship and affiliate tokens
    """
    dropship = load_token("dropship")
    affiliate = load_token("affiliate")

    def format_status(token_data):
        if not token_data:
            return {"status": "not_authorized", "message": "No tokens found"}

        if token_data["is_expired"]:
            return {
                "status": "expired",
                "message": "Token expired",
                "obtained_at": token_data["obtained_at"],
                "expires_at": token_data["expires_at"]
            }

        expires_at = datetime.fromisoformat(token_data["expires_at"])
        obtained_at = datetime.fromisoformat(token_data["obtained_at"])
        now = datetime.now(timezone.utc)

        expires_in_seconds = int((expires_at - now).total_seconds())
        expires_in_days = expires_in_seconds / 86400

        return {
            "status": "valid",
            "obtained_at": token_data["obtained_at"],
            "expires_at": token_data["expires_at"],
            "expires_in_seconds": expires_in_seconds,
            "expires_in_days": round(expires_in_days, 1),
            "needs_refresh": token_data["needs_refresh"],
            "has_refresh_token": True,
            "access_token_preview": token_data["access_token"][:20] + "..."
        }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dropship": format_status(dropship),
        "affiliate": format_status(affiliate)
    }


# Initialize database on import
init_db()
