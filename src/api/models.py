"""Pydantic request/response models for the API."""
from typing import Optional
from pydantic import BaseModel, Field


# ── Auth ───────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str = Field(..., min_length=8)
    role: str = "analyst"
    department: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str
    role: str


# ── Chat ───────────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str   # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    chat_history: list[ChatMessage] = Field(default_factory=list)


class CitationItem(BaseModel):
    index: int
    source_name: str
    source_type: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    chunk_id: str
    relevance_score: Optional[float] = None


class ChatResponse(BaseModel):
    response: str
    citations: list[CitationItem]
    query_type: str
    confidence: float
    latency_ms: int
    session_id: str


# ── Admin ──────────────────────────────────────────────────────────────────────

class IngestRequest(BaseModel):
    path: str
    allowed_roles: Optional[list[str]] = None
    sensitivity_level: str = "internal"
    recursive: bool = True


class IngestResponse(BaseModel):
    documents_processed: int
    chunks_created: int
    chunks_skipped: int
    errors: list[str]


class SyncRequest(BaseModel):
    """Request body for POST /api/admin/sync/{source}"""
    # Confluence
    space_key: Optional[str] = None          # e.g. "OPS"
    # Jira
    project_key: Optional[str] = None        # e.g. "BANK"
    jql: Optional[str] = None               # override default JQL
    # Outlook
    mailbox: Optional[str] = None           # override MS_MAILBOX
    folder: str = "Inbox"
    # SharePoint
    site_id: Optional[str] = None
    drive_id: Optional[str] = None
    folder_path: str = "root"
    # Common
    sensitivity_level: str = "internal"
    allowed_roles: Optional[list[str]] = None
    max_items: int = 500


class AuditLogEntry(BaseModel):
    log_id: str
    user_id: str
    query: str
    query_type: Optional[str]
    latency_ms: Optional[int]
    timestamp: str


class IngestionStatus(BaseModel):
    log_id: str
    source_path: str
    source_type: str
    status: str
    chunks_created: int
    processed_at: str
