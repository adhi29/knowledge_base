"""Node 5: HybridSearchNode — BM25 + Semantic search with RRF reranking."""
from src.query.state import QueryState
from src.storage.vector_store import get_vector_store
from src.config import settings


def hybrid_search_node(state: QueryState) -> QueryState:
    """
    Runs hybrid search (BM25 + Semantic) with RRF fusion for each
    rewritten query, then merges and deduplicates results.
    """
    if state.error or not state.rbac_passed:
        return state

    vs = get_vector_store()
    queries = state.rewritten_queries or [state.query]

    # Gather results from all query variants
    all_results: dict[str, dict] = {}  # chunk_id → best result

    for q in queries:
        results = vs.hybrid_search(q, top_k=settings.top_k_retrieval)
        for r in results:
            cid = r["chunk_id"]
            if cid not in all_results:
                all_results[cid] = r
            else:
                # Keep highest RRF score across query variants
                if r.get("rrf_score", 0) > all_results[cid].get("rrf_score", 0):
                    all_results[cid] = r

    # Sort by RRF score descending
    merged = sorted(all_results.values(), key=lambda x: x.get("rrf_score", 0), reverse=True)

    if not merged:
        return state.model_copy(update={
            "raw_results": [],
            "no_results": True,
        })

    return state.model_copy(update={
        "raw_results": merged,
        "no_results": False,
    })
