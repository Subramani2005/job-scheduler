"""
Tests focus on the two correctness-critical paths, not broad shallow
coverage of every CRUD endpoint.

WHY these two and not, say, testing every route: claim_next_job and the
retry backoff math are the parts where a bug is silent and catastrophic
(duplicate job execution, or a job retrying forever / never retrying).
A bug in a CRUD route is obvious the moment you call it manually. A race
condition in claim_next_job might not show up until production load --
that's exactly the kind of bug automated tests exist to catch before
a human ever notices.
"""

import pytest
import threading
from datetime import datetime, timedelta

from app import create_app, db
from app.models import User, Project, Queue, Job, RetryPolicy, Worker
from app.services import job_service, retry_service


@pytest.fixture
def app():
    app = create_app()
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def setup_queue(app):
    user = User(email="t@test.com", password_hash="x")
    db.session.add(user)
    db.session.commit()

    project = Project(user_id=user.id, name="test project")
    db.session.add(project)
    db.session.commit()

    queue = Queue(project_id=project.id, name="test queue")
    db.session.add(queue)
    db.session.commit()

    return queue


def test_claim_next_job_returns_none_when_empty(app, setup_queue):
    worker = Worker(hostname="w1")
    db.session.add(worker)
    db.session.commit()

    result = job_service.claim_next_job(worker.id)
    assert result is None


def test_claim_next_job_claims_highest_priority_first(app, setup_queue):
    job_service.create_job(setup_queue.id, "low", "example", priority=1)
    job_service.create_job(setup_queue.id, "high", "example", priority=10)

    worker = Worker(hostname="w1")
    db.session.add(worker)
    db.session.commit()

    claimed = job_service.claim_next_job(worker.id)
    assert claimed["name"] == "high"


def test_claim_next_job_never_double_claims(app, setup_queue):
    """
    Simulates two workers racing for the same single job.

    NOTE: SQLite doesn't support FOR UPDATE SKIP LOCKED the way Postgres
    does, so this test validates the *status-flip* correctness (only one
    claim succeeds), not true concurrent-transaction locking -- that
    guarantee is Postgres-specific and would need an integration test
    against a real Postgres instance to fully verify. Worth stating this
    limitation explicitly if asked about test coverage.
    """
    job_service.create_job(setup_queue.id, "solo job", "example")

    w1 = Worker(hostname="w1")
    w2 = Worker(hostname="w2")
    db.session.add_all([w1, w2])
    db.session.commit()

    first = job_service.claim_next_job(w1.id)
    second = job_service.claim_next_job(w2.id)

    assert first is not None
    assert second is None  # nothing left to claim


def test_fixed_retry_delay_is_constant():
    strategy = retry_service.FixedRetry()
    assert strategy.next_delay_seconds(1, 30) == 30
    assert strategy.next_delay_seconds(5, 30) == 30


def test_exponential_retry_grows_and_caps(app):
    strategy = retry_service.ExponentialRetry()
    assert strategy.next_delay_seconds(1, 10) == 10
    assert strategy.next_delay_seconds(2, 10) == 20
    assert strategy.next_delay_seconds(3, 10) == 40
    assert strategy.next_delay_seconds(20, 10) == 3600  # capped


def test_job_moves_to_dead_letter_after_max_attempts(app, setup_queue):
    policy = RetryPolicy(name="test", strategy="fixed",
                          max_attempts=2, base_delay_sec=1)
    db.session.add(policy)
    db.session.commit()

    job = job_service.create_job(
        setup_queue.id, "will fail", "example",
        retry_policy_id=policy.id
    )
    job.attempt_count = 2
    db.session.commit()

    result = retry_service.handle_job_failure(job.id, "boom")
    assert result.status == "dead_letter"


def test_job_retries_when_attempts_remain(app, setup_queue):
    policy = RetryPolicy(name="test", strategy="fixed",
                          max_attempts=5, base_delay_sec=1)
    db.session.add(policy)
    db.session.commit()

    job = job_service.create_job(
        setup_queue.id, "will retry", "example",
        retry_policy_id=policy.id
    )
    job.attempt_count = 1
    db.session.commit()

    result = retry_service.handle_job_failure(job.id, "boom")
    assert result.status == "retrying"
    assert result.run_at is not None