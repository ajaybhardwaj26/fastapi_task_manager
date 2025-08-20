from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.schemas.user import UserCreate, UserRead, Token
from app.api.deps import get_db_session
from app.api.v1.crud import user as crud_user
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.config import settings


limiter = Limiter(key_func=get_remote_address)  # IP-based for unauthenticated

router = APIRouter(tags=["auth"])

# ---------------------------
# auth.py should only handle authentication & token logic:
# ----Login endpoint (/auth/login)
# ----Token generation / validation
# ----Maybe refresh tokens
# It should NOT have CRUD logic for users or other tables
# ---------------------------

# ---------------------------
# Register endpoint
# ---------------------------

@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")  # 10 requests per minute per IP
async def register(
        request,  # Required for slowapi
        user_in: UserCreate,
        db: AsyncSession = Depends(get_db_session)
):
    existing_user = await crud_user.get_user_by_email(db, user_in.email)
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = await crud_user.create_user(db, user_in)
    return user


# ---------------------------
# Login endpoint
# ---------------------------
@router.post("/login", response_model=Token)
@limiter.limit("10/minute")  # Strict limit to prevent brute-force
async def login(
        request,  # Required for slowapi
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_db_session)
):
    user = await crud_user.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = {
        "sub": str(user.id),
        "role": user.role,
        "email": user.email,
        "scope": "access"
    }

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data=token_data,
        expires_delta=access_token_expires
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }