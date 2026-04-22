from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "edu",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_default_queue="default",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=300,
    task_soft_time_limit=240,
)

celery_app.autodiscover_tasks(["app.modules"])
