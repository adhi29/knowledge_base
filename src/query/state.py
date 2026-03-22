"""Shared LangGraph pipeline state definition."""
from typing import Optional, Annotated
from pydantic import BaseModel, Field


class QueryState(BaseModel):
    """State object passed through all LangGraph nodes."""

    # ── Input ──────────────────────────────────────────────────────────────────
    query: str = ""
    user_id: str = ""
    username: str = ""
    user_role: str = ""
    session_id: str = ""
    chat_history: list[dict] = Field(default_factory=list)  # [{role, content}]

    # ── Auth / RBAC ────────────────────────────────────────────────────────────
    auth_valid: bool = False
    auth_error: Optional[str] = None
    rbac_passed: bool = False

    # ── Classification & Routing ───────────────────────────────────────────────
    query_type: str = ""        # factual | procedural | policy | exception | general
    rewritten_queries: list[str] = Field(default_factory=list)

    # ── Retrieval ──────────────────────────────────────────────────────────────
    raw_results: list[dict] = Field(default_factory=list)       # from HybridSearch
    filtered_results: list[dict] = Field(default_factory=list)  # after RBAC filter
    reranked_results: list[dict] = Field(default_factory=list)  # after ReRanker
    context_window: str = ""                                    # assembled context

    # ── Generation ────────────────────────────────────────────────────────────
    response: str = ""
    citations: list[dict] = Field(default_factory=list)         # [{source, page, chunk_id}]
    confidence: float = 0.0

    # ── Error handling ─────────────────────────────────────────────────────────
    error: Optional[str] = None
    no_results: bool = False

    # ── Timing ────────────────────────────────────────────────────────────────
    start_time_ms: float = 0.0
    end_time_ms: float = 0.0

    class Config:
        arbitrary_types_allowed = True
