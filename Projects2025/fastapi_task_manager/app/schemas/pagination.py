from pydantic import BaseModel, validator
from typing import Generic, TypeVar, List, Optional
from datetime import datetime

T = TypeVar('T')

class PaginationParams(BaseModel):
    """Standard pagination parameters"""
    page: int = 1
    page_size: int = 20

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response"""
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool

    @classmethod
    def create(
            cls,
            items: List[T],
            total: int,
            page: int,
            page_size: int
    ) -> "PaginatedResponse[T]":
        total_pages = (total + page_size - 1) // page_size
        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1
        )

class TaskFilters(BaseModel):
    """Task filtering parameters. Dates must be in ISO format (e.g., 2025-08-17T12:00:00Z or 2025-08-17T12:00:00+00:00)."""
    status: Optional[str] = None
    owner_id: Optional[int] = None
    title_contains: Optional[str] = None
    created_after: Optional[str] = None  # ISO date string
    created_before: Optional[str] = None  # ISO date string

    @validator("created_after", "created_before")
    def validate_date(cls, value):
        if value:
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                raise ValueError("Invalid ISO date format")
        return value

class CommentFilters(BaseModel):
    """Comment filtering parameters"""
    task_id: Optional[int] = None
    user_id: Optional[int] = None
    content_contains: Optional[str] = None