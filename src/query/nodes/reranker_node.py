"""Node 7: ReRankerNode — Cross-encoder reranking using sentence-transformers."""
from src.query.state import QueryState
from src.config import settings

# Lazy-load the cross-encoder to avoid startup cost
_cross_encoder = None


def _get_cross_encoder():
    global _cross_encoder
    if _cross_encoder is None:
        from sentence_transformers import CrossEncoder
        # BGE reranker — free, local, no API cost
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _cross_encoder


def reranker_node(state: QueryState) -> QueryState:
    """
    Reranks the RBAC-filtered chunks using a cross-encoder model.
    Falls back to RRF order if reranker fails.
    """
    if state.error or not state.filtered_results:
        return state.model_copy(update={"reranked_results": []})

    candidates = state.filtered_results[: settings.top_k_retrieval]
    query = state.query

    try:
        encoder = _get_cross_encoder()
        pairs = [(query, c["text"]) for c in candidates]
        scores = encoder.predict(pairs)

        scored = list(zip(scores, candidates))
        scored.sort(key=lambda x: x[0], reverse=True)

        reranked = []
        for score, chunk in scored[: settings.top_k_rerank]:
            reranked.append({**chunk, "rerank_score": float(score)})

    except Exception:
        # Fall back to top-k by RRF score
        reranked = candidates[: settings.top_k_rerank]

    return state.model_copy(update={"reranked_results": reranked})
