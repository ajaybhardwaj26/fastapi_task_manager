from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash, verify_password

# ----- Create a new user -----
async def create_user(db: AsyncSession, user_in: UserCreate, role: str = "user") -> User:
    hashed_password = get_password_hash(user_in.password)
    user = User(
        username=user_in.username,
        email=user_in.email,
        hashed_password=hashed_password,
        role=role
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


# ----- Authenticate user -----
async def authenticate_user(db: AsyncSession, email: str, password: str) -> Optional[User]:
    user = await get_user_by_email(db, email)
    if user and verify_password(password, user.hashed_password):
        return user
    return None

# ----- Get user by id -----
async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """
    Retrieve a user by their unique ID.
    Returns None if user does not exist.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalars().first()

# ----- Get user by email -----
async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()

# ----- Get user by username -----
async def get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()

# ----- Get all users with optional pagination -----
async def get_all_users(db: AsyncSession, skip: int = 0, limit: int = 20) -> List[User]:
    query = select(User).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

# ----- Update a user -----
async def update_user(db: AsyncSession, user: User, updates: dict) -> User:
    for key, value in updates.items():
        if key == "password":
            setattr(user, "hashed_password", get_password_hash(value))
        else:
            setattr(user, key, value)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

# ----- Delete a user -----
async def delete_user(db: AsyncSession, user: User):
    await db.delete(user)
    await db.commit()