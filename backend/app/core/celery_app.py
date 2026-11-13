from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "documind",
    broker=settings.redis_url,
    include=["app.tasks.document_ingestion"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    worker_prefetch_multiplier=1,
)
