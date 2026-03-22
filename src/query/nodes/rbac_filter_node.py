"""Node 6: RBAC Filter — Post-retrieval sensitivity filter."""
from src.query.state import QueryState
from src.storage.database import get_chunk_metadata, _get_allowed_sensitivity


def rbac_filter_node(state: QueryState) -> QueryState:
    """
    Filters retrieved chunks based on the user's role.
    Removes any chunk whose sensitivity_level the user is not permitted to see.
    """
    if state.error or not state.raw_results:
        return state.model_copy(update={"filtered_results": []})

    allowed_levels = _get_allowed_sensitivity(state.user_role)
    filtered = []

    for result in state.raw_results:
        chunk_id = result.get("chunk_id")
        if not chunk_id:
            continue

        meta = get_chunk_metadata(chunk_id)
        if meta is None:
            # Chunk exists in FAISS but not in DB (shouldn't happen) — skip
            continue

        if meta["sensitivity_level"] in allowed_levels and meta.get("is_active", 1):
            result_with_meta = {**result, **{
                "source_name": meta.get("source_name", result.get("source_name", "")),
                "source_type": meta.get("source_type", result.get("source_type", "")),
                "page_number": meta.get("page_number"),
                "section":     meta.get("section"),
                "sensitivity_level": meta["sensitivity_level"],
                "allowed_roles": meta["allowed_roles"],
            }}
            filtered.append(result_with_meta)

    if not filtered:
        return state.model_copy(update={
            "filtered_results": [],
            "no_results": True,
            "error": "No accessible documents found for your role and query.",
        })

    return state.model_copy(update={"filtered_results": filtered})
