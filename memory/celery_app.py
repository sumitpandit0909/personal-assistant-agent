from celery import Celery
from config.settings import setting



celery_app = Celery(
    "assistant_task",
    broker=setting.REDIS_URL,
    backend='redis://localhost:6379/1',
    
)


celery_app.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)