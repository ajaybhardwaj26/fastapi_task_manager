from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func, JSON
from sqlalchemy.orm import relationship
from app.db.base import Base

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    status = Column(String, default="pending", nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now(), default=datetime.utcnow)

    # NEW FIELD: store external API metadata
    task_metadata = Column(JSON, nullable=True) # add a task_metadata JSON field so we can store the external API response when Celery updates the task.

    # relationships
    owner = relationship("User", back_populates="tasks")
    comments = relationship("Comment", back_populates="task")

    def is_completed(self) -> bool:
        """Check if task is completed"""
        return self.status.lower() == "completed"

    def is_pending(self) -> bool:
        """Check if task is pending"""
        return self.status.lower() == "pending"