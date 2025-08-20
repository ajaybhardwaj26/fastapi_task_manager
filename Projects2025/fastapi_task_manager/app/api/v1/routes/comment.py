from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import logging
from pythonjsonlogger import jsonlogger

from app.api.v1.crud import comment as crud_comment
from app.api.v1.crud import task as crud_task
from app.api.deps import get_db_session, get_current_user
from app.models.user import User
from app.schemas.comment import CommentCreate, CommentRead
from app.schemas.pagination import PaginatedResponse, PaginationParams, CommentFilters
from app.core.cache import cache

# Configure JSON logger
logger = logging.getLogger("task_manager.comment")
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ"
)
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

router = APIRouter(tags=["comments"])

# ----- Create a new comment -----
@router.post("/", response_model=CommentRead, status_code=status.HTTP_201_CREATED)
async def create_comment(
        comment_in: CommentCreate,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    """Create a new comment on a task."""
    # Verify task exists
    task = await crud_task.get_task_by_id(db, comment_in.task_id)
    if not task:
        logger.warning("Task not found for comment creation",
                       extra={"user_id": current_user.id, "task_id": comment_in.task_id})
        raise HTTPException(status_code=404, detail="Task not found")

    # Regular users can comment only on their own tasks
    if current_user.role != "admin" and task.owner_id != current_user.id:
        logger.warning("Forbidden comment creation attempt",
                       extra={"user_id": current_user.id, "task_id": comment_in.task_id})
        raise HTTPException(status_code=403, detail="Forbidden")

    # Create comment
    comment = await crud_comment.create_comment(db, comment_in, user_id=current_user.id)

    # Invalidate related caches
    await cache.delete_pattern(f"comments:*")
    await cache.delete(f"task:{comment_in.task_id}")  # Task cache includes comments

    logger.info("Comment created",
                extra={"user_id": current_user.id, "comment_id": comment.id, "task_id": comment_in.task_id})
    return comment

# ----- Get comments with pagination and filtering -----
@router.get("/", response_model=PaginatedResponse[CommentRead])
async def get_comments(
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(20, ge=1, le=100, description="Items per page"),
        task_id: Optional[int] = Query(None, description="Filter by task ID"),
        user_id: Optional[int] = Query(None, description="Filter by user ID (admin only)"),
        content_contains: Optional[str] = Query(None, description="Search in comment content"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    """Get comments with pagination and filtering."""
    # Create pagination and filter objects
    pagination = PaginationParams(page=page, page_size=page_size)
    filters = CommentFilters(
        task_id=task_id,
        user_id=user_id if current_user.role == "admin" else None,
        content_contains=content_contains
    )

    # Generate cache key
    cache_key = f"comments:user:{current_user.id}:page:{page}:size:{page_size}:filters:{hash(str(filters.dict()))}"

    # Try cache first
    cached_result = await cache.get(cache_key)
    if cached_result:
        logger.info("Retrieved comments from cache",
                    extra={"user_id": current_user.id, "cache_key": cache_key})
        return PaginatedResponse(**cached_result)

    if current_user.role == "admin":
        comments, total = await crud_comment.get_comments_with_pagination(
            db=db, pagination=pagination, filters=filters
        )
    else:
        # Regular users see only their own comments or comments on their tasks
        comments, total = await crud_comment.get_user_related_comments_with_pagination(
            db=db,
            user_id=current_user.id,
            pagination=pagination,
            filters=filters
        )

    # Create paginated response
    response = PaginatedResponse.create(
        items=[CommentRead.from_orm(comment) for comment in comments],
        total=total,
        page=page,
        page_size=page_size
    )

    # Cache for 3 minutes
    await cache.set(cache_key, response.dict(), expire_seconds=180)
    logger.info("Fetched comments from DB and cached",
                extra={"user_id": current_user.id, "cache_key": cache_key, "total_comments": total})
    return response

# ----- Get single comment by ID -----
@router.get("/{comment_id}", response_model=CommentRead)
async def get_comment(
        comment_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    """Get a single comment by ID."""
    comment = await crud_comment.get_comment_by_id(db, comment_id)
    if not comment:
        logger.warning("Comment not found",
                       extra={"user_id": current_user.id, "comment_id": comment_id})
        raise HTTPException(status_code=404, detail="Comment not found")

    # Regular user can only access own comment or comment on own task
    if current_user.role != "admin" and comment.user_id != current_user.id:
        task = await crud_task.get_task_by_id(db, comment.task_id)
        if not task or task.owner_id != current_user.id:
            logger.warning("Forbidden comment access attempt",
                           extra={"user_id": current_user.id, "comment_id": comment_id})
            raise HTTPException(status_code=403, detail="Forbidden")

    logger.info("Comment retrieved",
                extra={"user_id": current_user.id, "comment_id": comment_id})
    return comment

# ----- Update comment -----
@router.patch("/{comment_id}", response_model=CommentRead)
async def update_comment(
        comment_id: int,
        content: str = Query(..., description="New comment content"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    """Update a comment (only content can be updated)."""
    comment = await crud_comment.get_comment_by_id(db, comment_id)
    if not comment:
        logger.warning("Comment not found for update",
                       extra={"user_id": current_user.id, "comment_id": comment_id})
        raise HTTPException(status_code=404, detail="Comment not found")

    # Only comment author or admin can update
    if current_user.role != "admin" and comment.user_id != current_user.id:
        logger.warning("Forbidden comment update attempt",
                       extra={"user_id": current_user.id, "comment_id": comment_id})
        raise HTTPException(status_code=403, detail="Forbidden")

    # Update comment
    updated_comment = await crud_comment.update_comment(db, comment, {"content": content})

    # Invalidate caches
    await cache.delete_pattern(f"comments:*")
    await cache.delete(f"task:{comment.task_id}")

    logger.info("Comment updated",
                extra={"user_id": current_user.id, "comment_id": comment_id})
    return updated_comment

# ----- Delete comment -----
@router.delete("/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_comment(
        comment_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session)
):
    """Delete a comment."""
    comment = await crud_comment.get_comment_by_id(db, comment_id)
    if not comment:
        logger.warning("Comment not found for deletion",
                       extra={"user_id": current_user.id, "comment_id": comment_id})
        raise HTTPException(status_code=404, detail="Comment not found")

    if current_user.role != "admin" and comment.user_id != current_user.id:
        logger.warning("Forbidden comment deletion attempt",
                       extra={"user_id": current_user.id, "comment_id": comment_id})
        raise HTTPException(status_code=403, detail="Forbidden")

    task_id = comment.task_id
    await crud_comment.delete_comment(db, comment)
    # Invalidate caches
    await cache.delete_pattern(f"comments:*")
    await cache.delete(f"task:{task_id}")
    logger.info("Comment deleted",
                extra={"user_id": current_user.id, "comment_id": comment_id, "task_id": task_id})
    return None