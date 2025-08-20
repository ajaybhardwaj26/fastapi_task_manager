from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx
from app.core.celery_app import celery_app
from app.db.session import AsyncSessionLocal
from app.api.v1.crud import task as crud_task
import asyncio
import logging
from tenacity import after_log

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@celery_app.task
def fetch_task_metadata(task_id: int):
    """Celery task to fetch external metadata (sync wrapper for async function)"""
    return asyncio.run(_fetch_task_metadata_async(task_id))

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    after=after_log(logger, logging.WARNING)
)
async def _fetch_task_metadata_async(task_id: int):
    """Internal async function for fetching task metadata"""
    async with AsyncSessionLocal() as db:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"https://jsonplaceholder.typicode.com/todos/{task_id}")
                resp.raise_for_status()
                metadata = resp.json()

            task = await crud_task.get_task_by_id(db, task_id)
            if task:
                await crud_task.update_task_metadata(db, task, metadata)
                logger.info(f"Updated task {task_id} with metadata")
            else:
                logger.warning(f"Task {task_id} not found")

        except Exception as e:
            logger.error(f"Failed to fetch metadata for task {task_id}: {e}")
            raise