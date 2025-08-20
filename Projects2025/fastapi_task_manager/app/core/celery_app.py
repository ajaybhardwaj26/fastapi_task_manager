from celery import Celery
from app.core.config import settings  # your settings module

celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.task_routes = {
    "app.celery_app.tasks.fetch_and_update_task": {"queue": "tasks"},
}

# Optional: autodiscover tasks if you have many
celery_app.autodiscover_tasks(["app.celery_app"])