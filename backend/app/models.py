import uuid
from datetime import datetime
from app import db

def gen_uuid():
    return str(uuid.uuid4())

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    projects = db.relationship("Project", backref="user", lazy=True)

class Project(db.Model):
    __tablename__ = "projects"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    queues = db.relationship("Queue", backref="project", lazy=True)

class Queue(db.Model):
    __tablename__ = "queues"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    project_id = db.Column(db.String(36), db.ForeignKey("projects.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    max_concurrency = db.Column(db.Integer, default=5)
    is_paused = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    jobs = db.relationship("Job", backref="queue", lazy=True)

class RetryPolicy(db.Model):
    __tablename__ = "retry_policies"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(100), nullable=False)
    strategy = db.Column(db.String(20), nullable=False)  # fixed | linear | exponential
    max_attempts = db.Column(db.Integer, nullable=False)
    base_delay_sec = db.Column(db.Integer, nullable=False)

    jobs = db.relationship("Job", backref="retry_policy", lazy=True)

class Worker(db.Model):
    __tablename__ = "workers"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    hostname = db.Column(db.String(255))
    status = db.Column(db.String(20), default="idle")  # active | idle | dead
    last_seen_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Job(db.Model):
    __tablename__ = "jobs"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    queue_id = db.Column(db.String(36), db.ForeignKey("queues.id"), nullable=False)
    retry_policy_id = db.Column(db.String(36), db.ForeignKey("retry_policies.id"))
    claimed_by = db.Column(db.String(36), db.ForeignKey("workers.id"))

    idempotency_key = db.Column(db.String(255), unique=True)
    name = db.Column(db.String(255), nullable=False)
    job_type = db.Column(db.String(100), nullable=False)
    payload = db.Column(db.JSON)
    priority = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default="queued")
    # queued | scheduled | claimed | running | completed | failed | retrying | dead_letter

    run_at = db.Column(db.DateTime)              # null = run ASAP
    cron_expression = db.Column(db.String(100))  # null unless recurring
    attempt_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    executions = db.relationship("JobExecution", backref="job", lazy=True)

class JobExecution(db.Model):
    __tablename__ = "job_executions"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    job_id = db.Column(db.String(36), db.ForeignKey("jobs.id"), nullable=False)
    worker_id = db.Column(db.String(36), db.ForeignKey("workers.id"))

    attempt_no = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False)  # running | succeeded | failed
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)
    output = db.Column(db.Text)  # doubles as job_logs if you skip that table

class DeadLetterQueue(db.Model):
    __tablename__ = "dead_letter_queue"
    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    job_id = db.Column(db.String(36), db.ForeignKey("jobs.id"), nullable=False)
    final_error = db.Column(db.Text)
    moved_at = db.Column(db.DateTime, default=datetime.utcnow)