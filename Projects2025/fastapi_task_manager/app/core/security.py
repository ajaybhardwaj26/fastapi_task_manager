from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.schemas.user import TokenData

# Password hashing context (bcrypt is industry standard)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------
# Password Hashing Utilities
# ---------------------------
def get_password_hash(password: str) -> str:
    """Hash a plain-text password."""
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against the stored hash."""
    return pwd_context.verify(plain_password, hashed_password)

# ---------------------------
# JWT Token Utilities
# ---------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Generate a JWT token.
    - data: dict containing claims (data: expects {'user_id': id, 'role': 'user/admin'})
    - expires_delta: optional timedelta for expiry
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "sub": str(data["user_id"])})  # sub is user_id
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> Optional[TokenData]:
    """
     Decode a JWT token and return TokenData including userid and role.
     If invalid or expired, return None.
     """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        if user_id is None or role is None:
            return None
        return TokenData(user_id=int(user_id), role=role)
    except JWTError:
        return None


