"""
models.py — Pydantic models for Service B (Data Service).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class Record(BaseModel):
    """A data record stored by Service B."""
    id: str = Field(..., description="Unique record identifier")
    title: str = Field(..., description="Record title")
    content: str = Field(..., description="Record content/payload")
    owner: str = Field(..., description="Owning service or user")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(default=None, description="Last update timestamp")
    tags: List[str] = Field(default_factory=list, description="Classification tags")


class CreateRecordRequest(BaseModel):
    """Request body for creating a new record."""
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    tags: List[str] = Field(default_factory=list)


class PaginatedRecords(BaseModel):
    """Paginated list of records."""
    records: List[Record]
    total: int
    page: int
    page_size: int
    has_next: bool


class DeleteResponse(BaseModel):
    """Response after deleting a record."""
    deleted: bool
    record_id: str
    message: str
