"""Node 10: LLMGenerationNode — Answer generation using Groq (Llama 3.3 70B)."""
from groq import Groq
from src.query.state import QueryState
from src.config import settings

client = Groq(api_key=settings.groq_api_key)

# Confidence threshold disabled — allow LLM to answer even with low scores.
# NO_CONTEXT_RESPONSE still fires if no documents were retrieved at all.
MIN_CONFIDENCE_THRESHOLD = 0.0

# ── Role-based system prompts ─────────────────────────────────────────────────

_BASE_GUIDELINES = """
- Answer based strictly on the provided context. Do NOT fabricate information.
- If the context does not contain enough information, say so clearly.
- Always reference the source(s) you used at the end of your answer.
- Keep answers professional. End with: "Sources: [list source document names]"
"""

ROLE_SYSTEM_PROMPTS: dict[str, str] = {
    "analyst": (
        "You are a banking knowledge assistant for Analyst-level staff at Citi Banking Operations.\n"
        "Focus on factual lookups, procedural guides, and KYC/KRisk documentation.\n"
        "Use clear numbered lists for procedural steps. Avoid legal interpretation."
        + _BASE_GUIDELINES
    ),
    "operations": (
        "You are an operations support assistant for Banking Operations staff at Citi.\n"
        "Specialise in wire transfers, SWIFT, account management SOPs, and escalation paths.\n"
        "Prefer step-by-step answers with system names (e.g. Citi Systems, CHIPS, Fedwire)."
        + _BASE_GUIDELINES
    ),
    "compliance": (
        "You are a compliance advisory assistant for Compliance Officers at Citi Banking Operations.\n"
        "You have access to restricted regulatory documents. Cite specific regulations and policies.\n"
        "Flag ambiguities or gaps in the documentation clearly. Recommend SME consultation for edge cases."
        + _BASE_GUIDELINES
    ),
    "admin": (
        "You are a power-user assistant for System Administrators at Citi Banking Operations.\n"
        "You have full access to all document sensitivity levels.\n"
        "Provide complete, detailed answers. Include technical details where relevant."
        + _BASE_GUIDELINES
    ),
}

# Fallback for unknown roles
_DEFAULT_PROMPT = (
    "You are a banking operations knowledge assistant for Citi Banking Operations teams.\n"
    "Answer based strictly on the provided knowledge base context. Do NOT fabricate information."
    + _BASE_GUIDELINES
)


def _get_system_prompt(user_role: str) -> str:
    return ROLE_SYSTEM_PROMPTS.get(user_role, _DEFAULT_PROMPT)


NO_CONTEXT_RESPONSE = (
    "I couldn't find relevant information in the knowledge base to answer your question. "
    "This may be because:\n"
    "1. The relevant documents haven't been ingested yet\n"
    "2. Your query is outside the scope of available documentation\n"
    "3. You may not have access to the relevant documents based on your role\n\n"
    "Please try rephrasing your question or contact your SME directly."
)

LOW_CONFIDENCE_RESPONSE = (
    "⚠️ I found some potentially related information, but my confidence in its relevance "
    "to your specific question is too low to provide a reliable answer.\n\n"
    "Please try:\n"
    "1. Rephrasing your question with more specific terms\n"
    "2. Checking if the relevant documents have been ingested\n"
    "3. Contacting your SME directly for this topic"
)


def llm_generation_node(state: QueryState) -> QueryState:
    """
    Calls Groq Llama-3.3-70b with the assembled context to generate an answer.
    Uses a role-specific system prompt and filters low-confidence responses.
    """
    if state.error:
        return state

    if not state.context_window or state.no_results:
        return state.model_copy(update={
            "response": NO_CONTEXT_RESPONSE,
            "confidence": 0.0,
        })

    system_prompt = _get_system_prompt(state.user_role)

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Context from knowledge base:\n\n{state.context_window}\n\n"
                f"---\n\nQuestion: {state.query}\n\n"
                f"Query type: {state.query_type}\n\n"
                "Please provide a comprehensive answer based on the above context."
            ),
        },
    ]

    try:
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,
            max_tokens=1000,
            temperature=0.1,
        )
        answer = response.choices[0].message.content.strip()

        # Compute confidence score (cross-encoder score normalised to [0, 1])
        top_score = 0.0
        if state.reranked_results:
            top_score = state.reranked_results[0].get("rerank_score", 0.5)
            top_score = min(max((top_score + 10) / 20, 0.0), 1.0)

        confidence = round(top_score, 2)

        return state.model_copy(update={
            "response": answer,
            "confidence": confidence,
        })

    except Exception as e:
        return state.model_copy(update={
            "response": f"Error generating response: {str(e)}",
            "error": str(e),
            "confidence": 0.0,
        })
