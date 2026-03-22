"""Node 1: AuthNode — JWT token validation and user identity resolution."""
from src.query.state import QueryState
from src.storage.database import get_user_by_id


def auth_node(state: QueryState) -> QueryState:
    """
    Validates that user_id is present and corresponds to an active user.
    In the full system this validates a JWT token; here we trust the
    user_id / role already extracted by the FastAPI middleware.
    """
    if not state.user_id or not state.user_role:
        return state.model_copy(update={
            "auth_valid": False,
            "auth_error": "Missing user identity. Please log in.",
        })

    user = get_user_by_id(state.user_id)
    if not user:
        return state.model_copy(update={
            "auth_valid": False,
            "auth_error": f"User '{state.user_id}' not found or inactive.",
        })

    return state.model_copy(update={
        "auth_valid": True,
        "user_role": user["role"],       # Refresh role from DB (single source of truth)
        "username": user["username"],
    })
