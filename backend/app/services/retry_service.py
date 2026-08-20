"""
Retry strategy implementations.

WHY a strategy pattern (class per strategy) instead of an if/elif chain
inline in job_service: this is the Open/Closed principle in practice.
Adding a new backoff algorithm (e.g. "jittered exponential") later means
adding one class -- zero changes to any calling code. An if/elif chain
would need editing every time a strategy is added, and risks breaking
existing strategies while doing it.
"""

from datetime import datetime, timedelta
from app import db
from app.models import Job, DeadLetterQueue


class RetryStrategy:
    def next_delay_seconds(self, attempt: int, base_delay: int) -> int:
        raise NotImplementedError


class FixedRetry(RetryStrategy):
    def next_delay_seconds(self, attempt, base_delay):
        return base_delay


class LinearRetry(RetryStrategy):
    def next_delay_seconds(self, attempt, base_delay):
        return base_delay * attempt


class ExponentialRetry(RetryStrategy):
    def next_delay_seconds(self, attempt, base_delay):
        # capped at 1 hour -- WHY: uncapped exponential backoff on a long-lived
        # job (e.g. attempt 10) could push next_run_at days into the future,
        # which is rarely the intent. Capping is standard industry practice
        # (same idea AWS SDK / Stripe webhooks use).
        return min(base_delay * (2 ** (attempt - 1)), 3600)


STRATEGY_MAP = {
    "fixed": FixedRetry(),
    "linear": LinearRetry(),
    "exponential": ExponentialRetry(),
}


def handle_job_failure(job_id, error_message):
    """
    Decides: retry with backoff, or move to dead_letter_queue.

    WHY this logic lives here and NOT in job_service.mark_job_failed:
    single responsibility -- job_service only knows how to change a job's
    status. Deciding *what status it becomes next* based on policy is a
    separate concern (business rule vs state mutation), so it gets its
    own module. This also means retry policy changes never touch
    job_service.py at all.
    """
    job = Job.query.get(job_id)
    if not job:
        return None

    if not job.retry_policy_id:
        # no policy attached -> fail permanently, no silent infinite retries
        return _move_to_dlq(job, error_message)

    policy = job.retry_policy
    if job.attempt_count >= policy.max_attempts:
        return _move_to_dlq(job, error_message)

    strategy = STRATEGY_MAP.get(policy.strategy, FixedRetry())
    delay = strategy.next_delay_seconds(job.attempt_count, policy.base_delay_sec)

    job.status = "retrying"
    job.claimed_by = None
    job.run_at = datetime.utcnow() + timedelta(seconds=delay)
    db.session.commit()
    return job


def _move_to_dlq(job, error_message):
    job.status = "dead_letter"
    job.claimed_by = None
    db.session.add(DeadLetterQueue(job_id=job.id, final_error=error_message))
    db.session.commit()
    return job


def promote_due_retries():
    """
    Flips 'retrying' jobs back to 'queued' once their run_at has passed.

    WHY a separate promotion step instead of the worker directly picking up
    'retrying' jobs: keeps claim_next_job's WHERE clause simple (only ever
    reads 'queued'), and keeps "is this job due yet" logic in exactly one
    place instead of duplicated inside the claim query.
    """
    now = datetime.utcnow()
    due_jobs = Job.query.filter(
        Job.status == "retrying",
        Job.run_at <= now
    ).all()

    for job in due_jobs:
        job.status = "queued"
    db.session.commit()
    return len(due_jobs)