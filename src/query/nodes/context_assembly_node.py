"""Node 8: ContextAssemblyNode — Builds the final context window for the LLM."""
import tiktoken
from src.query.state import QueryState
from src.config import settings

# Token budget for context (leave room for system prompt + response)
CONTEXT_TOKEN_BUDGET = 6000
CHAT_HISTORY_TOKENS  = 800

_enc = None


def _get_encoder():
    global _enc
    if _enc is None:
        _enc = tiktoken.get_encoding("cl100k_base")
    return _enc


def _count_tokens(text: str) -> int:
    return len(_get_encoder().encode(text))


def _format_chunk(chunk: dict, index: int) -> str:
    source = chunk.get("source_name", "Unknown")
    page   = chunk.get("page_number")
    section = chunk.get("section")
    text   = chunk.get("text", "")

    header_parts = [f"[Source {index + 1}: {source}"]
    if page:
        header_parts.append(f"p.{page}")
    if section:
        header_parts.append(f"§ {section[:60]}")
    header = " | ".join(header_parts) + "]"

    return f"{header}\n{text}"


def context_assembly_node(state: QueryState) -> QueryState:
    """
    Assembles the context window from reranked chunks, respecting token budget.
    Also prepends recent chat history for multi-turn continuity.
    """
    if state.error or not state.reranked_results:
        return state.model_copy(update={"context_window": ""})

    chunks = state.reranked_results
    budget = CONTEXT_TOKEN_BUDGET

    # Build chat history context (last 3 turns)
    history_parts = []
    if state.chat_history:
        recent = state.chat_history[-6:]  # last 3 Q+A pairs
        for turn in recent:
            history_parts.append(f"{turn['role'].upper()}: {turn['content']}")
    history_text = "\n".join(history_parts)
    history_tokens = _count_tokens(history_text)
    budget -= min(history_tokens, CHAT_HISTORY_TOKENS)

    # Add chunks until budget exhausted
    context_parts = []
    used_tokens = 0

    for i, chunk in enumerate(chunks):
        formatted = _format_chunk(chunk, i)
        chunk_tokens = _count_tokens(formatted)

        if used_tokens + chunk_tokens > budget:
            break

        context_parts.append(formatted)
        used_tokens += chunk_tokens

    context_sections = []
    if history_text:
        context_sections.append("## Recent Conversation\n" + history_text)
    if context_parts:
        context_sections.append("## Retrieved Knowledge\n" + "\n\n---\n\n".join(context_parts))

    context_window = "\n\n".join(context_sections)

    return state.model_copy(update={"context_window": context_window})
