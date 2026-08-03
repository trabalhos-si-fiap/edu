import pkgutil

from celery import Celery

import app.modules as _modules_pkg
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

# autodiscover_tasks looks for a `tasks` module inside each listed package, so
# it must receive every module subpackage (e.g. app.modules.orders), not just
# `app.modules` — passing the parent would only probe app.modules.tasks and
# silently register nothing. Enumerate the subpackages so new modules with a
# tasks.py are picked up automatically.
_module_packages = [
    f"app.modules.{m.name}"
    for m in pkgutil.iter_modules(_modules_pkg.__path__)
    if m.ispkg
]
celery_app.autodiscover_tasks(_module_packages)
