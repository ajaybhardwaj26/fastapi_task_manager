from fastapi import APIRouter, Depends, HTTPException, status, Query, Header
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.v1.crud import task as crud_task
from app.api.deps import get_db_session, get_current_user
from app.models.user import User
from app.schemas.task import TaskRead, TaskCreate, TaskUpdate
from app.schemas.pagination import PaginatedResponse, PaginationParams, TaskFilters
from app.core.cache import cache, make_task_cache_key, make_task_detail_cache_key, make_user_tasks_cache_key
from app.worker import fetch_task_metadata
import logging
from pythonjsonlogger import jsonlogger

# Custom key function for authenticated users
def get_user_id_key(request):
    user = request.state.user if hasattr(request.state, "user") else None
    return f"user:{user.id}" if user else get_remote_address(request)

limiter = Limiter(key_func=get_user_id_key)

router = APIRouter(tags=["tasks"])

@router.post("/", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
@limiter.limit("50/minute")
async def create_task(
        request,  # Required for slowapi
        task_in: TaskCreate,
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    # Check idempotency key
    if idempotency_key:
        cached_response = await cache.get_idempotency(idempotency_key)
        if cached_response:
            logger.info("Idempotent request detected, returning cached response",
                        extra={"user_id": current_user.id, "idempotency_key": idempotency_key})
            return TaskRead(**cached_response)
    # Create task
    task = await crud_task.create_task(db, task_in, owner_id=current_user.id)

    # Store response for idempotency
    if idempotency_key:
        await cache.set_idempotency(idempotency_key, TaskRead.from_orm(task).dict())
        logger.info("Stored idempotency response",
                    extra={"user_id": current_user.id, "idempotency_key": idempotency_key, "task_id": task.id})

    # Invalidate cache and trigger background job
    await cache.delete_pattern(make_user_tasks_cache_key(current_user.id))
    fetch_task_metadata.delay(task.id)

    logger.info("Task created", extra={"user_id": current_user.id, "task_id": task.id})

    return task

@router.get("/", response_model=PaginatedResponse[TaskRead])
@limiter.limit("100/minute")
async def get_tasks(
        request,  # Add request parameter
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page"),
        status: Optional[str] = Query(None, description="Filter by status"),
        owner_id: Optional[int] = Query(None, description="Filter by owner ID (admin only)"),
        title_contains: Optional[str] = Query(None, description="Search in title"),
        created_after: Optional[str] = Query(None, description="Filter created after date (ISO format)"),
        created_before: Optional[str] = Query(None, description="Filter created before date (ISO format)"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    pagination = PaginationParams(page=page, page_size=page_size)
    filters = TaskFilters(
        status=status,
        owner_id=owner_id if current_user.role == "admin" else None,
        title_contains=title_contains,
        created_after=created_after,
        created_before=created_before
    )
    cache_key = make_task_cache_key(
        current_user.id,
        {
            "page": page,
            "page_size": page_size,
            "status": status,
            "owner_id": filters.owner_id,
            "title_contains": title_contains,
            "created_after": created_after,
            "created_before": created_before,
            "is_admin": current_user.role == "admin"
        }
    )
    cached_result = await cache.get(cache_key)
    if cached_result:
        return PaginatedResponse(**cached_result)
    tasks, total = await crud_task.get_tasks_with_pagination(
        db=db,
        pagination=pagination,
        filters=filters,
        current_user_id=current_user.id,
        is_admin=current_user.role == "admin"
    )
    response = PaginatedResponse.create(
        items=[TaskRead.from_orm(task) for task in tasks],
        total=total,
        page=page,
        page_size=page_size
    )
    await cache.set(cache_key, response.dict(), expire_seconds=300)
    logger.info("Fetched tasks from DB and cached",
                extra={"user_id": current_user.id, "cache_key": cache_key, "total_tasks": total})
    return response

@router.get("/{task_id}", response_model=TaskRead)
@limiter.limit("100/minute")
async def get_task(
        request,  # Add request parameter
        task_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    cache_key = make_task_detail_cache_key(task_id)
    cached_task = await cache.get(cache_key)
    if cached_task:
        if current_user.role != "admin" and cached_task["owner_id"] != current_user.id:
            raise HTTPException(status_code=403, detail="Forbidden")
        logger.info("Retrieved task from cache",
                    extra={"user_id": current_user.id, "task_id": task_id, "cache_key": cache_key})
        return TaskRead(**cached_task)
    task = await crud_task.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if current_user.role != "admin" and task.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    task_data = TaskRead.from_orm(task)
    await cache.set(cache_key, task_data.dict(), expire_seconds=600)
    logger.info("Fetched task from DB and cached",
                extra={"user_id": current_user.id, "task_id": task_id, "cache_key": cache_key})
    return task_data

@router.patch("/{task_id}", response_model=TaskRead)
@limiter.limit("50/minute")
async def update_task(
        request,  # Already present
        task_id: int,
        task_update: TaskUpdate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    task = await crud_task.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if current_user.role != "admin" and task.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    update_data = task_update.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    updated_task = await crud_task.update_task(db, task_id, update_data)
    if not updated_task:
        raise HTTPException(status_code=404, detail="Task not found")
    await cache.delete(make_task_detail_cache_key(task_id))
    await cache.delete_pattern(make_user_tasks_cache_key(current_user.id))
    if current_user.role == "admin":
        await cache.delete_pattern("tasks:user:*")
    logger.info("Task updated",
                extra={"user_id": current_user.id, "task_id": task_id, "updates": update_data})
    return TaskRead.from_orm(updated_task)
@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("50/minute")
async def delete_task(
        request,  # Already present
        task_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    task = await crud_task.get_task_by_id(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if current_user.role != "admin" and task.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await crud_task.delete_task(db, task)
    await cache.delete(make_task_detail_cache_key(task_id))
    await cache.delete_pattern(make_user_tasks_cache_key(current_user.id))
    logger.info("Task deleted", extra={"user_id": current_user.id, "task_id": task_id})
    return None

@router.get("/stats/summary", response_model=dict)
@limiter.limit("20/minute")
async def get_task_stats(
        request,  # Already present
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    cache_key = f"task_stats:user:{current_user.id}"
    cached_stats = await cache.get(cache_key)
    if cached_stats:
        logger.info("Retrieved task stats from cache",
                    extra={"user_id": current_user.id, "cache_key": cache_key})
        return cached_stats
    stats = await crud_task.get_task_statistics(db, current_user.id)
    await cache.set(cache_key, stats, expire_seconds=120)
    logger.info("Fetched task stats from DB and cached",
                extra={"user_id": current_user.id, "cache_key": cache_key})
    return stats