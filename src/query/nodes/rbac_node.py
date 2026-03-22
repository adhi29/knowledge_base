"""Node 2: RBACNode — Role-based access pre-check before retrieval."""
from src.query.state import QueryState
from src.storage.database import _get_allowed_sensitivity

VALID_ROLES = {"analyst", "operations", "compliance", "admin"}


def rbac_node(state: QueryState) -> QueryState:
    """
    Verifies the user has a known, active role and determines
    which sensitivity levels they can access. Blocks the query
    early if the role is unknown.
    """
    role = state.user_role.lower()

    if role not in VALID_ROLES:
        return state.model_copy(update={
            "rbac_passed": False,
            "error": f"Unknown role '{role}'. Access denied.",
        })

    allowed = _get_allowed_sensitivity(role)
    if not allowed:
        return state.model_copy(update={
            "rbac_passed": False,
            "error": "No access permissions configured for your role.",
        })

    return state.model_copy(update={"rbac_passed": True})
