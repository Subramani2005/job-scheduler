# Distributed Job Scheduler

A distributed job scheduling system supporting immediate, delayed, and recurring (cron) jobs, executed by a horizontally scalable pool of workers with atomic job claiming, configurable retries with backoff, and a dead-letter queue for permanently failed jobs.

**Live demo:** `job-scheduler-wheat.vercel.app`

## Stack

- **Backend:** Flask + Flask-RESTful, SQLAlchemy, Flask-Migrate, Flask-JWT-Extended
- **Database:** PostgreSQL (hosted on Neon)
- **Frontend:** React (Vite), axios
- **Deployment:** Render (backend), Vercel (frontend)

## Architecture

The system is built as three logical processes sharing one database:

- **API** — handles auth and CRUD for projects, queues, and jobs
- **Scheduler** — promotes due/scheduled jobs, promotes due retries, and spawns the next occurrence of recurring (cron) jobs. Designed to run as exactly one instance.
- **Worker pool** — polls for queued jobs, atomically claims one using `SELECT ... FOR UPDATE SKIP LOCKED` (so concurrent workers never claim the same job), executes it, and reports success/failure. Designed to run as many instances for throughput.

> **Note on this deployment:** Render's free tier only offers Web Services, not Background Workers. For this deployment, the worker and scheduler loops run as background threads inside the same process as the API (see `run.py`). In a paid/production deployment these would run as independent processes exactly as designed — `worker.py` and `scheduler.py` are unchanged either way.

Full architecture diagram, ER diagram, and the reasoning behind every major design decision are in [`Design_Document.docx`](./Design_Document.docx).

## Project structure

```
backend/
├── app/
│   ├── models.py           # 8 SQLAlchemy models
│   ├── config.py
│   ├── routes/              # auth, projects, queues, jobs
│   └── services/             # business logic + atomic claim + retry strategies
├── run.py                   # API entrypoint (also starts worker/scheduler threads)
├── worker.py                 # worker loop (claim -> execute -> report)
├── scheduler.py               # promotes scheduled/retry jobs, spawns cron occurrences
├── tests/
├── requirements.txt
└── Procfile

frontend/
├── src/
│   ├── App.jsx
│   ├── api.js
│   └── components/
│       ├── Login.jsx
│       └── Dashboard.jsx
```

## Running locally

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# create backend/.env with:
# DATABASE_URL=postgresql://...
# JWT_SECRET_KEY=your-secret

flask db upgrade
python run.py
```

**Frontend:**
```bash
cd frontend
npm install

# create frontend/.env with:
# VITE_API_URL=http://localhost:5000/api

npm run dev
```

**Run tests:**
```bash
cd backend
pytest
```

## API overview

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/signup` | Create an account |
| POST | `/api/auth/login` | Log in, get a JWT |
| POST / GET | `/api/projects` | Create / list projects |
| GET / DELETE | `/api/projects/{id}` | Get / delete a project |
| POST / GET | `/api/projects/{project_id}/queues` | Create / list queues |
| PATCH | `/api/projects/{project_id}/queues/{queue_id}/pause` | Pause a queue |
| PATCH | `/api/projects/{project_id}/queues/{queue_id}/resume` | Resume a queue |
| POST / GET | `/api/queues/{queue_id}/jobs` | Create / list jobs |
| GET | `/api/queues/{queue_id}/jobs/{job_id}` | Get a job |

All routes except signup/login require `Authorization: Bearer <token>`.

## Job lifecycle

```
scheduled -> queued -> claimed -> running -> completed
                                      |
                                      v
                                  retrying -> queued (once due)
                                      |
                                      v
                                 dead_letter (after max attempts)
```

## Key design decisions (short version)

- **PostgreSQL**, specifically for `SELECT ... FOR UPDATE SKIP LOCKED` — the mechanism that guarantees no two workers ever claim the same job.
- **Raw SQL for the claim query only**, ORM everywhere else — the one place correctness under concurrency justifies bypassing the ORM.
- **Worker, Scheduler, and API as separate processes** — different scaling needs (many workers, exactly one scheduler).
- **Database polling instead of a message broker** — `SKIP LOCKED` gives the same no-double-delivery guarantee without extra infrastructure, at the cost of poll-interval latency.
- **Retry backoff as a Strategy pattern** — adding a new backoff algorithm requires no changes to existing code.

Full reasoning, alternatives considered, and trade-offs for each decision are documented in `Design_Document.docx`.

## Known limitations / future improvements

- `max_concurrency` on queues is stored but not yet enforced in the claim query
- No worker-to-queue affinity (all workers currently pull from all queues)
- Polling-based delivery trades latency for infrastructure simplicity
- CORS is currently permissive for development speed
