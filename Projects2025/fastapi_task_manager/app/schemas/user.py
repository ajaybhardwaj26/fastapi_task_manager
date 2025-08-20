from pydantic import BaseModel, EmailStr, ConfigDict, constr
from datetime import datetime
from typing import Optional

# Shared properties between multiple user schemas
class UserBase(BaseModel):
    username: str
    email: EmailStr
    role: str = "user"  # default role

# Schema for creating a new user (request body)
class UserCreate(UserBase):
    password: str

# Schema for reading user data in responses (no password)
class UserRead(UserBase):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)  # Pydantic v2 style

# Schema for JWT token response
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# Schema for decoded JWT token data
class TokenData(BaseModel):
    user_id: Optional[int] = None  # JWT sub
    role: Optional[str] = "user"

# ---------------------------
# Schema for updating user (optional fields + validation)
# ---------------------------
class UserUpdate(BaseModel):
    username: Optional[constr(min_length=3, max_length=50)]
    email: Optional[EmailStr]
    password: Optional[constr(min_length=6)]
    role: Optional[constr(min_length=3, max_length=20)]