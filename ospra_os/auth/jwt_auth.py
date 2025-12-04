"""
JWT Authentication System for Ospra Intelligence
================================================

Provides:
- Password hashing with bcrypt
- JWT token generation/validation
- FastAPI dependencies for protected routes
- Session-based user identification (replaces user_id query params)
"""

from datetime import datetime, timedelta
from typing import Optional
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr

from ospra_os.database.multi_store_models import User, SessionLocal, SubscriptionTier


# ============================================================================
# CONFIGURATION
# ============================================================================

# Secret key for JWT signing (use env var in production!)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "ospra-dev-secret-change-in-production-abc123xyz789")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30


# ============================================================================
# PASSWORD HASHING
# ============================================================================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TokenData(BaseModel):
    """Data encoded in JWT token"""
    user_id: int
    email: str
    tier: str
    exp: datetime


class TokenResponse(BaseModel):
    """Response when issuing tokens"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds
    user: dict


class UserCreate(BaseModel):
    """Request body for user registration"""
    email: EmailStr
    password: str
    name: str


class UserLogin(BaseModel):
    """Request body for login"""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User data returned to client (no sensitive info)"""
    id: int
    email: str
    name: str
    subscription_tier: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# TOKEN GENERATION
# ============================================================================

def create_access_token(user: User) -> str:
    """
    Create JWT access token for a user.
    
    Args:
        user: User model instance
        
    Returns:
        Encoded JWT string
    """
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": str(user.id),  # Subject (user ID as string)
        "email": user.email,
        "tier": user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    }
    
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user: User) -> str:
    """
    Create JWT refresh token for a user.
    
    Args:
        user: User model instance
        
    Returns:
        Encoded JWT string
    """
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    payload = {
        "sub": str(user.id),
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "refresh"
    }
    
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT token.
    
    Args:
        token: JWT string
        
    Returns:
        Decoded payload dict
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ============================================================================
# DATABASE HELPERS
# ============================================================================

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email address"""
    return db.query(User).filter(User.email == email).first()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID"""
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, user_data: UserCreate) -> User:
    """
    Create a new user.
    
    Args:
        db: Database session
        user_data: User registration data
        
    Returns:
        Created User instance
        
    Raises:
        HTTPException: If email already exists
    """
    # Check if email exists
    if get_user_by_email(db, user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user with hashed password
    user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=hash_password(user_data.password),
        subscription_tier=SubscriptionTier.NEST,  # Start at free tier
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Authenticate user with email and password.
    
    Args:
        db: Database session
        email: User email
        password: Plain text password
        
    Returns:
        User if authenticated, None otherwise
    """
    user = get_user_by_email(db, email)
    
    if not user:
        return None
    
    # Check if user has password_hash (for migrated users)
    if not hasattr(user, 'password_hash') or not user.password_hash:
        return None
        
    if not verify_password(password, user.password_hash):
        return None
        
    return user


# ============================================================================
# FASTAPI DEPENDENCIES
# ============================================================================

# HTTP Bearer scheme for token extraction
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    FastAPI dependency to get current authenticated user.
    
    Usage:
        @router.get("/protected")
        async def protected_route(user: User = Depends(get_current_user)):
            return {"user_id": user.id}
    
    Args:
        credentials: Bearer token from Authorization header
        db: Database session
        
    Returns:
        Authenticated User instance
        
    Raises:
        HTTPException: If not authenticated or token invalid
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Decode token
    payload = decode_token(credentials.credentials)
    
    # Validate token type
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user ID from token
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Fetch user from database
    user = get_user_by_id(db, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    FastAPI dependency for optional authentication.
    Returns None if not authenticated instead of raising exception.
    
    Usage:
        @router.get("/public-or-personalized")
        async def route(user: Optional[User] = Depends(get_current_user_optional)):
            if user:
                return {"message": f"Hello, {user.name}!"}
            return {"message": "Hello, guest!"}
    """
    if not credentials:
        return None
    
    try:
        payload = decode_token(credentials.credentials)
        
        if payload.get("type") != "access":
            return None
            
        user_id = payload.get("sub")
        if not user_id:
            return None
            
        return get_user_by_id(db, int(user_id))
        
    except HTTPException:
        return None


def require_tier(min_tier: str):
    """
    FastAPI dependency factory to require minimum subscription tier.
    
    Usage:
        @router.get("/pro-feature")
        async def pro_feature(user: User = Depends(require_tier("soar"))):
            return {"access": "granted"}
    
    Args:
        min_tier: Minimum required tier ("nest", "flight", "soar", "stratosphere")
        
    Returns:
        Dependency function
    """
    tier_order = ["nest", "flight", "soar", "stratosphere"]
    
    async def tier_checker(user: User = Depends(get_current_user)) -> User:
        user_tier = user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier)
        
        user_tier_index = tier_order.index(user_tier.lower()) if user_tier.lower() in tier_order else 0
        required_tier_index = tier_order.index(min_tier.lower()) if min_tier.lower() in tier_order else 0
        
        if user_tier_index < required_tier_index:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "tier_required",
                    "message": f"This feature requires {min_tier.capitalize()} tier or higher",
                    "current_tier": user_tier,
                    "required_tier": min_tier,
                    "upgrade_url": f"/subscription/upgrade?to={min_tier}"
                }
            )
        
        return user
    
    return tier_checker


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def user_to_dict(user: User) -> dict:
    """Convert User model to safe dictionary (no password)"""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "subscription_tier": user.subscription_tier.value if hasattr(user.subscription_tier, 'value') else str(user.subscription_tier),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login": user.last_login.isoformat() if user.last_login else None,
    }


def generate_tokens(user: User) -> TokenResponse:
    """Generate access and refresh tokens for a user"""
    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=user_to_dict(user)
    )
