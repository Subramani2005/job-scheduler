from datetime import datetime
from sqlalchemy import text
from app import db
from app.models import Job

def create_job(queue_id, name, job_type, payload=None, priority=0,
                run_at=None, cron_expression=None, retry_policy_id=None,
                idempotency_key=None):
    # if run_at is set in the future -> scheduled, else queued immediately
    status = "scheduled" if run_at else "queued"

    job = Job(
        queue_id=queue_id,
        name=name,
        job_type=job_type,
        payload=payload or {},
        priority=priority,
        run_at=run_at,
        cron_expression=cron_expression,
        retry_policy_id=retry_policy_id,
        idempotency_key=idempotency_key,
        status=status
    )
    db.session.add(job)
    db.session.commit()
    return job

def get_jobs_for_queue(queue_id, status_filter=None):
    query = Job.query.filter_by(queue_id=queue_id)
    if status_filter:
        query = query.filter_by(status=status_filter)
    return query.order_by(Job.created_at.desc()).all()

def get_job(job_id):
    return Job.query.get(job_id)

def claim_next_job(worker_id, queue_id=None):
    """
    Atomically claims the next available job using SELECT ... FOR UPDATE SKIP LOCKED.

    WHY raw SQL here instead of the ORM: SQLAlchemy's query layer doesn't
    expose SKIP LOCKED cleanly through its normal filter API in a single
    atomic statement. This is the one place raw SQL is justified -- it's
    the concurrency-critical path, and the alternative (ORM read-then-write)
    has a race condition between two workers reading the same row before
    either commits.
    """
    queue_filter = "AND queue_id = :queue_id" if queue_id else ""

    sql = text(f"""
        UPDATE jobs
        SET status = 'claimed',
            claimed_by = :worker_id,
            updated_at = now()
        WHERE id = (
            SELECT id FROM jobs
            WHERE status = 'queued'
            {queue_filter}
            ORDER BY priority DESC, created_at ASC
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        RETURNING id, queue_id, name, job_type, payload, retry_policy_id, attempt_count;
    """)

    params = {"worker_id": worker_id}
    if queue_id:
        params["queue_id"] = queue_id

    result = db.session.execute(sql, params).fetchone()
    db.session.commit()

    if not result:
        return None

    return dict(result._mapping)

def mark_job_running(job_id):
    job = Job.query.get(job_id)
    job.status = "running"
    job.attempt_count += 1
    db.session.commit()
    return job

def mark_job_completed(job_id):
    job = Job.query.get(job_id)
    job.status = "completed"
    job.claimed_by = None
    db.session.commit()
    return job

def mark_job_failed(job_id):
    """Just flips status -- retry decision handled by retry_service."""
    job = Job.query.get(job_id)
    job.status = "failed"
    job.claimed_by = None
    db.session.commit()
    return job

def requeue_job(job_id, next_run_at=None):
    job = Job.query.get(job_id)
    job.status = "scheduled" if next_run_at else "queued"
    job.run_at = next_run_at
    job.claimed_by = None
    db.session.commit()
    return job