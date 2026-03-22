"""Admin endpoints: ingest documents, audit logs, ingestion status, stats."""
from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import require_role, TokenData
from src.api.models import IngestRequest, IngestResponse, AuditLogEntry, IngestionStatus
from src.ingestion.pipeline import ingest_directory, ingest_file
from src.storage.database import get_audit_logs, get_ingestion_status
from src.storage.vector_store import get_vector_store

router = APIRouter(prefix="/api/admin", tags=["Admin"])

admin_or_compliance = require_role("admin", "compliance")
admin_only = require_role("admin")


@router.post("/ingest", response_model=IngestResponse)
def ingest(
    req: IngestRequest,
    _: TokenData = Depends(admin_only),
):
    """Trigger ingestion for a local file or directory path."""
    import os
    path = req.path
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")

    if os.path.isfile(path):
        summary = ingest_file(path, req.allowed_roles, req.sensitivity_level)
    else:
        summary = ingest_directory(path, req.allowed_roles, req.sensitivity_level, req.recursive)

    return IngestResponse(
        documents_processed=summary["documents_processed"],
        chunks_created=summary["chunks_created"],
        chunks_skipped=summary["chunks_skipped"],
        errors=summary["errors"],
    )


@router.get("/audit-logs", response_model=list[AuditLogEntry])
def audit_logs(
    user_id: str = None,
    limit: int = 100,
    _: TokenData = Depends(admin_or_compliance),
):
    """View audit logs. Compliance and admin can filter by user_id."""
    logs = get_audit_logs(user_id=user_id, limit=limit)
    return [
        AuditLogEntry(
            log_id=l["log_id"],
            user_id=l["user_id"],
            query=l["query"],
            query_type=l.get("query_type"),
            latency_ms=l.get("latency_ms"),
            timestamp=l["timestamp"],
        )
        for l in logs
    ]


@router.get("/ingestion-status", response_model=list[IngestionStatus])
def ingestion_status(
    limit: int = 50,
    _: TokenData = Depends(admin_only),
):
    """View document ingestion history."""
    records = get_ingestion_status(limit=limit)
    return [
        IngestionStatus(
            log_id=r["log_id"],
            source_path=r["source_path"],
            source_type=r["source_type"],
            status=r["status"],
            chunks_created=r.get("chunks_created", 0),
            processed_at=r["processed_at"],
        )
        for r in records
    ]


@router.get("/stats")
def stats(_: TokenData = Depends(admin_only)):
    """System statistics."""
    vs = get_vector_store()
    return {
        "total_chunks_indexed": vs.total_chunks,
        "faiss_index_size": vs.index.ntotal,
    }
