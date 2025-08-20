from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List, Optional
from app.models.comment import Comment
from app.schemas.comment import CommentCreate
from typing import Tuple

# ----- Create a new comment -----
async def create_comment(db: AsyncSession, comment_in: CommentCreate, user_id: int) -> Comment:
    """
    Create a new comment.

    Args:
        db: Database session
        comment_in: Comment creation data from request
        user_id: ID of the user creating the comment

    Returns:
        Comment: The created comment object
    """
    comment_data = comment_in.dict()
    comment_data["user_id"] = user_id  # Set the user_id from auth context

    new_comment = Comment(**comment_data)
    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)
    return new_comment

# ----- Get comments for a specific user -----
async def get_comments_by_user(db: AsyncSession, user_id: int) -> List[Comment]:
    result = await db.execute(select(Comment).where(Comment.user_id == user_id))
    return result.scalars().all()

# ----- Get all comments (with optional filters and pagination) -----
async def get_all_comments(
        db: AsyncSession,
        task_id: Optional[int] = None,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20
) -> List[Comment]:
    query = select(Comment)

    if task_id is not None:
        query = query.where(Comment.task_id == task_id)
    if user_id is not None:
        query = query.where(Comment.user_id == user_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

# ----- Get user-related comments (for regular users) -----
async def get_user_related_comments(
        db: AsyncSession,
        user_id: int,
        task_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 20
) -> List[Comment]:
    query = select(Comment).where(Comment.user_id == user_id)

    if task_id is not None:
        query = query.where(Comment.task_id == task_id)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

# ----- Get a single comment by ID -----
async def get_comment_by_id(db: AsyncSession, comment_id: int) -> Optional[Comment]:
    result = await db.execute(select(Comment).where(Comment.id == comment_id))
    return result.scalars().first()

# ----- Delete a comment -----
async def delete_comment(db: AsyncSession, comment: Comment):
    await db.delete(comment)
    await db.commit()

async def get_comments_with_pagination(
        db: AsyncSession,
        pagination: PaginationParams,
        filters: CommentFilters
) -> Tuple[List[Comment], int]:
    """Get comments with pagination and filtering for admins."""
    from sqlalchemy import func, and_

    query = select(Comment).options(
        selectinload(Comment.author),
        selectinload(Comment.task)
    )

    conditions = []
    if filters.task_id:
        conditions.append(Comment.task_id == filters.task_id)
    if filters.user_id:
        conditions.append(Comment.user_id == filters.user_id)
    if filters.content_contains:
        conditions.append(Comment.content.ilike(f"%{filters.content_contains}%"))

    if conditions:
        query = query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count(Comment.id))
    if conditions:
        count_query = count_query.where(and_(*conditions))

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.order_by(Comment.created_at.desc()).offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    comments = result.scalars().all()

    return comments, total

async def get_user_related_comments_with_pagination(
        db: AsyncSession,
        user_id: int,
        pagination: PaginationParams,
        filters: CommentFilters
) -> Tuple[List[Comment], int]:
    """Get user-related comments with pagination."""
    from sqlalchemy import func, and_, or_
    from app.models.task import Task

    # Comments user made OR comments on user's tasks
    query = select(Comment).options(
        selectinload(Comment.author),
        selectinload(Comment.task)
    ).join(Task, Comment.task_id == Task.id).where(
        or_(
            Comment.user_id == user_id,
            Task.owner_id == user_id
        )
    )

    conditions = []
    if filters.task_id:
        conditions.append(Comment.task_id == filters.task_id)
    if filters.content_contains:
        conditions.append(Comment.content.ilike(f"%{filters.content_contains}%"))

    if conditions:
        query = query.where(and_(*conditions))

    # Get total count
    count_query = select(func.count(Comment.id)).join(Task, Comment.task_id == Task.id).where(
        or_(
            Comment.user_id == user_id,
            Task.owner_id == user_id
        )
    )
    if conditions:
        count_query = count_query.where(and_(*conditions))

    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Apply pagination
    query = query.order_by(Comment.created_at.desc()).offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(query)
    comments = result.scalars().all()

    return comments, total

async def update_comment(db: AsyncSession, comment: Comment, updates: dict) -> Comment:
    """Update a comment."""
    for key, value in updates.items():
        setattr(comment, key, value)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment