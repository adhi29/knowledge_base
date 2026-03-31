from fastapi import APIRouter, Depends, HTTPException

from src.api.auth import get_current_user, TokenData
from src.storage.database import (
    get_user_chat_sessions, get_chat_messages,
    delete_chat_session, rename_chat_session
)

router = APIRouter(prefix="/api/chat/history", tags=["Chat History"])


@router.get("/sessions")
def list_sessions(token: TokenData = Depends(get_current_user)):
    """List all chat sessions for the current user."""
    return get_user_chat_sessions(token.user_id)


@router.get("/sessions/{session_id}")
def get_session_messages(session_id: str, token: TokenData = Depends(get_current_user)):
    """Get all messages for a specific session. Ensures user ownership."""
    sessions = get_user_chat_sessions(token.user_id, limit=1000)
    if not any(s["session_id"] == session_id for s in sessions):
        raise HTTPException(status_code=403, detail="Access denied to this session")
    return get_chat_messages(session_id)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, token: TokenData = Depends(get_current_user)):
    """Delete a chat session and its messages."""
    delete_chat_session(session_id, token.user_id)
    return {"status": "success"}


@router.patch("/sessions/{session_id}")
def rename_session(session_id: str, title: str, token: TokenData = Depends(get_current_user)):
    """Rename a chat session."""
    rename_chat_session(session_id, token.user_id, title)
    return {"status": "success"}
