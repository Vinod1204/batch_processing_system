import csv
import threading
import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dateutil import parser
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import SessionLocal
from app.models import Job, JobStatus, Transaction, User

running_jobs_lock = threading.Lock()
running_jobs: set[uuid.UUID] = set()


class CSVValidationError(Exception):
    pass


def _parse_uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value)


def _parse_amount(value: str) -> Decimal:
    return Decimal(value)


def _parse_timestamp(value: str) -> datetime:
    return parser.isoparse(value)


def _validate_row(row: dict[str, str], seen_transaction_ids: set[uuid.UUID], db: Session) -> dict:
    required_fields = ["transaction_id", "user_id", "amount", "timestamp"]
    errors: list[str] = []

    normalized = {key: (row.get(key) or "").strip() for key in required_fields}

    for field in required_fields:
        if not normalized[field]:
            errors.append(f"Missing required field: {field}")

    parsed_transaction_id = None
    parsed_user_id = None
    parsed_amount = None
    parsed_timestamp = None

    if normalized["transaction_id"]:
        try:
            parsed_transaction_id = _parse_uuid(normalized["transaction_id"])
            if parsed_transaction_id in seen_transaction_ids:
                errors.append("Duplicate transaction_id in this job")
                parsed_transaction_id = None
            else:
                seen_transaction_ids.add(parsed_transaction_id)
        except ValueError:
            errors.append("transaction_id must be a valid GUID")

    if normalized["user_id"]:
        try:
            parsed_user_id = _parse_uuid(normalized["user_id"])
        except ValueError:
            errors.append("user_id must be a valid GUID")

    if normalized["amount"]:
        try:
            parsed_amount = _parse_amount(normalized["amount"])
        except (InvalidOperation, ValueError):
            errors.append("amount must be numeric")

    if normalized["timestamp"]:
        try:
            parsed_timestamp = _parse_timestamp(normalized["timestamp"])
        except (ValueError, TypeError):
            errors.append("timestamp must be valid ISO 8601")

    if settings.require_user_exists and parsed_user_id:
        user_exists = db.execute(select(User.id).where(User.id == parsed_user_id)).scalar_one_or_none()
        if user_exists is None:
            errors.append("user_id does not exist in users table")

    suspicious = False
    if parsed_amount is not None and (parsed_amount < 0 or parsed_amount > 50000):
        suspicious = True

    return {
        "is_valid": len(errors) == 0,
        "is_suspicious": suspicious,
        "errors": errors,
        "transaction_id": parsed_transaction_id,
        "user_id": parsed_user_id,
        "amount": parsed_amount,
        "timestamp": parsed_timestamp,
        "raw": normalized,
    }


def start_job_processing(job_id: uuid.UUID) -> None:
    with running_jobs_lock:
        if job_id in running_jobs:
            raise CSVValidationError("Job is already running")
        running_jobs.add(job_id)

    thread = threading.Thread(target=_process_job, args=(job_id,), daemon=True)
    thread.start()


def _process_job(job_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        job = db.get(Job, job_id)
        if not job:
            return

        file_path = Path(job.file_path)
        if not file_path.exists():
            job.status = JobStatus.failed.value
            job.error_message = f"Uploaded file not found: {file_path}"
            job.completed_at = datetime.utcnow()
            db.commit()
            return

        with file_path.open("r", newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            headers = set(reader.fieldnames or [])
            expected = {"transaction_id", "user_id", "amount", "timestamp"}
            if not expected.issubset(headers):
                missing = ", ".join(sorted(expected.difference(headers)))
                raise CSVValidationError(f"CSV is missing required columns: {missing}")

        with file_path.open("r", newline="", encoding="utf-8") as source:
            total_records = sum(1 for _ in csv.DictReader(source))

        job.total_records = total_records
        db.commit()

        seen_transaction_ids: set[uuid.UUID] = set()

        with file_path.open("r", newline="", encoding="utf-8") as source:
            reader = csv.DictReader(source)
            batch: list[Transaction] = []
            processed_in_batch = 0
            valid_in_batch = 0
            invalid_in_batch = 0

            for row in reader:
                result = _validate_row(row, seen_transaction_ids, db)
                txn = Transaction(
                    job_id=job.id,
                    transaction_id_raw=result["raw"]["transaction_id"],
                    user_id_raw=result["raw"]["user_id"],
                    amount_raw=result["raw"]["amount"],
                    timestamp_raw=result["raw"]["timestamp"],
                    transaction_id=result["transaction_id"],
                    user_id=result["user_id"],
                    amount=result["amount"],
                    timestamp=result["timestamp"],
                    is_valid=result["is_valid"],
                    is_suspicious=result["is_suspicious"],
                    error_reasons=result["errors"],
                )
                batch.append(txn)
                processed_in_batch += 1
                if result["is_valid"]:
                    valid_in_batch += 1
                else:
                    invalid_in_batch += 1

                if len(batch) >= settings.batch_size:
                    _commit_batch(db, job.id, batch, processed_in_batch, valid_in_batch, invalid_in_batch)
                    batch = []
                    processed_in_batch = 0
                    valid_in_batch = 0
                    invalid_in_batch = 0

            if batch:
                _commit_batch(db, job.id, batch, processed_in_batch, valid_in_batch, invalid_in_batch)

        refreshed_job = db.get(Job, job_id)
        if refreshed_job:
            refreshed_job.status = JobStatus.completed.value
            refreshed_job.progress_percent = 100
            refreshed_job.completed_at = datetime.utcnow()
            db.commit()

    except Exception as ex:
        db.rollback()
        failed_job = db.get(Job, job_id)
        if failed_job:
            failed_job.status = JobStatus.failed.value
            failed_job.error_message = str(ex)
            failed_job.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()
        with running_jobs_lock:
            running_jobs.discard(job_id)


def _commit_batch(
    db: Session,
    job_id: uuid.UUID,
    batch: list[Transaction],
    processed_in_batch: int,
    valid_in_batch: int,
    invalid_in_batch: int,
) -> None:
    db.add_all(batch)

    job = db.get(Job, job_id)
    if not job:
        return

    job.processed_records += processed_in_batch
    job.valid_records += valid_in_batch
    job.invalid_records += invalid_in_batch

    if job.total_records > 0:
        job.progress_percent = int((job.processed_records / job.total_records) * 100)

    db.commit()
