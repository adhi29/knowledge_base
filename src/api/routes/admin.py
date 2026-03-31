"""Admin endpoints: ingest documents, audit logs, ingestion status, stats."""
import httpx
from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import require_role, TokenData
from src.api.models import IngestRequest, IngestResponse, AuditLogEntry, IngestionStatus, SyncRequest
from src.ingestion.pipeline import ingest_directory, ingest_file, IngestionPipeline
from src.ingestion.connectors.live_connectors import (
    ConfluenceConnector, JiraConnector, OutlookConnector, SharePointConnector,
)
from src.storage.database import (
    get_audit_logs, get_ingestion_status, get_all_sync_states, set_connector_sync_state,
)
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


# ── Live connector sync ────────────────────────────────────────────────────────

_SOURCE_LABELS = {
    "confluence": "Confluence",
    "jira": "Jira",
    "outlook": "Outlook",
    "sharepoint": "SharePoint",
}


@router.post("/sync/{source}", response_model=IngestResponse)
def sync_live_source(
    source: str,
    req: SyncRequest,
    _: TokenData = Depends(admin_only),
):
    """
    Trigger a live sync from an enterprise source.

    source: one of  confluence | jira | outlook | sharepoint

    Credentials must be set in .env before calling.
    Returns 422 if any required env var is missing.
    """
    if source not in _SOURCE_LABELS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown source '{source}'. Choose from: {list(_SOURCE_LABELS)}",
        )

    # Build the appropriate connector
    try:
        if source == "confluence":
            if not req.space_key:
                raise HTTPException(status_code=422, detail="space_key is required for Confluence sync")
            connector = ConfluenceConnector(
                space_key=req.space_key,
                max_pages=req.max_items,
                allowed_roles=req.allowed_roles,
                sensitivity_level=req.sensitivity_level,
            )

        elif source == "jira":
            if not req.project_key:
                raise HTTPException(status_code=422, detail="project_key is required for Jira sync")
            connector = JiraConnector(
                project_key=req.project_key,
                jql=req.jql,
                max_issues=req.max_items,
                allowed_roles=req.allowed_roles,
                sensitivity_level=req.sensitivity_level,
            )

        elif source == "outlook":
            connector = OutlookConnector(
                mailbox=req.mailbox,
                folder=req.folder,
                max_messages=req.max_items,
                allowed_roles=req.allowed_roles,
                sensitivity_level=req.sensitivity_level,
            )

        elif source == "sharepoint":
            connector = SharePointConnector(
                site_id=req.site_id,
                drive_id=req.drive_id,
                folder_path=req.folder_path,
                allowed_roles=req.allowed_roles,
                sensitivity_level=req.sensitivity_level,
            )

    except ValueError as exc:
        # Missing credentials — give a clear 422 with the exact env vars needed
        raise HTTPException(status_code=422, detail=str(exc))

    # Run full ingestion pipeline with the live connector
    try:
        pipeline = IngestionPipeline(connectors=[connector])
        summary = pipeline.run()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"{_SOURCE_LABELS[source]} sync failed: {exc}",
        )

    # Persist sync state for incremental tracking
    from src.config import settings as _settings
    source_key = req.space_key or req.project_key or req.mailbox or req.folder_path or source
    set_connector_sync_state(
        source_key=f"{source}:{source_key}",
        source_type=source,
        docs_synced=summary["documents_processed"],
        status="success",
    )

    # Fire Slack webhook if configured
    slack_url = getattr(_settings, "slack_webhook_url", None)
    if slack_url:
        _notify_slack(
            slack_url,
            source=_SOURCE_LABELS[source],
            docs=summary["documents_processed"],
            chunks=summary["chunks_created"],
        )

    return IngestResponse(
        documents_processed=summary["documents_processed"],
        chunks_created=summary["chunks_created"],
        chunks_skipped=summary["chunks_skipped"],
        errors=summary["errors"],
    )


# ── Sync status ────────────────────────────────────────────────────────────────

@router.get("/sync-status")
def sync_status(_: TokenData = Depends(admin_only)):
    """Return last sync timestamp and doc count for all configured connectors."""
    return get_all_sync_states()


# ── Slack webhook helper ───────────────────────────────────────────────────────

def _notify_slack(webhook_url: str, source: str, docs: int, chunks: int):
    """Post a brief sync summary to a Slack incoming webhook (best-effort)."""
    try:
        payload = {
            "text": (
                f"✅ *{source} sync complete* — "
                f"{docs} docs ingested, {chunks} new chunks added to the knowledge base."
            )
        }
        httpx.post(webhook_url, json=payload, timeout=5)
    except Exception:
        pass  # Never let Slack failure break the main sync response

