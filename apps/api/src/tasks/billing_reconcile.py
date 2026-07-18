"""Celery task: nightly billing reconciliation.

Runs `reconcile_all()` — pulls the live subscription for every workspace linked
to Stripe and repairs any drift a missed/failed webhook left behind. Scheduled
via Celery Beat (see celery_app.beat_schedule) or run directly for cron-based
deployments: `python -m src.jobs.reconcile_billing`.
"""
import logging

from src.celery_app import celery_app
from src.services.billing_sync import reconcile_all

logger = logging.getLogger(__name__)


@celery_app.task(name="src.tasks.billing_reconcile.reconcile_subscriptions", bind=True)
def reconcile_subscriptions(self):
    """Reconcile every linked workspace against Stripe. Idempotent."""
    result = reconcile_all()
    logger.info("Nightly billing reconcile: %s", result)
    return result
