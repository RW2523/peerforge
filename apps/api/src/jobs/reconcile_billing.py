"""Run the billing reconciliation once, then exit.

For deployments that don't run Celery Beat (e.g. eager mode, or a platform
cron / scheduled job). Prints a JSON summary and exits non-zero if the run
errored on any workspace, so a scheduler can alert on it.

    python -m src.jobs.reconcile_billing
"""
import json
import logging
import sys

from src.services.billing_sync import reconcile_all


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    result = reconcile_all()
    print(json.dumps(result))
    return 1 if result.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())
