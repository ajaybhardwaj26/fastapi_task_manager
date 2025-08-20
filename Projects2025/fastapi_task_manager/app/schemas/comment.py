from pydantic import BaseModel
from datetime import datetime

class CommentCreate(BaseModel):
    task_id: int
    content: str
    # Note: user_id will be set from authentication context, not from request body

class CommentUpdate(BaseModel):
    """Schema for updating comments"""
    content: str

class CommentRead(BaseModel):
    id: int
    content: str
    task_id: int
    user_id: int
    created_at: datetime

    class Config:
        from_attributes = True