import asyncio
from app.db.session import AsyncSessionLocal
from app.celery_app.helpers import fetch_external_data_and_update
from app.core.celery_app import celery_app

@celery_app.task
def fetch_and_update_task(task_id: int):
    """
    Celery task to fetch external data and update task in background.

    Args:
        task_id: ID of the task to update
    """
    async def _run():
        async with AsyncSessionLocal() as db:
            await fetch_external_data_and_update(db, task_id)

    asyncio.run(_run())