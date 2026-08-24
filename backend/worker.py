"""
Standalone worker process.

WHY this is a separate script (`python worker.py`) and not a thread inside
the Flask API process: in a real distributed scheduler, workers and the API
scale independently -- you might run 1 API instance and 20 worker instances
under load. Coupling worker execution to the web process would mean you
can't scale them separately, and a crashing job handler could take the API
down with it. Industry pattern: API and workers are always separate
deployables (see Celery, Sidekiq, BullMQ -- worker is always its own process).

WHY polling instead of a message queue (e.g. RabbitMQ/SQS) pushing jobs to
workers: the assignment's core ask is a Postgres-backed scheduler, and
FOR UPDATE SKIP LOCKED gives push-queue-like guarantees (no double-delivery)
without needing extra infra. Trade-off worth stating out loud in interview:
polling has latency = poll interval (here, 2s), whereas a real message queue
gives near-instant delivery. For THIS assignment's scale, that trade-off is
the right one -- for a production system processing millions of jobs/day,
I'd reach for SQS/RabbitMQ instead.
"""

import time
import socket
import importlib
from datetime import datetime

from app import create_app, db
from app.models import Worker, JobExecution
from app.services import job_service, retry_service

POLL_INTERVAL_SEC = 2
HEARTBEAT_INTERVAL_SEC = 10


def register_worker():
    # WHY append a thread id to hostname: when several worker loops run as
    # threads inside one process (free-tier deployment), they'd otherwise
    # all register with the identical hostname, making it impossible to
    # tell them apart in the `workers` table or in logs when demonstrating
    # concurrent claiming.
    import threading
    hostname = f"{socket.gethostname()}-t{threading.get_ident() % 10000}"
    worker = Worker(hostname=hostname, status="active",
                     last_seen_at=datetime.utcnow())
    db.session.add(worker)
    db.session.commit()
    return worker


def heartbeat(worker):
    worker.last_seen_at = datetime.utcnow()
    worker.status = "active"
    db.session.commit()


def execute_job(job_dict):
    """
    Dispatches to the actual job handler based on job_type.

    WHY a dispatch-by-string-key registry instead of e.g. eval() or storing
    executable code in the DB: storing/eval-ing code from the database is a
    remote-code-execution risk -- never do this. A fixed registry of known,
    reviewed handler functions is the safe, standard pattern (same idea as
    Celery task registration).
    """
    job_type = job_dict["job_type"]
    handler = JOB_HANDLERS.get(job_type)
    if not handler:
        raise ValueError(f"no handler registered for job_type '{job_type}'")
    return handler(job_dict["payload"])


def example_handler(payload):
    # placeholder -- replace with real task logic (send email, process file, etc.)
    time.sleep(1)
    return {"result": "ok", "echo": payload}


def always_fail_handler(payload):
    """
    WHY this handler exists: to demonstrate retry backoff and the
    dead-letter queue on demand, rather than waiting for a real failure to
    happen naturally. Create a job with job_type="always_fail" and a
    retry_policy attached -- you'll see it retry with increasing delay,
    then land in dead_letter_queue once max_attempts is hit. Useful
    specifically for a live demo of DLQ behavior.
    """
    raise RuntimeError(f"intentional failure for demo purposes: {payload}")


def flaky_handler(payload):
    """Fails ~50% of the time -- demonstrates a job that eventually
    succeeds after one or two retries, distinct from always_fail which
    demonstrates the DLQ path."""
    import random
    if random.random() < 0.5:
        raise RuntimeError("simulated transient failure")
    return {"result": "ok", "echo": payload}


JOB_HANDLERS = {
    "example": example_handler,
    "always_fail": always_fail_handler,
    "flaky": flaky_handler,
}


def run_worker_loop():
    app = create_app()
    with app.app_context():
        worker = register_worker()
        print(f"[worker {worker.id}] started on {worker.hostname}")

        last_heartbeat = time.time()

        while True:
            if time.time() - last_heartbeat > HEARTBEAT_INTERVAL_SEC:
                heartbeat(worker)
                last_heartbeat = time.time()

            # promote any due retries before claiming, so they're pickable
            retry_service.promote_due_retries()

            claimed = job_service.claim_next_job(worker.id)

            if not claimed:
                time.sleep(POLL_INTERVAL_SEC)
                continue

            job_id = claimed["id"]
            attempt_no = claimed["attempt_count"] + 1
            print(f"[worker {worker.id}] claimed job {job_id} (attempt {attempt_no})")

            job_service.mark_job_running(job_id)

            execution = JobExecution(
                job_id=job_id, worker_id=worker.id,
                attempt_no=attempt_no, status="running",
                started_at=datetime.utcnow()
            )
            db.session.add(execution)
            db.session.commit()

            try:
                result = execute_job(claimed)
                execution.status = "succeeded"
                execution.output = str(result)
                execution.finished_at = datetime.utcnow()
                db.session.commit()

                job_service.mark_job_completed(job_id)
                print(f"[worker {worker.id}] job {job_id} completed")

            except Exception as e:
                execution.status = "failed"
                execution.error_message = str(e)
                execution.finished_at = datetime.utcnow()
                db.session.commit()

                job_service.mark_job_failed(job_id)
                retry_service.handle_job_failure(job_id, str(e))
                print(f"[worker {worker.id}] job {job_id} failed: {e}")


if __name__ == "__main__":
    run_worker_loop()
