# Batch Processing System

This project lets you upload a CSV file of transactions, process it in batches, and view results in a web UI.

## What This App Does

- Upload a CSV file with transactions
- Process records in the background in fixed-size batches
- Track job progress live
- Mark records as valid, invalid, or suspicious
- Browse results with pagination and filters

## Tech Used

- Backend: FastAPI + SQLAlchemy
- Frontend: React (Vite)
- Database: PostgreSQL

## Validation Rules

Each row is checked using these rules.

Required fields:
- `transaction_id`
- `user_id`
- `amount`
- `timestamp`

Format rules:
- `transaction_id` must be a valid GUID
- `user_id` must be a valid GUID
- `amount` must be numeric
- `timestamp` must be valid ISO-8601 datetime
- `transaction_id` must be unique inside the same job

Suspicious rules:
- amount is less than 0
- amount is greater than 50,000

Optional user check:
- if `REQUIRE_USER_EXISTS=true`, `user_id` must exist in the `users` table

## Main Files

- `backend/app/main.py`: app startup
- `backend/app/api/jobs.py`: API endpoints
- `backend/app/models.py`: DB models
- `backend/app/services/processor.py`: batch processing logic
- `frontend/src/App.jsx`: frontend screen
- `scripts/init_db.sql`: optional SQL seed for users
- `sample_transactions.csv`: sample input file

## Run Locally (Without Docker)

### 1. Start PostgreSQL

Create a database named `batch_processing`.

### 2. Start Backend

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

If running from project root:

```bash
python -m uvicorn app.main:app --reload --port 8000 --app-dir backend
```

Optional: seed users for user-exists validation tests:

```bash
psql -U postgres -d batch_processing -f ../scripts/init_db.sql
```

### 3. Start Frontend

```bash
cd frontend
npm install
npm run dev
```

Open: `http://localhost:5173`

## Run With Docker

From project root:

```bash
docker compose up --build
```

Services:
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- PostgreSQL: `localhost:5432`

## API Endpoints

### Create Job

- `POST /jobs`
- Body: multipart form-data with file field `file`
- Returns: job id

### Start Job

- `POST /jobs/{id}/start`
- Starts async processing for uploaded file

### Job Status

- `GET /jobs/{id}`
- Returns progress and counters

### Transactions List

- `GET /jobs/{id}/transactions?page=1&page_size=20&filter=all`
- Filters: `all`, `valid`, `invalid`, `suspicious`

## Notes

- Processing runs in a background thread so API stays responsive
- Batches are committed incrementally, so progress is not lost if a large file is being processed
- Invalid rows are stored with error details for debugging
