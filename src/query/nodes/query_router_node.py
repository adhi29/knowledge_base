"""Node 4: QueryRouterNode — Query rewriting with HyDE, expansion, and multi-query."""
from groq import Groq
from src.query.state import QueryState
from src.config import settings

client = Groq(api_key=settings.groq_api_key)

REWRITE_SYSTEM = """You are a search query optimizer for a banking operations knowledge base.
Given a user question, generate 3 improved search query variants that:
1. Expand banking acronyms and terminology
2. Rephrase the question for better document matching
3. Target different aspects of the question

Return ONLY a JSON array of 3 strings. Example: ["query1", "query2", "query3"]"""

HYDE_SYSTEM = """You are an expert in banking operations.
Write a short, factual paragraph (2-3 sentences) that would directly answer this question.
This is used for document retrieval — write as if you know the answer.
Be specific and use banking terminology."""


def query_router_node(state: QueryState) -> QueryState:
    """
    Applies three query rewriting strategies:
    1. HyDE — hypothetical answer embedding
    2. Query expansion — terminology and acronym expansion
    3. Multi-query — 3 query variants for broader coverage
    """
    query = state.query
    rewritten = [query]  # Always include original

    try:
        # Multi-query expansion
        response = client.chat.completions.create(
            model=settings.router_model,
            messages=[
                {"role": "system", "content": REWRITE_SYSTEM},
                {"role": "user", "content": query},
            ],
            max_tokens=200,
            temperature=0.3,
        )
        import json
        text = response.choices[0].message.content.strip()
        variants = json.loads(text)
        if isinstance(variants, list):
            rewritten.extend([v for v in variants if isinstance(v, str)])
    except Exception:
        pass  # Fall back to original query

    try:
        # HyDE — hypothetical document embedding
        if state.query_type in ("factual", "procedural", "policy", "exception-handling"):
            hyde_response = client.chat.completions.create(
                model=settings.router_model,
                messages=[
                    {"role": "system", "content": HYDE_SYSTEM},
                    {"role": "user", "content": query},
                ],
                max_tokens=150,
                temperature=0.2,
            )
            hyde_text = hyde_response.choices[0].message.content.strip()
            rewritten.append(hyde_text)
    except Exception:
        pass

    # Deduplicate while preserving order
    seen = set()
    unique_queries = []
    for q in rewritten:
        if q not in seen:
            seen.add(q)
            unique_queries.append(q)

    return state.model_copy(update={"rewritten_queries": unique_queries})
