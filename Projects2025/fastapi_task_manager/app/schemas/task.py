from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
### After the Celery job fetches external API data and updates the DB, if you fetch the task again via /tasks/{id}, you’ll see the updated metadata.
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "pending"


class TaskUpdate(BaseModel):
    """Schema for updating tasks - all fields optional"""
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class TaskRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    owner_id: int
    created_at: datetime
    task_metadata: Optional[Dict[str, Any]] = None   # to support Celery's external API integration

    class Config:
        from_attributes = True