import os
import shutil
import uuid
from datetime import datetime
from math import ceil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db import get_db
from app.models import Job, JobStatus, Transaction
from app.schemas import JobCreateResponse, JobStatusResponse, TransactionListResponse, TransactionResponse
from app.services.processor import CSVValidationError, running_jobs, running_jobs_lock, start_job_processing

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _to_job_status_response(job: Job) -> JobStatusResponse:
    return JobStatusResponse(
        id=job.id,
        status=job.status,
        total_records=job.total_records,
        processed_records=job.processed_records,
        valid_records=job.valid_records,
        invalid_records=job.invalid_records,
        progress_percent=job.progress_percent,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


@router.post("", response_model=JobCreateResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    file: UploadFile | None = File(None),
    csv_file: UploadFile | None = File(None),
    upload: UploadFile | None = File(None),
    db: Session = Depends(get_db),
) -> JobCreateResponse:
    incoming_file = file or csv_file or upload
    if incoming_file is None:
        raise HTTPException(status_code=400, detail="Missing file upload. Use multipart/form-data key 'file'.")

    if not incoming_file.filename or not incoming_file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are supported")

    job_id = uuid.uuid4()
    upload_dir = Path(settings.upload_dir)
    os.makedirs(upload_dir, exist_ok=True)

    destination = upload_dir / f"{job_id}.csv"
    with destination.open("wb") as target:
        shutil.copyfileobj(incoming_file.file, target)

    job = Job(
        id=job_id,
        filename=incoming_file.filename,
        file_path=str(destination.resolve()),
        status=JobStatus.pending.value,
    )

    db.add(job)
    db.commit()

    return JobCreateResponse(id=job.id)


@router.post("/{job_id}/start", response_model=JobStatusResponse)
def start_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == JobStatus.running.value:
        raise HTTPException(status_code=409, detail="Job is already running")

    with running_jobs_lock:
        if job_id in running_jobs:
            raise HTTPException(status_code=409, detail="Job is already running")

    job.status = JobStatus.running.value
    job.error_message = None
    job.started_at = datetime.utcnow()
    job.completed_at = None
    job.total_records = 0
    job.processed_records = 0
    job.valid_records = 0
    job.invalid_records = 0
    job.progress_percent = 0
    db.commit()
    db.refresh(job)

    try:
        start_job_processing(job_id)
    except CSVValidationError as ex:
        raise HTTPException(status_code=409, detail=str(ex)) from ex

    return _to_job_status_response(job)


@router.get("/{job_id}", response_model=JobStatusResponse)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)) -> JobStatusResponse:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return _to_job_status_response(job)


@router.get("/{job_id}/transactions", response_model=TransactionListResponse)
def get_transactions(
    job_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    filter: str = Query("all", pattern="^(all|valid|invalid|suspicious)$"),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    query = select(Transaction).where(Transaction.job_id == job_id)
    count_query = select(func.count(Transaction.id)).where(Transaction.job_id == job_id)

    if filter == "valid":
        query = query.where(Transaction.is_valid.is_(True))
        count_query = count_query.where(Transaction.is_valid.is_(True))
    elif filter == "invalid":
        query = query.where(Transaction.is_valid.is_(False))
        count_query = count_query.where(Transaction.is_valid.is_(False))
    elif filter == "suspicious":
        query = query.where(Transaction.is_suspicious.is_(True))
        count_query = count_query.where(Transaction.is_suspicious.is_(True))

    total_items = db.execute(count_query).scalar_one()

    query = query.order_by(Transaction.id).offset((page - 1) * page_size).limit(page_size)
    rows = db.execute(query).scalars().all()

    items = [
        TransactionResponse(
            id=row.id,
            transaction_id=str(row.transaction_id) if row.transaction_id else None,
            user_id=str(row.user_id) if row.user_id else None,
            amount=float(row.amount) if row.amount is not None else None,
            timestamp=row.timestamp,
            transaction_id_raw=row.transaction_id_raw,
            user_id_raw=row.user_id_raw,
            amount_raw=row.amount_raw,
            timestamp_raw=row.timestamp_raw,
            is_valid=row.is_valid,
            is_suspicious=row.is_suspicious,
            error_reasons=row.error_reasons,
        )
        for row in rows
    ]

    total_pages = max(1, ceil(total_items / page_size))
    return TransactionListResponse(
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
        items=items,
    )
