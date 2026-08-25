"""
Scheduler process.

WHY a separate process from worker.py, even though both poll the DB:
different responsibility and different scaling need. The scheduler must
run as exactly ONE instance (running two would create duplicate cron
occurrences), while workers are meant to run as MANY instances for
throughput. Bundling them would force you to run only one worker, or
build extra locking to stop duplicate scheduler ticks -- cleaner to keep
them as separate deployables with different scaling rules from the start.

WHY APScheduler's simple interval loop instead of a full separate cron
daemon like system cron: this keeps the whole scheduling concern inside
the app's own codebase/deploy unit -- one Python process to run and
reason about, no OS-level cron config to keep in sync across environments
(local Windows dev vs Linux deploy target behave differently for cron).
Trade-off: APScheduler's timer lives in-process, so if this process dies,
scheduling pauses until it's restarted -- acceptable here since Render/
Railway auto-restart crashed processes.
"""

import time
from datetime import datetime
from croniter import croniter

from app import create_app, db
from app.models import Job
from app.services import job_service, retry_service

TICK_INTERVAL_SEC = 5


def promote_scheduled_jobs():
    """scheduled -> queued once run_at has passed."""
    now = datetime.utcnow()
    due = Job.query.filter(
        Job.status == "scheduled",
        Job.run_at <= now
    ).all()

    for job in due:
        job.status = "queued"
    db.session.commit()

    if due:
        print(f"[scheduler] promoted {len(due)} scheduled job(s) to queued")


def spawn_next_cron_occurrences():
    """
    For completed jobs with a cron_expression, create the next occurrence.

    WHY check on 'completed' cron jobs rather than re-using the same job
    row forever: keeps the append-only execution history intact per
    occurrence (one Job row = one scheduled instance, consistent with how
    JobExecution already models one row per attempt). Re-using a single
    row would mean losing the history of when each past occurrence ran.
    """
    completed_cron_jobs = Job.query.filter(
        Job.status == "completed",
        Job.cron_expression.isnot(None)
    ).all()

    for job in completed_cron_jobs:
        base_time = job.run_at or job.updated_at or datetime.utcnow()
        next_time = croniter(job.cron_expression, base_time).get_next(datetime)

        job_service.create_job(
            queue_id=job.queue_id,
            name=job.name,
            job_type=job.job_type,
            payload=job.payload,
            priority=job.priority,
            run_at=next_time,
            cron_expression=job.cron_expression,
            retry_policy_id=job.retry_policy_id,
        )

        # mark this occurrence so we don't spawn its child again next tick
        job.cron_expression = None
        db.session.commit()
        print(f"[scheduler] spawned next occurrence of '{job.name}' at {next_time}")


def run_scheduler_loop(app=None):
    if app is None:
        app = create_app()
    with app.app_context():
        print("[scheduler] started")
        while True:
            promote_scheduled_jobs()
            retry_service.promote_due_retries()
            spawn_next_cron_occurrences()
            time.sleep(TICK_INTERVAL_SEC)


if __name__ == "__main__":
    run_scheduler_loop()
