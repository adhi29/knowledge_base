"""Chat endpoint — runs the full LangGraph query pipeline."""
import uuid
from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import get_current_user, TokenData
from src.api.models import ChatRequest, ChatResponse, CitationItem
from src.query.graph import run_query

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest, current_user: TokenData = Depends(get_current_user)):
    session_id = req.session_id or str(uuid.uuid4())

    history = [{"role": m.role, "content": m.content} for m in req.chat_history]

    result = run_query(
        query=req.query,
        user_id=current_user.user_id,
        user_role=current_user.role,
        session_id=session_id,
        chat_history=history,
    )

    # If auth or RBAC failed, surface as 403
    if not result.get("auth_valid", True) is False and result.get("auth_error"):
        raise HTTPException(status_code=401, detail=result["auth_error"])

    latency_ms = int(
        (result.get("end_time_ms", 0) - result.get("start_time_ms", 0)) * 1000
    )

    citations = [
        CitationItem(
            index=c["index"],
            source_name=c["source_name"],
            source_type=c.get("source_type", ""),
            page_number=c.get("page_number"),
            section=c.get("section"),
            chunk_id=c["chunk_id"],
            relevance_score=c.get("relevance_score"),
        )
        for c in (result.get("citations") or [])
    ]

    return ChatResponse(
        response=result.get("response", ""),
        citations=citations,
        query_type=result.get("query_type", "general"),
        confidence=result.get("confidence", 0.0),
        latency_ms=latency_ms,
        session_id=session_id,
    )
