from celery import Celery

from config import REDIS_URL, setup_logging

setup_logging()

celery_app = Celery(
    "indoc",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)
