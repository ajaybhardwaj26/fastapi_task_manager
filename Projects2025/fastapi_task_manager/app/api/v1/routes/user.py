from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from datetime import timedelta
import logging
from pythonjsonlogger import jsonlogger

from app.api.v1.crud import user as crud_user
from app.api.deps import get_db_session, get_current_user
from app.models.user import User
from app.schemas.user import UserRead, UserCreate, UserUpdate

# Configure JSON logger
logger = logging.getLogger("task_manager.user")
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ"
)
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

# Only define router here, NO prefix
router = APIRouter(tags=["users"])

# ---------------------------
# Seed test user (dev only)
# ---------------------------
@router.post("/seed", status_code=status.HTTP_201_CREATED)
async def seed_test_user(db: AsyncSession = Depends(get_db_session)):
    test_user = await crud_user.get_user_by_email(db, "test@example.com")
    if not test_user:
        await crud_user.create_user(db, UserCreate(
            username="testuser", email="test@example.com", password="password123"
        ))
        logger.info("Test user created", extra={"email": "test@example.com"})
    return {"message": "Test user created"}

# ---------------------------
# Get current logged-in user
# ---------------------------
@router.get("/me", response_model=UserRead)
async def read_current_user(current_user: User = Depends(get_current_user)):
    logger.info("User accessed /me", extra={"user_id": current_user.id})
    return current_user

# ---------------------------
# List all users (admin only)
# ---------------------------
@router.get("/", response_model=List[UserRead])
async def read_users(
        db: AsyncSession = Depends(get_db_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return await crud_user.get_all_users(db)

# ---------------------------
# Get user by ID (admin only)
# ---------------------------
@router.get("/{user_id}", response_model=UserRead)
async def read_user(
        user_id: int,
        db: AsyncSession = Depends(get_db_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    db_user = await crud_user.get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

# ---------------------------
# Update user (admin only)
# ---------------------------
@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
        user_id: int,
        updates: UserUpdate,
        db: AsyncSession = Depends(get_db_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    db_user = await crud_user.get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = updates.dict(exclude_unset=True)  # only fields provided by the client
    updated_user = await crud_user.update_user(db, db_user, update_data)

    # ----------------- Logging/Auditing -----------------
    print(f"[AUDIT] User {current_user.id} updated user {user_id}: {update_data}")

    return updated_user

# ---------------------------
# Delete user (admin only)
# ---------------------------
@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
        user_id: int,
        db: AsyncSession = Depends(get_db_session),
        current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    db_user = await crud_user.get_user_by_id(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    await crud_user.delete_user(db, db_user)
    return