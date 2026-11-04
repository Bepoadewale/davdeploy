"""Bounded SQS-triggered worker entry point.

SQS is the wake-up and retry transport. Durable workflow state and idempotency
remain in the control-plane database.
"""

from __future__ import annotations

import json
import os
from typing import Any

from davdeploy.db import SessionLocal
from davdeploy.service import ProductService

WORKER_QUEUE_METHODS = (
    "run_next_generated_plan_run",
    "run_next_discovery_job",
    "run_next_cloud_execution",
    "run_next_job",
)


def handler(event: dict[str, Any], _context: Any) -> dict[str, int]:
    """Reconcile event records, then claim a deliberately small durable backlog."""
    records = event.get("Records") or []
    try:
        maximum_jobs = int(os.getenv("DAVDEPLOY_WORKER_MAX_JOBS_PER_WAKEUP", "5"))
    except ValueError:
        maximum_jobs = 5
    # Reserve one claim slot per durable queue kind. A large Nova backlog must
    # not consume the whole invocation before other work gets a chance.
    maximum_jobs = min(max(maximum_jobs, len(WORKER_QUEUE_METHODS)), 10)
    processed_events = 0
    for record in records:
        with SessionLocal() as db:
            service = ProductService(db)
            body = record.get("body") if isinstance(record, dict) else None
            try:
                message = json.loads(body) if isinstance(body, str) else {}
            except json.JSONDecodeError:
                # A malformed wake-up carries no actionable build identifier. Do not let it
                # repeatedly redrive an otherwise healthy durable worker backlog.
                message = {}
            build_id = ((message.get("detail") or {}).get("build-id")) if isinstance(message, dict) else None
            if build_id:
                reconciled = service.reconcile_cloud_execution_build(str(build_id))
                if not reconciled:
                    reconciled = service.reconcile_generated_plan_build(str(build_id))
                if reconciled:
                    processed_events += 1

    processed_jobs = 0
    next_queue_index = 0
    for _ in range(maximum_jobs):
        claimed = False
        with SessionLocal() as db:
            service = ProductService(db)
            for offset in range(len(WORKER_QUEUE_METHODS)):
                queue_index = (next_queue_index + offset) % len(WORKER_QUEUE_METHODS)
                run_next = getattr(service, WORKER_QUEUE_METHODS[queue_index])
                if run_next():
                    processed_jobs += 1
                    next_queue_index = (queue_index + 1) % len(WORKER_QUEUE_METHODS)
                    claimed = True
                    break
        if not claimed:
            break
    return {
        "records": len(records),
        "processed": processed_events + processed_jobs,
        "processed_jobs": processed_jobs,
    }
