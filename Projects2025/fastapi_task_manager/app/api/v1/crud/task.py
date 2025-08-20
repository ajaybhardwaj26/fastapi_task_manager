# app/api/v1/crud/task.py
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import OperationalError

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional, Tuple
from datetime import datetime
from app.models.task import Task
from app.schemas.task import TaskCreate
from app.schemas.pagination import TaskFilters, PaginationParams

from fastapi import HTTPException

@retry(
    stop=stop_after_attempt(3),  # Retry 3 times
    wait=wait_fixed(2),  # Wait 2s between retries
    retry=retry_if_exception_type(OperationalError)  # Retry on DB connection errors
)
# ----- Create a new task -----
async def create_task(db: AsyncSession, task_in: TaskCreate, owner_id: int) -> Task:
    """Create a new task."""
    task_data = task_in.dict()
    task_data["owner_id"] = owner_id
    new_task = Task(**task_data)
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    return new_task

# ----- Get tasks with filtering and pagination -----
async def get_tasks_with_pagination(
        db: AsyncSession,
        pagination: PaginationParams,
        filters: TaskFilters,
        current_user_id: int,
        is_admin: bool = False
) -> Tuple[List[Task], int]:
    """Get tasks with pagination and filtering. Raises HTTP 400 for invalid ISO date formats."""
    # Base query with relationships
    query = select(Task).options(
        selectinload(Task.owner),
        selectinload(Task.comments)
    )

    # Build filter conditions
    conditions = []

    # Permission-based filtering
    if not is_admin:
        conditions.append(Task.owner_id == current_user_id)
    elif filters.owner_id is not None:
        conditions.append(Task.owner_id == filters.owner_id)

    # Status filter
    if filters.status:
        conditions.append(Task.status.ilike(f"%{filters.status}%"))

    # Title search
    if filters.title_contains:
        conditions.append(Task.title.ilike(f"%{filters.title_contains}%"))

    # Date filters
    if filters.created_after:
        try:
            date_after = datetime.fromisoformat(filters.created_after.replace('Z', '+00:00'))
            conditions.append(Task.created_at >= date_after)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid created_after date format")

    if filters.created_before:
        try:
            date_before = datetime.fromisoformat(filters.created_before.replace('Z', '+00:00'))
            conditions.append(Task.created_at <= date_before)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid created_before date format")

    # Apply filters
    if conditions:
        query = query.where(and_(*conditions))

    # Get total count for pagination
    count_query = select(func.count(Task.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination and ordering
    query = (
        query
        .order_by(Task.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )

    result = await db.execute(query)
    tasks = result.scalars().all()

    return tasks, total

# ----- Get all tasks (admin only, with optional filters) -----
async def get_all_tasks(
        db: AsyncSession,
        owner_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
) -> List[Task]:
    """Get all tasks with optional filters (admin only)."""
    query = select(Task).options(
        selectinload(Task.owner),
        selectinload(Task.comments)
    )

    conditions = []
    if owner_id is not None:
        conditions.append(Task.owner_id == owner_id)
    if status is not None:
        conditions.append(Task.status.ilike(f"%{status}%"))

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

# ----- Get user tasks with filters -----
async def get_user_tasks(
        db: AsyncSession,
        owner_id: int,
        status: Optional[str] = None,
        title_contains: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
) -> List[Task]:
    """Get tasks for specific user with filters."""
    query = select(Task).options(
        selectinload(Task.owner),
        selectinload(Task.comments)
    ).where(Task.owner_id == owner_id)

    conditions = []
    if status is not None:
        conditions.append(Task.status.ilike(f"%{status}%"))
    if title_contains is not None:
        conditions.append(Task.title.ilike(f"%{title_contains}%"))

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Task.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

# ----- Get a single task by ID -----
async def get_task_by_id(db: AsyncSession, task_id: int) -> Optional[Task]:
    """Get single task with relationships loaded."""
    result = await db.execute(
        select(Task)
        .options(
            selectinload(Task.owner),
            selectinload(Task.comments)
        )
        .where(Task.id == task_id)
    )
    return result.scalars().first()

# ----- Update a task -----
async def update_task(db: AsyncSession, task_id: int, updates: dict) -> Optional[Task]:
    """Update a Task and return the updated Task object."""
    result = await db.execute(
        update(Task)
        .where(Task.id == task_id)
        .values(**updates)
        .returning(Task)
    )

    updated_task = result.fetchone()
    await db.commit()

    if updated_task is None:
        return None

    return updated_task[0]

# ----- Delete a task -----
async def delete_task(db: AsyncSession, task: Task):
    """Delete a task."""
    await db.delete(task)
    await db.commit()

# ----- Update task metadata (for Celery) -----
async def update_task_metadata(db: AsyncSession, task: Task, metadata: dict):
    """Update the metadata field of a task."""
    task.task_metadata = metadata
    db.add(task)
    await db.commit()
    await db.refresh(task)

# ----- Get task statistics -----
async def get_task_statistics(db: AsyncSession, user_id: int) -> dict:
    """Get task statistics for a user."""
    # Count tasks by status
    status_counts = await db.execute(
        select(Task.status, func.count(Task.id))
        .where(Task.owner_id == user_id)
        .group_by(Task.status)
    )

    stats = {"total": 0}
    for status, count in status_counts.fetchall():
        stats[status.lower()] = count
        stats["total"] += count

    return stats