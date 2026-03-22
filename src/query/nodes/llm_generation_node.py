"""Node 9: LLMGenerationNode — Answer generation using Groq (Llama 3.3 70B)."""
from groq import Groq
from src.query.state import QueryState
from src.config import settings

client = Groq(api_key=settings.groq_api_key)

SYSTEM_PROMPT = """You are a banking operations knowledge assistant for Citi Banking Operations teams.
Your role is to provide accurate, concise answers based ONLY on the provided knowledge base context.

Guidelines:
- Answer based strictly on the provided context. Do NOT fabricate information.
- If the context does not contain enough information, say so clearly.
- For procedural questions, list steps clearly and numbered.
- For policy questions, cite the specific policy or document.
- Always reference the source(s) you used at the end of your answer.
- Keep answers clear and professional — appropriate for banking operations staff.
- If you detect the query is out of scope or unrelated to banking operations, politely redirect.

Format:
- Use clear paragraphs or numbered lists as appropriate.
- End with: "Sources: [list the source document names]"
"""

NO_CONTEXT_RESPONSE = (
    "I couldn't find relevant information in the knowledge base to answer your question. "
    "This may be because:\n"
    "1. The relevant documents haven't been ingested yet\n"
    "2. Your query is outside the scope of available documentation\n"
    "3. You may not have access to the relevant documents based on your role\n\n"
    "Please try rephrasing your question or contact your SME directly."
)


def llm_generation_node(state: QueryState) -> QueryState:
    """
    Calls OpenAI GPT-4o with the assembled context to generate an answer.
    Returns a no-context fallback message if context is empty.
    """
    if state.error:
        return state

    if not state.context_window or state.no_results:
        return state.model_copy(update={
            "response": NO_CONTEXT_RESPONSE,
            "confidence": 0.0,
        })

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
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

        # Simple confidence proxy: ratio of top rerank score to 1.0
        top_score = 0.0
        if state.reranked_results:
            top_score = state.reranked_results[0].get("rerank_score", 0.5)
            # Normalize: cross-encoder scores are typically -10 to 10
            top_score = min(max((top_score + 10) / 20, 0.0), 1.0)

        return state.model_copy(update={
            "response": answer,
            "confidence": round(top_score, 2),
        })

    except Exception as e:
        return state.model_copy(update={
            "response": f"Error generating response: {str(e)}",
            "error": str(e),
            "confidence": 0.0,
        })
