"""
LangGraph query pipeline orchestration.
Wires all 11 nodes into a directed graph with conditional edges.
"""
import time
from langgraph.graph import StateGraph, END

from src.query.state import QueryState
from src.query.nodes.auth_node import auth_node
from src.query.nodes.rbac_node import rbac_node
from src.query.nodes.classifier_node import classifier_node
from src.query.nodes.query_router_node import query_router_node
from src.query.nodes.hybrid_search_node import hybrid_search_node
from src.query.nodes.rbac_filter_node import rbac_filter_node
from src.query.nodes.reranker_node import reranker_node
from src.query.nodes.context_assembly_node import context_assembly_node
from src.query.nodes.llm_generation_node import llm_generation_node
from src.query.nodes.citation_formatter_node import citation_formatter_node
from src.query.nodes.audit_log_node import audit_log_node


# ── Wrapper nodes that track timing ───────────────────────────────────────────

def start_timer(state: QueryState) -> QueryState:
    return state.model_copy(update={"start_time_ms": time.time()})


def stop_timer(state: QueryState) -> QueryState:
    return state.model_copy(update={"end_time_ms": time.time()})


# ── Conditional edge functions ─────────────────────────────────────────────────

def should_continue_after_auth(state: QueryState) -> str:
    return "rbac" if state.auth_valid else "end"


def should_continue_after_rbac(state: QueryState) -> str:
    return "classify" if state.rbac_passed else "end"


def should_continue_after_search(state: QueryState) -> str:
    return "rbac_filter" if state.raw_results else "generate"


def should_continue_after_filter(state: QueryState) -> str:
    return "rerank" if state.filtered_results else "generate"


def error_response(state: QueryState) -> QueryState:
    """Terminal node that formats error/access-denied response."""
    error_msg = state.auth_error or state.error or "An error occurred. Please try again."
    return state.model_copy(update={
        "response": error_msg,
        "citations": [],
        "confidence": 0.0,
        "end_time_ms": time.time(),
    })


# ── Build the graph ────────────────────────────────────────────────────────────

def build_query_graph() -> StateGraph:
    graph = StateGraph(QueryState)

    # Add all nodes
    graph.add_node("start_timer",        start_timer)
    graph.add_node("auth",               auth_node)
    graph.add_node("rbac",               rbac_node)
    graph.add_node("classify",           classifier_node)
    graph.add_node("rewrite",            query_router_node)
    graph.add_node("search",             hybrid_search_node)
    graph.add_node("rbac_filter",        rbac_filter_node)
    graph.add_node("rerank",             reranker_node)
    graph.add_node("assemble_context",   context_assembly_node)
    graph.add_node("generate",           llm_generation_node)
    graph.add_node("format_citations",   citation_formatter_node)
    graph.add_node("stop_timer",         stop_timer)
    graph.add_node("audit",              audit_log_node)
    graph.add_node("error_response",     error_response)

    # Entry point
    graph.set_entry_point("start_timer")

    # Linear flow: start → auth
    graph.add_edge("start_timer", "auth")

    # Auth conditional
    graph.add_conditional_edges(
        "auth",
        should_continue_after_auth,
        {"rbac": "rbac", "end": "error_response"},
    )

    # RBAC conditional
    graph.add_conditional_edges(
        "rbac",
        should_continue_after_rbac,
        {"classify": "classify", "end": "error_response"},
    )

    # Classification → query rewriting → hybrid search
    graph.add_edge("classify",  "rewrite")
    graph.add_edge("rewrite",   "search")

    # Search conditional
    graph.add_conditional_edges(
        "search",
        should_continue_after_search,
        {"rbac_filter": "rbac_filter", "generate": "generate"},
    )

    # RBAC filter conditional
    graph.add_conditional_edges(
        "rbac_filter",
        should_continue_after_filter,
        {"rerank": "rerank", "generate": "generate"},
    )

    # Rerank → context assembly → generate
    graph.add_edge("rerank",          "assemble_context")
    graph.add_edge("assemble_context", "generate")

    # Generate → citations → stop timer → audit → END
    graph.add_edge("generate",          "format_citations")
    graph.add_edge("format_citations",  "stop_timer")
    graph.add_edge("stop_timer",        "audit")
    graph.add_edge("audit",             END)

    # Error path also writes audit
    graph.add_edge("error_response", "stop_timer")

    return graph.compile()


# Singleton compiled graph
_compiled_graph = None


def get_query_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_query_graph()
    return _compiled_graph


def run_query(
    query: str,
    user_id: str,
    user_role: str,
    session_id: str,
    chat_history: list[dict] | None = None,
) -> QueryState:
    """
    Main entry point: run the full pipeline for a user query.
    Returns the final QueryState with response, citations, and metadata.
    """
    graph = get_query_graph()

    initial_state = QueryState(
        query=query,
        user_id=user_id,
        user_role=user_role,
        session_id=session_id,
        chat_history=chat_history or [],
    )

    result = graph.invoke(initial_state)
    return result
