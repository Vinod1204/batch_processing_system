# Batch Processing System

A small full-stack application for uploading CSV transactions, running backend batch processing, monitoring live job status, and viewing processed results.

## Tech Stack

- Backend: FastAPI, SQLAlchemy, PostgreSQL, threaded batch worker
- Frontend: React (Vite), polling-based live updates
- Database: PostgreSQL (schema auto-created by SQLAlchemy)

## Features

- Upload CSV via `POST /jobs`
- Start processing via `POST /jobs/{id}/start`
- Batch processing with per-batch commit (default batch size: 100)
- Continuous progress updates in `GET /jobs/{id}`
- Result browsing with pagination and filters in `GET /jobs/{id}/transactions`
- Validation and suspicious flagging rules implemented

## Validation Rules Implemented

Required fields:
- `transaction_id`
- `user_id`
- `amount`
- `timestamp`

Format checks:
- `transaction_id` must be GUID
- `user_id` must be GUID
- `amount` must be numeric
- `timestamp` must be ISO-8601 parseable
- `transaction_id` must be unique within each job

Suspicious checks (still valid if format is valid):
- `amount < 0`
- `amount > 50000`

Optional referential check:
- If `REQUIRE_USER_EXISTS=true`, `user_id` must exist in table `users`

## Project Structure

- `backend/app/main.py`: FastAPI app and startup
- `backend/app/api/jobs.py`: Job and transaction endpoints
- `backend/app/models.py`: SQLAlchemy models and indexes
- `backend/app/services/processor.py`: Batch processing pipeline
- `frontend/src/App.jsx`: UI for upload/start/status/results
- `scripts/init_db.sql`: Optional seed users for referential checks
- `sample_transactions.csv`: Sample file for testing

## Backend Setup

1. Create a Python virtual environment and activate it.
2. Install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

3. Copy environment file and edit if needed:

```bash
copy .env.example .env
```

4. Ensure PostgreSQL is running and create database `batch_processing`.

5. Optional: seed users for referential integrity testing:

```bash
psql -U postgres -d batch_processing -f ../scripts/init_db.sql
```

6. Start backend:

```bash
python -m uvicorn app.main:app --reload --port 8000
```

If you run from the repository root instead of the backend folder:

```bash
python -m uvicorn app.main:app --reload --port 8000 --app-dir backend
```

Troubleshooting: if startup fails with "password authentication failed for user postgres", update `DATABASE_URL` in `backend/.env` to the real PostgreSQL password for your machine. If the password contains special characters, URL-encode them (for example: `@` becomes `%40`).

## Frontend Setup

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Start frontend:

```bash
npm run dev
```

3. Open `http://localhost:5173`

## Docker Compose (Optional)

From repo root:

```bash
docker compose up --build
```

Services:
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

## API Quick Reference

- `POST /jobs`
  - Multipart form-data: `file` (CSV)
  - Returns: `{ "id": "<job-uuid>" }`

- `POST /jobs/{id}/start`
  - Starts asynchronous processing
  - Rejects if job is currently running

- `GET /jobs/{id}`
  - Returns live counters and progress

- `GET /jobs/{id}/transactions?page=1&page_size=20&filter=all`
  - `filter` in: `all | valid | invalid | suspicious`

## Design Decisions

- Threaded background execution keeps API responsive without external queue dependency.
- Progress and counters are persisted in DB, not memory, for reliable polling.
- Batch commits ensure partial progress is durable and reduce memory pressure.
- Invalid records are stored with raw values and error reasons to support debugging.
- Indexes are defined on common query dimensions (`job_id`, validity, suspicious flag).

## Assumptions

- Input files are UTF-8 encoded CSV files with header row.
- Duplicate transaction IDs are only scoped within the same job.
- Restart is blocked only while a job is running; failed/pending jobs can be re-run.
- Authentication and authorization are out of scope by requirement.
