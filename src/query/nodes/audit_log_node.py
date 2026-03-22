"""Node 11: AuditLogNode — Append-only audit log write to SQLite."""
import time
import uuid
from src.query.state import QueryState
from src.storage.database import write_audit_log


def audit_log_node(state: QueryState) -> QueryState:
    """
    Writes an append-only audit record for every query interaction.
    Records: user, query, query_type, retrieved chunks, response summary, latency.
    """
    try:
        latency_ms = int((state.end_time_ms - state.start_time_ms) * 1000) if state.end_time_ms else 0
        chunk_ids = [c.get("chunk_id", "") for c in state.reranked_results]
        response_summary = (state.response or "")[:500]  # Truncate for storage

        write_audit_log(
            log_id=str(uuid.uuid4()),
            user_id=state.user_id,
            query=state.query,
            query_type=state.query_type,
            retrieved_chunk_ids=chunk_ids,
            response_summary=response_summary,
            latency_ms=latency_ms,
            session_id=state.session_id,
        )
    except Exception as e:
        # Audit log failures must never break the user-facing response
        print(f"[AuditLogNode] Warning: failed to write audit log: {e}")

    return state
