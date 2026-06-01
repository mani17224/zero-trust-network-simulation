"""
routes.py — Data Service routes: GET/POST /records, DELETE /records/{id}.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from models import CreateRecordRequest, DeleteResponse, PaginatedRecords, Record
from auth import verify_client_cn

router = APIRouter()

# In-memory data store (replace with real DB in production)
_RECORDS: Dict[str, Record] = {}


def _seed_records() -> None:
    """Pre-populate some demo records."""
    demo = [
        ("Network policy config", "WireGuard VPN settings for all nodes", ["network", "config"]),
        ("TLS certificate inventory", "List of all issued mTLS certificates", ["security", "certs"]),
        ("OPA policy snapshot", "Rego policy rules as of last deploy", ["policy", "opa"]),
        ("Audit log archive", "Compressed audit logs from last 30 days", ["logs", "audit"]),
        ("Service mesh topology", "Current service-to-service communication map", ["topology"]),
    ]
    for title, content, tags in demo:
        rec_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        _RECORDS[rec_id] = Record(
            id=rec_id,
            title=title,
            content=content,
            owner="system",
            created_at=now,
            tags=tags,
        )


_seed_records()


@router.get(
    "/records",
    response_model=PaginatedRecords,
    summary="List records (paginated)",
)
async def list_records(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Records per page"),
    client_cn: str = Depends(verify_client_cn),
) -> PaginatedRecords:
    """
    Return a paginated list of data records.

    Requires reader or higher role (enforced by OPA at gateway).

    Args:
        page:       Page number (1-indexed).
        page_size:  Number of records per page.
        client_cn:  Verified caller CN.

    Returns:
        PaginatedRecords with records and pagination metadata.
    """
    all_records = list(_RECORDS.values())
    total = len(all_records)
    start = (page - 1) * page_size
    end = start + page_size
    page_records = all_records[start:end]

    return PaginatedRecords(
        records=page_records,
        total=total,
        page=page,
        page_size=page_size,
        has_next=end < total,
    )


@router.post(
    "/records",
    response_model=Record,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new record",
)
async def create_record(
    body: CreateRecordRequest,
    request: Request,
    client_cn: str = Depends(verify_client_cn),
) -> Record:
    """
    Create and store a new data record.

    Requires writer or higher role (enforced by OPA at gateway).

    Args:
        body:       Record data.
        request:    Incoming request (for owner extraction).
        client_cn:  Verified caller CN.

    Returns:
        The newly created Record.
    """
    rec_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    # Use X-Subject header to record who created this
    owner = request.headers.get("X-Subject", client_cn.split(".")[0])

    record = Record(
        id=rec_id,
        title=body.title,
        content=body.content,
        owner=owner,
        created_at=now,
        tags=body.tags,
    )
    _RECORDS[rec_id] = record
    return record


@router.delete(
    "/records/{record_id}",
    response_model=DeleteResponse,
    summary="Delete a record by ID",
)
async def delete_record(
    record_id: str,
    request: Request,
    client_cn: str = Depends(verify_client_cn),
) -> DeleteResponse:
    """
    Delete a record by its ID.

    Requires admin role (enforced by OPA at gateway).

    Args:
        record_id:  The UUID of the record to delete.
        client_cn:  Verified caller CN.

    Returns:
        DeleteResponse confirming deletion.

    Raises:
        HTTPException 404: If record not found.
    """
    if record_id not in _RECORDS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": f"Record '{record_id}' not found"},
        )

    del _RECORDS[record_id]

    return DeleteResponse(
        deleted=True,
        record_id=record_id,
        message=f"Record {record_id} deleted successfully",
    )
