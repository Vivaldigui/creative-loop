# Import all task modules so Celery autodiscover registers them.
from . import creative_tasks, experiment_tasks, meta_tasks, publish_task  # noqa: F401
