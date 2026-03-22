"""Node 10: CitationFormatterNode — Extracts and formats inline + final citations."""
import re
from src.query.state import QueryState


def citation_formatter_node(state: QueryState) -> QueryState:
    """
    Builds a structured citation list from the reranked results used in generation.
    Deduplicates by source_name + page_number.
    """
    if not state.reranked_results:
        return state.model_copy(update={"citations": []})

    seen = set()
    citations = []

    for i, chunk in enumerate(state.reranked_results):
        source_name  = chunk.get("source_name", "Unknown")
        page_number  = chunk.get("page_number")
        section      = chunk.get("section")
        chunk_id     = chunk.get("chunk_id", "")
        source_type  = chunk.get("source_type", "")
        rerank_score = chunk.get("rerank_score")

        key = (source_name, page_number)
        if key in seen:
            continue
        seen.add(key)

        citation = {
            "index":       i + 1,
            "source_name": source_name,
            "source_type": source_type,
            "page_number": page_number,
            "section":     section,
            "chunk_id":    chunk_id,
        }
        if rerank_score is not None:
            citation["relevance_score"] = round(float(rerank_score), 3)

        citations.append(citation)

    return state.model_copy(update={"citations": citations})
