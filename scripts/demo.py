"""
demo.py — End-to-End Smoke Test for CITI BRAIN Banking Chatbot POC
===================================================================

Proves the system works end-to-end without manual UI interaction.

Usage:
    # 1. Start the API server in another terminal:
    #    uvicorn src.api.main:app --reload --port 8000

    # 2. Run this script:
    python scripts/demo.py [--url http://localhost:8000]

What it does:
    1. Logs in as the demo analyst user
    2. Sends 3 representative queries (factual, procedural, greeting)
    3. Prints response, query type, confidence, citations, and latency
    4. Exits with code 0 on success, 1 on any failure
"""

import sys
import argparse
import textwrap
import httpx


# ── Demo configuration ─────────────────────────────────────────────────────────

DEMO_USER = "analyst1"
DEMO_PASS = "analyst123!"

DEMO_QUESTIONS = [
    "What documents are required for KYC verification?",
    "How do I initiate a wire transfer?",
    "Hello!",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def separator(char="─", width=60):
    print(char * width)


def print_header():
    separator("=")
    print(" CITI BRAIN — End-to-End Demo")
    separator("=")


def login(base_url: str) -> str:
    """Login and return a Bearer token. Raises SystemExit on failure."""
    resp = httpx.post(
        f"{base_url}/api/auth/login",
        data={"username": DEMO_USER, "password": DEMO_PASS},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"✗ Login failed: {resp.status_code} — {resp.text}")
        sys.exit(1)

    data = resp.json()
    token = data.get("access_token")
    role  = data.get("role", "?")
    print(f"✓ Login successful (role: {role})")
    return token


def ask(base_url: str, token: str, question: str, session_id: str) -> dict:
    """Send a single chat message and return the parsed response dict."""
    resp = httpx.post(
        f"{base_url}/api/chat",
        json={"query": question, "session_id": session_id, "chat_history": []},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.json()


def print_result(index: int, question: str, result: dict):
    """Pretty-print a single Q&A result."""
    print()
    print(f"[Q{index}] {question}")
    separator()

    query_type = result.get("query_type", "unknown")
    confidence = result.get("confidence", 0.0)
    latency_ms = result.get("latency_ms", 0)
    response   = result.get("response", "")
    citations  = result.get("citations", [])

    # Header line
    meta = f"Type: {query_type} | Latency: {latency_ms}ms"
    if query_type != "greeting":
        meta += f" | Confidence: {confidence:.2f}"
    print(meta)

    # Response text (wrapped)
    print()
    print("Response:")
    for line in textwrap.wrap(response, width=70):
        print(f"  {line}")

    # Citations
    if citations:
        print()
        print("Citations:")
        for c in citations[:3]:  # show up to 3
            src  = c.get("source_name", "?")
            page = c.get("page_number")
            sec  = c.get("section") or ""
            score = c.get("relevance_score")
            parts = [f"  [{c['index']}] {src}"]
            if page:
                parts[0] += f" p.{page}"
            if sec:
                parts[0] += f" § {sec[:40]}"
            if score is not None:
                parts[0] += f" (score: {score:.3f})"
            print(parts[0])


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="CITI BRAIN end-to-end smoke test")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Base URL of the API server (default: http://localhost:8000)",
    )
    args = parser.parse_args()
    base_url = args.url.rstrip("/")

    print_header()

    # ── 1. Login ──────────────────────────────────────────────────────────────
    try:
        token = login(base_url)
    except httpx.ConnectError:
        print(f"\n✗ Cannot connect to {base_url}")
        print("  Make sure the API server is running:")
        print("    uvicorn src.api.main:app --reload --port 8000")
        sys.exit(1)

    # Use a fixed session ID so all 3 questions share one chat session
    import uuid
    session_id = str(uuid.uuid4())

    # ── 2. Send demo questions ─────────────────────────────────────────────────
    failures = 0

    for i, question in enumerate(DEMO_QUESTIONS, start=1):
        try:
            result = ask(base_url, token, question, session_id)
            print_result(i, question, result)
        except httpx.HTTPStatusError as exc:
            print(f"\n✗ Q{i} failed: HTTP {exc.response.status_code} — {exc.response.text}")
            failures += 1
        except Exception as exc:
            print(f"\n✗ Q{i} failed: {exc}")
            failures += 1

    # ── 3. Summary ────────────────────────────────────────────────────────────
    print()
    separator("=")
    total = len(DEMO_QUESTIONS)
    passed = total - failures

    if failures == 0:
        print(f"✓ All {total} queries succeeded.")
        print()
        print("Next steps:")
        print("  • Open the frontend:  http://localhost:5173")
        print("  • Browse the API docs: http://localhost:8000/docs")
        print("  • Try admin stats endpoint with: admin / admin123!")
    else:
        print(f"✗ {failures}/{total} queries failed.")

    separator("=")
    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    main()
