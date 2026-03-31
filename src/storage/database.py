"""SQLite metadata, RBAC, audit log, and user session store."""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
import hashlib

from src.config import settings


def get_connection() -> sqlite3.Connection:
    Path(settings.sqlite_db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.sqlite_db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    cur = conn.cursor()

    # Document chunks metadata
    cur.execute("""
        CREATE TABLE IF NOT EXISTS text_chunks (
            chunk_id     TEXT PRIMARY KEY,
            source_id    TEXT NOT NULL,
            source_type  TEXT NOT NULL,
            source_name  TEXT NOT NULL,
            source_path  TEXT,
            content_hash TEXT NOT NULL,
            chunk_index  INTEGER,
            page_number  INTEGER,
            section      TEXT,
            allowed_roles TEXT NOT NULL DEFAULT '["analyst","compliance","operations","admin"]',
            sensitivity_level TEXT NOT NULL DEFAULT 'internal',
            is_active    INTEGER NOT NULL DEFAULT 1,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        )
    """)

    # Table records (from parsed tables)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS table_records (
            record_id    TEXT PRIMARY KEY,
            source_id    TEXT NOT NULL,
            source_name  TEXT NOT NULL,
            table_index  INTEGER,
            markdown_content TEXT,
            summary      TEXT,
            allowed_roles TEXT NOT NULL DEFAULT '["analyst","compliance","operations","admin"]',
            created_at   TEXT NOT NULL
        )
    """)

    # Users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id      TEXT PRIMARY KEY,
            username     TEXT UNIQUE NOT NULL,
            hashed_password TEXT NOT NULL,
            role         TEXT NOT NULL DEFAULT 'analyst',
            department   TEXT,
            is_active    INTEGER NOT NULL DEFAULT 1,
            created_at   TEXT NOT NULL
        )
    """)

    # Role permissions matrix
    cur.execute("""
        CREATE TABLE IF NOT EXISTS role_permissions (
            role             TEXT NOT NULL,
            sensitivity_level TEXT NOT NULL,
            can_access       INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (role, sensitivity_level)
        )
    """)

    # User sessions
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_id   TEXT PRIMARY KEY,
            user_id      TEXT NOT NULL,
            started_at   TEXT NOT NULL,
            last_active  TEXT NOT NULL,
            is_active    INTEGER NOT NULL DEFAULT 1
        )
    """)

    # Audit logs — append-only
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            log_id           TEXT PRIMARY KEY,
            session_id       TEXT,
            user_id          TEXT NOT NULL,
            query            TEXT NOT NULL,
            query_type       TEXT,
            retrieved_chunks TEXT,
            response_summary TEXT,
            latency_ms       INTEGER,
            timestamp        TEXT NOT NULL
        )
    """)

    # Ingestion log
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ingestion_log (
            log_id       TEXT PRIMARY KEY,
            source_path  TEXT NOT NULL,
            source_type  TEXT NOT NULL,
            status       TEXT NOT NULL,
            chunks_created INTEGER DEFAULT 0,
            error_message TEXT,
            processed_at TEXT NOT NULL
        )
    """)

    # Connector sync state — tracks last sync per source for incremental sync
    cur.execute("""
        CREATE TABLE IF NOT EXISTS connector_sync_state (
            source_key   TEXT PRIMARY KEY,   -- e.g. "confluence:OPS"
            source_type  TEXT NOT NULL,
            last_synced  TEXT,               -- ISO timestamp of last successful sync
            docs_synced  INTEGER DEFAULT 0,
            status       TEXT DEFAULT 'never'
        )
    """)

    # Persistent Chat History
    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            session_id   TEXT PRIMARY KEY,
            user_id      TEXT NOT NULL,
            title        TEXT NOT NULL,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            message_id   TEXT PRIMARY KEY,
            session_id   TEXT NOT NULL,
            role         TEXT NOT NULL,      -- 'user' | 'assistant'
            content      TEXT NOT NULL,
            metadata     TEXT,               -- JSON: citations, etc.
            timestamp    TEXT NOT NULL
        )
    """)

    # Seed role permissions
    role_permissions = [
        ("analyst",    "public",        1),
        ("analyst",    "internal",      1),
        ("analyst",    "confidential",  0),
        ("analyst",    "restricted",    0),
        ("operations", "public",        1),
        ("operations", "internal",      1),
        ("operations", "confidential",  1),
        ("operations", "restricted",    0),
        ("compliance", "public",        1),
        ("compliance", "internal",      1),
        ("compliance", "confidential",  1),
        ("compliance", "restricted",    1),
        ("admin",      "public",        1),
        ("admin",      "internal",      1),
        ("admin",      "confidential",  1),
        ("admin",      "restricted",    1),
    ]
    cur.executemany(
        "INSERT OR IGNORE INTO role_permissions VALUES (?, ?, ?)",
        role_permissions,
    )

    conn.commit()
    conn.close()


# ── Chunk metadata ─────────────────────────────────────────────────────────────

def upsert_chunk_metadata(
    chunk_id: str,
    source_id: str,
    source_type: str,
    source_name: str,
    source_path: str,
    content_hash: str,
    chunk_index: int,
    allowed_roles: list[str],
    sensitivity_level: str = "internal",
    page_number: Optional[int] = None,
    section: Optional[str] = None,
):
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO text_chunks
            (chunk_id, source_id, source_type, source_name, source_path,
             content_hash, chunk_index, page_number, section,
             allowed_roles, sensitivity_level, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(chunk_id) DO UPDATE SET
            content_hash=excluded.content_hash,
            updated_at=excluded.updated_at,
            is_active=1
    """, (chunk_id, source_id, source_type, source_name, source_path,
          content_hash, chunk_index, page_number, section,
          json.dumps(allowed_roles), sensitivity_level, now, now))
    conn.commit()
    conn.close()


def get_chunk_metadata(chunk_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM text_chunks WHERE chunk_id=?", (chunk_id,)
    ).fetchone()
    conn.close()
    if row:
        d = dict(row)
        d["allowed_roles"] = json.loads(d["allowed_roles"])
        return d
    return None


def get_chunks_for_rbac(chunk_ids: list[str], user_role: str) -> list[str]:
    """Return only chunk_ids the user's role may access."""
    if not chunk_ids:
        return []
    conn = get_connection()
    placeholders = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f"SELECT chunk_id, sensitivity_level FROM text_chunks WHERE chunk_id IN ({placeholders})",
        chunk_ids,
    ).fetchall()
    conn.close()

    allowed_levels = _get_allowed_sensitivity(user_role, conn_reuse=False)
    return [r["chunk_id"] for r in rows if r["sensitivity_level"] in allowed_levels]


def _get_allowed_sensitivity(role: str, conn_reuse: bool = True) -> set[str]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT sensitivity_level FROM role_permissions WHERE role=? AND can_access=1",
        (role,)
    ).fetchall()
    conn.close()
    return {r["sensitivity_level"] for r in rows}


def hash_exists(content_hash: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM text_chunks WHERE content_hash=? AND is_active=1",
        (content_hash,)
    ).fetchone()
    conn.close()
    return row is not None


# ── Users ──────────────────────────────────────────────────────────────────────

def create_user(user_id: str, username: str, hashed_password: str,
                role: str = "analyst", department: Optional[str] = None):
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    try:
        conn.execute("""
            INSERT INTO users (user_id, username, hashed_password, role, department, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?)
        """, (user_id, username, hashed_password, role, department, now))
        conn.commit()
    finally:
        conn.close()


def get_user_by_username(username: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username=? AND is_active=1", (username,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE user_id=? AND is_active=1", (user_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Audit log ─────────────────────────────────────────────────────────────────

def write_audit_log(
    log_id: str,
    user_id: str,
    query: str,
    query_type: str,
    retrieved_chunk_ids: list[str],
    response_summary: str,
    latency_ms: int,
    session_id: Optional[str] = None,
):
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO audit_logs
            (log_id, session_id, user_id, query, query_type,
             retrieved_chunks, response_summary, latency_ms, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (log_id, session_id, user_id, query, query_type,
          json.dumps(retrieved_chunk_ids), response_summary, latency_ms, now))
    conn.commit()
    conn.close()


def get_audit_logs(user_id: Optional[str] = None, limit: int = 100) -> list[dict]:
    conn = get_connection()
    if user_id:
        rows = conn.execute(
            "SELECT * FROM audit_logs WHERE user_id=? ORDER BY timestamp DESC LIMIT ?",
            (user_id, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Ingestion log ──────────────────────────────────────────────────────────────

def write_ingestion_log(
    log_id: str, source_path: str, source_type: str,
    status: str, chunks_created: int = 0, error_message: Optional[str] = None
):
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO ingestion_log
            (log_id, source_path, source_type, status, chunks_created, error_message, processed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (log_id, source_path, source_type, status, chunks_created, error_message, now))
    conn.commit()
    conn.close()


def get_ingestion_status(limit: int = 50) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM ingestion_log ORDER BY processed_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Connector sync state (incremental sync) ───────────────────────────────────

def get_connector_sync_state(source_key: str) -> Optional[dict]:
    """Return the last sync state for a source key (e.g. 'confluence:OPS')."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM connector_sync_state WHERE source_key=?", (source_key,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def set_connector_sync_state(
    source_key: str,
    source_type: str,
    docs_synced: int = 0,
    status: str = "success",
):
    """Update/insert sync state after a successful connector run."""
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO connector_sync_state (source_key, source_type, last_synced, docs_synced, status)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(source_key) DO UPDATE SET
            last_synced=excluded.last_synced,
            docs_synced=excluded.docs_synced,
            status=excluded.status
    """, (source_key, source_type, now, docs_synced, status))
    conn.commit()
    conn.close()


def get_all_sync_states() -> list[dict]:
    """Return sync state for all registered connectors."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM connector_sync_state ORDER BY last_synced DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Chat History ─────────────────────────────────────────────────────────────

def create_chat_session(session_id: str, user_id: str, title: str):
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO chat_sessions (session_id, user_id, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, user_id, title, now, now))
    conn.commit()
    conn.close()


def get_user_chat_sessions(user_id: str, limit: int = 50) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM chat_sessions 
        WHERE user_id=? 
        ORDER BY updated_at DESC LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_chat_messages(session_id: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM chat_messages 
        WHERE session_id=? 
        ORDER BY timestamp ASC
    """, (session_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def write_chat_message(
    message_id: str, session_id: str, role: str, 
    content: str, metadata: Optional[dict] = None
):
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT INTO chat_messages (message_id, session_id, role, content, metadata, timestamp)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (message_id, session_id, role, content, json.dumps(metadata), now))
    
    # Update session timestamp
    conn.execute("UPDATE chat_sessions SET updated_at=? WHERE session_id=?", (now, session_id))
    
    conn.commit()
    conn.close()


def delete_chat_session(session_id: str, user_id: str):
    conn = get_connection()
    # Check ownership
    conn.execute("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
    conn.execute("DELETE FROM chat_sessions WHERE session_id=? AND user_id=?", (session_id, user_id))
    conn.commit()
    conn.close()


def rename_chat_session(session_id: str, user_id: str, new_title: str):
    conn = get_connection()
    conn.execute("""
        UPDATE chat_sessions SET title=? 
        WHERE session_id=? AND user_id=?
    """, (new_title, session_id, user_id))
    conn.commit()
    conn.close()
