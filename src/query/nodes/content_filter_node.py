"""
Node 3b — ContentFilterNode
Runs immediately after RBAC, before classification.

Two-layer approach (no LLM call, zero API cost):
  Layer 1: compiled regex patterns — fast and deterministic.
  Layer 2: exact phrase list — catches common attack phrasings.

If a query is flagged → sets content_filtered = True and a user-facing reason.
If safe → passes through unchanged.
The node never raises; any exception falls back to allowing the query through.
"""

import re
import logging

from src.query.state import QueryState

logger = logging.getLogger(__name__)

# ── Restricted message shown to users ─────────────────────────────────────────

RESTRICTED_MESSAGE = (
    "⚠️ Your message has been flagged as restricted content and cannot be "
    "processed. Please keep your queries related to banking operations."
)

# ── Layer 1: Regex pattern blocklist ──────────────────────────────────────────
# Each pattern uses word-boundary matching (\b) where practical.
# Pattern categories: weapons, explosives, drugs, hacking, self-harm,
# explicit content, hate speech, violence.

_RAW_PATTERNS = [
    # Weapons & explosives
    r"\bhow\s+to\s+(make|build|create|assemble|construct)\s+(a\s+)?(bomb|explosive|ied|grenade|mine|detonator)",
    r"\bbomb\s+(making|recipe|instructions|guide|tutorial)",
    r"\b(pipe\s+bomb|nail\s+bomb|car\s+bomb|suicide\s+bomb|dirty\s+bomb|nuclear\s+bomb)",
    r"\b(explosive|c4|tnt|rdx|semtex|anfo|thermite|nitroglycerin)\s*(synthesis|making|recipe|production)",
    r"\bhow\s+to\s+(detonate|trigger|arm)\s+.{0,30}\b(bomb|explosive|device)",
    r"\b(weapon|gun|firearm|rifle|pistol|ammunition)\s+illegal",
    r"\bhow\s+to\s+(smuggle|traffic)\s+(weapons|guns|arms|explosives)",
    # Cyber attacks / hacking
    r"\bhow\s+to\s+(hack|crack|exploit|bypass|compromise)\s+(into\s+)?.{0,40}(system|server|network|account|database|password)",
    r"\bhow\s+to\s+(create|write|build|make|develop|deploy|install)\s+(ransomware|malware|trojan|keylogger|rootkit|spyware|botnet|virus|worm)",
    r"\b(ransomware|malware|trojan|keylogger|rootkit|spyware|botnet)\s+(code|script|install|deploy|create|write)",
    r"\bsql\s+injection\b.{0,30}(attack|exploit|hack)",
    r"\bphishing\s+(email|kit|template|attack|campaign)\b",
    r"\bddos\s+attack\b",
    r"\bzero[\s-]day\s+exploit\b",
    # Drugs / controlled substances
    r"\bhow\s+to\s+(make|cook|synthesize|manufacture|produce)\s+(meth|methamphetamine|heroin|cocaine|fentanyl|lsd|ecstasy|mdma|crack)",
    r"\b(drug|narcotics)\s+(synthesis|recipe|cook|lab|manufacture)",
    r"\bhow\s+to\s+(buy|sell|traffic|smuggle)\s+(drugs|narcotics|meth|heroin|cocaine|fentanyl)",
    # Violence / murder
    r"\bhow\s+to\s+(kill|murder|assassinate|poison|stab|shoot)\s+(a\s+)?(person|someone|people|human)",
    r"\bhow\s+to\s+(strangle|suffocate)\s+(a\s+)?(person|someone|people)",
    r"\bmass\s+(shooting|killing|murder)\s+(plan|instructions|how\s+to)",
    r"\bhow\s+to\s+(get\s+away\s+with|commit)\s+murder",
    # Self-harm (respond with care, but block engagement)
    r"\bhow\s+to\s+(commit\s+suicide|kill\s+myself|end\s+my\s+life|self[\s-]harm)",
    r"\bbest\s+way\s+to\s+(die|end\s+it\s+all|commit\s+suicide)",
    # Explicit / NSFW
    r"\b(porn|pornography|xxx|nude|naked|sex\s+video|adult\s+content)\b",
    r"\b(child\s+(porn|abuse|exploitation|sexual))",
    # Hate speech
    r"\b(kill\s+all|genocide|ethnic\s+cleansing)\b",
    r"\b(n[i1]gg[e3]r|f[a4]gg[o0]t|ch[i1]nk|sp[i1]c|k[i1]k[e3])\b",
    # Terrorism
    r"\b(how\s+to\s+(join|recruit\s+for|fund)|how\s+to\s+plan)\s+(isis|al[\s-]?qaeda|terrorist|terror\s+attack)",
    r"\bterrorist\s+(attack|plot|plan|bomb|operation)\b",
    r"\bjihad\s+(attack|how\s+to|kill)\b",
    # Financial crimes (protect banking context)
    r"\bhow\s+to\s+(launder|wash)\s+money\b",
    r"\bhow\s+to\s+(avoid|evade)\s+(taxes|tax\s+reporting|aml|kyc)\b",
    r"\bhow\s+to\s+commit\s+(fraud|insider\s+trading|embezzlement)\b",
]

# Compile once at import time for performance
_COMPILED_PATTERNS = [
    re.compile(p, re.IGNORECASE | re.DOTALL) for p in _RAW_PATTERNS
]

# ── Layer 2: Exact phrase list (after normalisation) ─────────────────────────
# Catches short, direct attack phrases that regex above might over-generalise.

_EXACT_PHRASES = [
    "how to make a bomb",
    "how to build a bomb",
    "how to make explosives",
    "how to make a gun",
    "how to make drugs",
    "how to hack a bank",
    "how to hack a system",
    "how to crack a password",
    "how to make meth",
    "how to make cocaine",
    "how to make heroin",
    "how to poison someone",
    "how to kill someone",
    "how to commit murder",
    "how to commit suicide",
    "how to launder money",
    "how to evade kyc",
    "how to evade aml",
    "how to commit fraud",
    "how to make a bioweapon",
    "how to make a chemical weapon",
    "step by step bomb",
    "bomb recipe",
    "bomb making instructions",
    "drug synthesis guide",
]


def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", " ", text)   # remove punctuation
    text = re.sub(r"\s+", " ", text)        # collapse spaces
    return text


def _is_flagged(query: str) -> tuple[bool, str]:
    """
    Returns (is_flagged, matched_category) for a query string.
    Checks Layer 1 (regex) then Layer 2 (phrase list).
    """
    # Layer 1: compiled regex patterns
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(query):
            return True, "Harmful or restricted content detected (pattern match)"

    # Layer 2: normalised phrase matching
    normalised = _normalise(query)
    for phrase in _EXACT_PHRASES:
        if phrase in normalised:
            return True, "Harmful or restricted content detected (phrase match)"

    return False, ""


# ── Node function ─────────────────────────────────────────────────────────────

def content_filter_node(state: QueryState) -> QueryState:
    """
    Content safety filter node.
    Blocks harmful / abusive / off-topic queries before any LLM or retrieval
    call is made.  If blocked, sets content_filtered=True and a user-facing
    error on the state so the graph routes to error_response.
    """
    try:
        flagged, reason = _is_flagged(state.query)
        if flagged:
            logger.warning(
                "Content filter blocked query for user=%s | reason=%s | query=%r",
                state.user_id,
                reason,
                state.query[:120],
            )
            return state.model_copy(update={
                "content_filtered": True,
                "content_filter_reason": reason,
                "error": RESTRICTED_MESSAGE,
            })

        # Safe — pass through
        return state.model_copy(update={"content_filtered": False})

    except Exception as exc:  # noqa: BLE001
        # Never let the filter crash the pipeline
        logger.error("ContentFilterNode raised unexpectedly: %s", exc)
        return state.model_copy(update={"content_filtered": False})
