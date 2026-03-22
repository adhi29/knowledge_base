"""Node 3: ClassifierNode — Query type classification using Groq."""
from groq import Groq
from src.query.state import QueryState
from src.config import settings

client = Groq(api_key=settings.groq_api_key)

QUERY_TYPES = ["factual", "procedural", "policy", "exception-handling", "general"]

SYSTEM_PROMPT = """You are a query classifier for a banking operations knowledge chatbot.
Classify the user query into exactly ONE of these types:

- factual: Asks for a specific fact, definition, number, or piece of information
- procedural: Asks how to do something, step-by-step processes
- policy: Asks about rules, regulations, compliance requirements, policies
- exception-handling: Asks about edge cases, exceptions to rules, escalation paths
- general: General conversation, greetings, or out-of-scope questions

Respond with ONLY the type label (one word from the list above). No explanation."""


def classifier_node(state: QueryState) -> QueryState:
    """
    Classifies the user query into one of 5 types.
    Falls back to 'general' on any error.
    """
    try:
        response = client.chat.completions.create(
            model=settings.router_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": state.query},
            ],
            max_tokens=10,
            temperature=0,
        )
        raw = response.choices[0].message.content.strip().lower()
        query_type = raw if raw in QUERY_TYPES else "general"
    except Exception:
        query_type = "general"

    return state.model_copy(update={"query_type": query_type})
