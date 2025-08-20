from sqlalchemy.ext.asyncio import AsyncSession
from app.api.v1.crud import task as crud_task

async def fetch_external_data_and_update(db: AsyncSession, task_id: int):
    """
    Fetch data from an external API and update the task in DB.
    """
    # Example external API call (replace with your real API logic)
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.get("https://jsonplaceholder.typicode.com/todos/1")
        if response.status_code == 200:
            data = response.json()
            # Update task description with external data
            task_data = {
                "description": f"{data.get('title')} (fetched from API)",
                "task_metadata": data
            }
            await crud_task.update_task(db, task_id, task_data)
