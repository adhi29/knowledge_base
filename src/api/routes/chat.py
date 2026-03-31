"""Chat endpoint — runs the full LangGraph query pipeline."""
import uuid
import time
from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import get_current_user, TokenData
from src.api.models import ChatRequest, ChatResponse, CitationItem
from src.query.graph import run_query
from src.storage.database import (
    create_chat_session, write_chat_message, get_user_chat_sessions
)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
def chat(req: ChatRequest, current_user: TokenData = Depends(get_current_user)):
    session_id = req.session_id or str(uuid.uuid4())

    # ── Check/Create Persistent Session ──────────────────────────────────────
    user_sessions = get_user_chat_sessions(current_user.user_id, limit=1000)
    session_exists = any(s["session_id"] == session_id for s in user_sessions)

    if not session_exists:
        title = req.query[:50] + ("..." if len(req.query) > 50 else "")
        create_chat_session(session_id, current_user.user_id, title)

    # Save User Message
    write_chat_message(
        message_id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content=req.query
    )

    history = [{"role": m.role, "content": m.content} for m in req.chat_history]

    # ── Wall-clock latency ────────────────────────────────────────────────────
    t_start = time.time()

    # graph.invoke() returns a plain dict, not a QueryState object
    result: dict = run_query(
        query=req.query,
        user_id=current_user.user_id,
        user_role=current_user.role,
        session_id=session_id,
        chat_history=history,
    )

    latency_ms = int((time.time() - t_start) * 1000)

    # ── Surface auth errors ───────────────────────────────────────────────────
    if not result.get("auth_valid", True) and result.get("auth_error"):
        raise HTTPException(status_code=401, detail=result["auth_error"])

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

    # Save Assistant Message with all metadata
    assistant_content = result.get("response", "")
    if assistant_content:
        write_chat_message(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role="assistant",
            content=assistant_content,
            metadata={
                "citations": [c.dict() for c in citations],
                "query_type": result.get("query_type"),
                "confidence": result.get("confidence"),
                "latency_ms": latency_ms
            }
        )

    return ChatResponse(
        response=result.get("response", ""),
        citations=citations,
        query_type=result.get("query_type", "general"),
        confidence=result.get("confidence", 0.0),
        latency_ms=latency_ms,
        session_id=session_id,
    )
