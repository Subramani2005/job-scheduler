import os
import threading
from app import create_app, db
from app.models import User, Project, Queue, RetryPolicy, Worker, Job, JobExecution, DeadLetterQueue

app = create_app()


def start_background_processes():
    """
    WHY threads instead of separate processes here: Render's free tier only
    offers Web Services, not Background Workers (those need a paid plan).
    Running worker.py and scheduler.py as daemon threads inside the same
    process lets the whole system run on a single free instance.

    Trade-off to state explicitly if asked: this sacrifices the independent
    scaling we designed for (worker count tied to API instance count, GIL
    contention under heavy load) in exchange for zero hosting cost. In a
    paid/production deployment, these would go back to being separate
    Background Worker services exactly as originally architected -- this
    is a deliberate, temporary concession to a free-tier constraint, not
    a redesign of the architecture.
    """
    from worker import run_worker_loop
    from scheduler import run_scheduler_loop

    # WHY the shared `app` object (built once above) is passed into every
    # thread instead of each thread calling create_app() itself: that was
    # the actual cause of an out-of-memory crash on Render's free tier --
    # N threads each building their own SQLAlchemy engine/connection pool.
    # One shared engine, reused across threads, keeps memory flat
    # regardless of WORKER_COUNT.
    worker_count = int(os.environ.get("WORKER_COUNT", "2"))
    for _ in range(worker_count):
        threading.Thread(target=run_worker_loop, args=(app,), daemon=True).start()

    threading.Thread(target=run_scheduler_loop, args=(app,), daemon=True).start()


# only start background threads in the actual running server process,
# not during `flask db migrate` or other CLI invocations that import this file
if os.environ.get("RUN_BACKGROUND_PROCESSES", "true").lower() == "true":
    start_background_processes()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
