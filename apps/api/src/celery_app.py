"""
Celery application configuration for Arinar V2
Handles asynchronous material processing tasks
"""

import os

from celery import Celery
from src.config import settings

# Create Celery app
celery_app = Celery(
    "arinar",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.tasks.material_processing", "src.tasks.preflight"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    task_soft_time_limit=540,  # 9 minutes soft limit
    worker_prefetch_multiplier=1,  # Process one task at a time for better visibility
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks (prevent memory leaks)
    task_acks_late=True,  # Only ack after task completion (safe for crashes)
    task_reject_on_worker_lost=True,  # Requeue if worker crashes
    # Eager mode: run tasks synchronously in the API process — no worker or
    # Redis needed. For small single-instance deployments (free tiers).
    task_always_eager=os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true",
    task_eager_propagates=os.getenv("CELERY_TASK_ALWAYS_EAGER", "false").lower() == "true",
    result_expires=3600,  # Results expire after 1 hour
)

# Route tasks to named queues.
# IMPORTANT: workers must be started with --queues=celery,materials,preflight
# (or use the default "celery" queue for everything by removing these routes).
# All queues are consolidated here so a single worker handles the full pipeline.
celery_app.conf.task_routes = {
    "src.tasks.material_processing.process_material": {"queue": "materials"},
    "src.tasks.preflight.*": {"queue": "preflight"},
}

# Workers pick up all queues by default (avoids "task stuck pending" issues).
celery_app.conf.task_default_queue = "celery"
celery_app.conf.worker_queues = ("celery", "materials", "preflight")
