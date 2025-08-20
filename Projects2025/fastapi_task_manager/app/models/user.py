from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="user", nullable=False)
    created_at = Column(DateTime(timezone=False), nullable=False, server_default=func.now(), default=datetime.utcnow)

    # relationships
    comments = relationship("Comment", back_populates="author")
    tasks = relationship("Task", back_populates="owner")
    audit_logs = relationship("AuditLog", back_populates="user")

    def is_admin(self) -> bool:
        return self.role.lower() == "admin"