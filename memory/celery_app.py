# In memory/celery_app.py:
import sys
import os
# Dynamically add the root directory of the project to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from celery import Celery
from config.settings import setting



celery_app = Celery(
    "assistant_task",
    broker=setting.REDIS_URL,
    backend=setting.REDIS_URL,
    include=["tasks.backgorund_tasks"]
)


celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)