from datetime import datetime
from sqlalchemy import text
from app import db
from app.models import Job


def create_job(queue_id, name, job_type, payload=None, priority=0,
                run_at=None, cron_expression=None, retry_policy_id=None,
                idempotency_key=None):
    # WHY fall back to a default policy instead of leaving retry_policy_id
    # null: a null policy means zero retries -- a job fails once and goes
    # straight to dead_letter_queue, which is surprising default behavior
    # for anyone creating a job without explicitly thinking about retries.
    # A sensible default (3 attempts, exponential backoff) matches what
    # most job schedulers (Celery, Sidekiq) apply out of the box, while
    # still letting callers override it per-job when they want different
    # behavior (or explicitly pass retry_policy_id=None semantics via a
    # policy with max_attempts=1, if "no retry" is genuinely intended).
    if retry_policy_id is None:
        retry_policy_id = get_or_create_default_policy().id

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


def get_or_create_default_policy():
    """
    Returns a shared 'default' retry policy, creating it once if it
    doesn't exist yet. WHY a singleton default row instead of hardcoding
    max_attempts=3 directly on Job: keeps the policy visible and editable
    like any other RetryPolicy (e.g. from an admin UI later), rather than
    a magic number buried in service code.
    """
    from app.models import RetryPolicy
    policy = RetryPolicy.query.filter_by(name="default").first()
    if not policy:
        policy = RetryPolicy(
            name="default", strategy="exponential",
            max_attempts=3, base_delay_sec=10
        )
        db.session.add(policy)
        db.session.commit()
    return policy


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

    WHY max_concurrency is enforced with a correlated subquery counting
    in-flight jobs per queue, rather than a separate "current load" counter
    column: a counter column can drift out of sync if a worker crashes
    mid-job (the decrement never happens). Computing the count live from
    actual row states is always correct, at the cost of a slightly more
    expensive query -- an acceptable trade at this system's scale.
    """
    queue_filter = "AND j.queue_id = :queue_id" if queue_id else ""

    sql = text(f"""
        UPDATE jobs
        SET status = 'claimed',
            claimed_by = :worker_id,
            updated_at = now()
        WHERE id = (
            SELECT j.id FROM jobs j
            JOIN queues q ON q.id = j.queue_id
            WHERE j.status = 'queued'
              AND q.is_paused = false
              {queue_filter}
              AND (
                SELECT COUNT(*) FROM jobs j2
                WHERE j2.queue_id = j.queue_id
                  AND j2.status IN ('claimed', 'running')
              ) < q.max_concurrency
            ORDER BY j.priority DESC, j.created_at ASC
            FOR UPDATE OF j SKIP LOCKED
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
