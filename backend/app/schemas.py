import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class JobCreateResponse(BaseModel):
    id: uuid.UUID


class JobStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    total_records: int
    processed_records: int
    valid_records: int
    invalid_records: int
    progress_percent: int
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class TransactionResponse(BaseModel):
    id: int
    transaction_id: str | None
    user_id: str | None
    amount: float | None
    timestamp: datetime | None
    transaction_id_raw: str
    user_id_raw: str
    amount_raw: str
    timestamp_raw: str
    is_valid: bool
    is_suspicious: bool
    error_reasons: list[str]


class TransactionListResponse(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int
    items: list[TransactionResponse]


TransactionFilter = Literal["all", "valid", "invalid", "suspicious"]


class TransactionsQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
    filter: TransactionFilter = "all"
