# Banking Knowledge Chatbot — End-to-End Architecture

AI-powered RAG (Retrieval-Augmented Generation) chatbot for Citi Banking Operations teams.
Built as a 16-week POC by Virtusa AI CoE.

---

## Table of Contents

1. [High-Level Overview](#1-high-level-overview)
2. [Part A — Document Ingestion Pipeline](#2-part-a--document-ingestion-pipeline)
3. [Part B — Query & Answer Pipeline](#3-part-b--query--answer-pipeline)
4. [Authentication & RBAC](#4-authentication--rbac)
5. [Storage Layer](#5-storage-layer)
6. [API Layer](#6-api-layer)
7. [Data Flow Diagram](#7-data-flow-diagram)
8. [Tech Stack Summary](#8-tech-stack-summary)

---

## 1. High-Level Overview

The system has two completely separate pipelines:

```
INGESTION (offline, manual trigger)
  Files / Docs  →  Parse  →  Chunk  →  Embed  →  FAISS + SQLite

QUERY (online, per user request)
  HTTP Request  →  JWT Auth  →  RBAC  →  Classify  →  Rewrite  →  Hybrid Search
               →  RBAC Filter  →  Rerank  →  Assemble Context  →  LLM Generate
               →  Citations  →  Audit Log  →  HTTP Response
```

These two pipelines share the same storage layer (FAISS + SQLite) but run independently.

---

## 2. Part A — Document Ingestion Pipeline

### How to trigger

```bash
# Via script
python scripts/ingest_sample.py --path data/sample_docs/

# Via API (admin only)
POST /api/admin/ingest
{ "path": "data/sample_docs/", "allowed_roles": ["analyst"], "sensitivity_level": "internal" }
```

### Step-by-step flow

```
src/ingestion/pipeline.py  →  IngestionPipeline.run()
```

#### Step 1 — Fetch (FileConnector)
**File:** `src/ingestion/connectors/file_connector.py`

The `FileConnector` scans the given path for supported file types: `.pdf`, `.txt`, `.md`, `.docx`.

- **PDF**: PyMuPDF extracts native text page-by-page. If a page has fewer than 50 characters (scanned/image PDF), pytesseract OCR is used as fallback. Tables are separately extracted via pdfplumber.
- **DOCX**: python-docx extracts paragraphs.
- **TXT / MD**: read as plain text.

Each document becomes a `RawDocument` object containing: raw text, list of pages (with page numbers), extracted tables, source metadata (path, type, name, allowed roles, sensitivity level).

> Enterprise connectors (SharePoint, Confluence, Jira, Outlook) exist as stubs in `src/ingestion/connectors/stub_connectors.py` — they return empty lists until implemented with real API credentials.

#### Step 2 — Chunk
**File:** `src/ingestion/processors/chunker.py`

Each `RawDocument` is split into semantic chunks of ~512 tokens (default). The chunker:
- Respects page boundaries when page data is available.
- Assigns each chunk a `chunk_id` (UUID) and `chunk_index`.
- Computes a `content_hash` (SHA256 of the chunk text) for deduplication.
- Inherits `allowed_roles` and `sensitivity_level` from the parent document.

#### Step 3 — Deduplicate
**File:** `src/ingestion/deduplicator.py`

Each chunk's `content_hash` is checked against the `text_chunks` table in SQLite.
- If the hash already exists → chunk is **skipped** (no re-embedding, no storage).
- If the hash is new or changed → chunk proceeds to embedding.

This means re-ingesting a file that hasn't changed costs almost nothing. If a paragraph was edited, only that chunk's hash changes, so only that chunk gets re-embedded.

#### Step 4 — Embed
**File:** `src/storage/vector_store.py`

New chunks are embedded in batches of 50 using `sentence-transformers/all-MiniLM-L6-v2` (local model, 384 dimensions, no API key needed).

Each text is encoded to a float32 vector, then L2-normalized so that inner-product search equals cosine similarity. Vectors are added to the FAISS flat index (`IndexFlatIP`).

#### Step 5 — Store
After embedding:
- **FAISS index** (`.bin` file) is saved to disk — contains the raw vectors.
- **Metadata pickle** (`_meta.pkl`) is saved — maps FAISS index positions to chunk metadata (chunk_id, text, source_name, page_number, section).
- **BM25 index** (`_bm25.pkl`) is rebuilt from all texts and saved — used for keyword search.
- **SQLite** (`data/chatbot.db`) stores full chunk metadata via `upsert_chunk_metadata()`: source path, allowed roles, sensitivity level, content hash, timestamps.
- **Ingestion log** is written to `ingestion_log` table recording success/partial/failure per document.

---

## 3. Part B — Query & Answer Pipeline

Every user chat message triggers the full LangGraph pipeline. The graph is a **compiled singleton** (`_compiled_graph`) built once at startup.

```
src/query/graph.py  →  run_query()  →  graph.invoke(initial_state)
```

The pipeline passes a single `QueryState` (Pydantic model) through 13 nodes. Each node returns an updated copy of the state — nothing is mutated in place.

### Node 1 — `start_timer`
Records `start_time_ms = time.time()` on the state. Used later to compute latency.

### Node 2 — `auth` (AuthNode)
**File:** `src/query/nodes/auth_node.py`

Validates that `user_id` and `user_role` are present on the state (injected by FastAPI from the JWT token). Re-fetches the user record from SQLite via `get_user_by_id()` to confirm the user is active and to refresh the role from the database (single source of truth).

- If user not found → sets `auth_valid = False`, `auth_error` message → graph routes to `error_response`.
- If valid → sets `auth_valid = True`, refreshes `user_role` from DB.

### Node 3 — `rbac` (RBACNode)
**File:** `src/query/nodes/rbac_node.py`

Checks that the user's role is one of the known valid roles: `analyst`, `operations`, `compliance`, `admin`. Sets `rbac_passed = True/False`. If false → graph routes to `error_response`.

### Node 4 — `classify` (ClassifierNode)
**File:** `src/query/nodes/classifier_node.py`

Sends the raw query to Groq (`llama-3.1-8b-instant`, the fast/cheap routing model) with a short system prompt asking it to classify the query into one of five types:

| Type | Example |
|---|---|
| `factual` | "What is the KYC document limit?" |
| `procedural` | "How do I initiate a wire transfer?" |
| `policy` | "What are the AML reporting rules?" |
| `exception-handling` | "What happens if a customer misses the deadline?" |
| `general` | "Hello" / out-of-scope questions |

The classification label is stored in `state.query_type` and used downstream to shape how the LLM answers and whether HyDE is applied.

### Node 5 — `rewrite` (QueryRouterNode)
**File:** `src/query/nodes/query_router_node.py`

Applies two query rewriting strategies to improve retrieval recall:

**Multi-query expansion** — Sends the query to Groq and asks for 3 alternative phrasings that expand banking acronyms and rephrase for better document matching. Returns a JSON array of 3 strings.

**HyDE (Hypothetical Document Embedding)** — For non-general queries, asks Groq: *"Write a short paragraph that would directly answer this question."* The hypothetical answer is then used as an additional search query. Because the hypothetical answer uses the same language as real documents, it finds more relevant chunks than the raw user question alone.

All variants (original + 3 expanded + 1 HyDE) are deduplicated and stored in `state.rewritten_queries`.

### Node 6 — `search` (HybridSearchNode)
**File:** `src/query/nodes/hybrid_search_node.py`

Runs **hybrid search** for each query variant and merges results.

For each query string:
1. **Semantic search**: Embeds the query with `all-MiniLM-L6-v2` → searches FAISS index (cosine similarity via inner product on normalized vectors) → returns top-K results with `semantic_score`.
2. **BM25 keyword search**: Tokenizes the query → scores all documents using BM25Okapi → returns top-K results with `bm25_score`.
3. **RRF fusion (Reciprocal Rank Fusion)**: Combines the two ranked lists using the formula `score += 1 / (60 + rank)` for each list. This blends semantic relevance with keyword precision without needing to normalize scores between the two methods.

Across all query variants, the highest RRF score per `chunk_id` is kept. Final results sorted by RRF score descending → stored in `state.raw_results`.

If no results found → sets `no_results = True` → graph skips to `generate` (which returns a "not found" message).

### Node 7 — `rbac_filter` (RBACFilterNode)
**File:** `src/query/nodes/rbac_filter_node.py`

Post-retrieval security filter. For each chunk in `raw_results`:
- Looks up `chunk_id` in SQLite to get its `sensitivity_level` and `allowed_roles`.
- Checks if the user's role is permitted to see that sensitivity level:

| Role | Allowed Sensitivity Levels |
|---|---|
| `analyst` | `public`, `internal` |
| `operations` | `public`, `internal`, `confidential` |
| `compliance` | `public`, `internal`, `confidential`, `restricted` |
| `admin` | all levels |

Chunks the user cannot access are silently dropped. If all chunks are filtered out → sets `no_results = True` with an access-denied message.

This is a **double check** — documents are already tagged at ingest time with `allowed_roles`, but this node enforces at query time based on sensitivity level, which is more granular.

### Node 8 — `rerank` (ReRankerNode)
**File:** `src/query/nodes/reranker_node.py`

Re-scores the filtered chunks using a **cross-encoder model** (`cross-encoder/ms-marco-MiniLM-L-6-v2`, local, free). Unlike the bi-encoder used for initial retrieval, a cross-encoder sees both the query and chunk text together, producing a much more accurate relevance score.

For each `(query, chunk_text)` pair, the cross-encoder outputs a float score (typically -10 to +10). Chunks are re-sorted by this score descending, and only the top-K (configurable via `settings.top_k_rerank`) are kept in `state.reranked_results`.

Falls back to RRF order if the cross-encoder fails.

### Node 9 — `assemble_context` (ContextAssemblyNode)
**File:** `src/query/nodes/context_assembly_node.py`

Builds the final text block passed to the LLM. It:
- Counts tokens using `tiktoken` (`cl100k_base` encoding, same as GPT-4).
- Reserves up to 800 tokens for the last 3 turns of chat history (for multi-turn conversation continuity).
- Fills remaining budget (6000 tokens total) with reranked chunks, stopping when budget is exhausted.
- Formats each chunk with a source header: `[Source 1: wire_transfer_sop.pdf | p.3 | § Approval Process]`.

Result stored in `state.context_window`.

### Node 10 — `generate` (LLMGenerationNode)
**File:** `src/query/nodes/llm_generation_node.py`

Calls Groq API (`llama-3.3-70b-versatile`, the large high-quality model) with:
- **System prompt**: instructs the model to answer strictly from context, not fabricate, cite sources, keep a professional banking tone.
- **User message**: the assembled context window + the original query + query type.
- **Temperature**: 0.1 (near-deterministic for factual accuracy).
- **Max tokens**: 1000.

If `context_window` is empty → returns a canned "not found" message without calling the LLM.

Confidence score is derived from the top reranker score, normalized from [-10, 10] to [0, 1].

### Node 11 — `format_citations` (CitationFormatterNode)
**File:** `src/query/nodes/citation_formatter_node.py`

Builds a structured citation list from `reranked_results`. Deduplicates by `(source_name, page_number)`. Each citation includes: source name, source type, page number, section, chunk_id, and relevance score.

### Node 12 — `stop_timer`
Records `end_time_ms = time.time()`. Latency = `(end_time_ms - start_time_ms) * 1000` ms.

### Node 13 — `audit` (AuditLogNode)
**File:** `src/query/nodes/audit_log_node.py`

Writes an append-only record to the `audit_logs` SQLite table: user_id, session_id, query, query_type, list of retrieved chunk_ids, first 500 chars of response, latency_ms. This node never raises — audit failures are logged but never surface to the user.

### Error path

At any node where `auth_valid = False` or `rbac_passed = False`, the graph routes to `error_response` which formats the error message and then flows to `stop_timer → audit → END`. So even failed/denied queries are audited.

---

## 4. Authentication & RBAC

### Login flow
**File:** `src/api/auth.py`

1. Client sends `POST /api/auth/login` with username + password (form data).
2. Server looks up the user in SQLite, verifies bcrypt hash via passlib.
3. If valid → creates a JWT token signed with `SECRET_KEY` (HS256). Payload contains: `sub` (user_id), `username`, `role`, `exp` (expiry).
4. Client stores the token and sends it as `Authorization: Bearer <token>` on every subsequent request.

### Per-request auth
FastAPI dependency `get_current_user` (in `src/api/auth.py`):
1. Extracts the Bearer token from the `Authorization` header.
2. Decodes and validates the JWT (signature + expiry) using `python-jose`.
3. Returns a `TokenData(user_id, username, role)` object.
4. Any route that uses `Depends(get_current_user)` is protected.

The `require_role(*roles)` dependency factory further restricts endpoints to specific roles. For example, the ingest endpoint requires `admin` role.

---

## 5. Storage Layer

### FAISS Vector Store (`src/storage/vector_store.py`)
- In-memory `IndexFlatIP` (exact inner-product search, cosine on L2-normalized vectors).
- Singleton instance — loaded once at startup from `.bin` file, held in memory.
- Persisted to disk after every `add_chunks()` call:
  - `data/faiss_index.bin` — FAISS binary index
  - `data/faiss_index_meta.pkl` — list of chunk metadata dicts (maps FAISS position → chunk info)
  - `data/faiss_index_bm25.pkl` — serialized BM25Okapi object

### SQLite Database (`src/storage/database.py`)
Path: `data/chatbot.db`. WAL mode enabled for concurrent reads.

| Table | Purpose |
|---|---|
| `text_chunks` | Full chunk metadata: chunk_id, source_path, content_hash, sensitivity_level, allowed_roles, page_number, section, is_active, created_at, updated_at |
| `users` | user_id, username, hashed_password, role, department, is_active |
| `role_permissions` | Maps roles → allowed sensitivity levels |
| `user_sessions` | Session tracking |
| `audit_logs` | Every query interaction (append-only) |
| `ingestion_log` | Every ingestion run (status, chunks created) |
| `table_records` | Metadata for tables extracted from PDFs |

---

## 6. API Layer

**File:** `src/api/main.py` — FastAPI app with CORS middleware.

### Routes

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/login` | None | Login, returns JWT |
| `POST` | `/api/auth/register` | None | Register new user |
| `GET` | `/api/auth/me` | JWT | Current user info |
| `POST` | `/api/chat/` | JWT | Send a chat message |
| `GET` | `/api/chat/history/{session_id}` | JWT | Get chat history |
| `POST` | `/api/admin/ingest` | JWT (admin) | Trigger document ingestion |
| `GET` | `/api/admin/stats` | JWT (admin) | System statistics |
| `GET` | `/health` | None | Health check |

The chat endpoint calls `run_query()` from `src/query/graph.py`, waits for the full pipeline to complete, and returns the response + citations + confidence + latency.

---

## 7. Data Flow Diagram

```
USER
 │
 ▼
POST /api/chat/
 │  Authorization: Bearer <JWT>
 │
 ▼
FastAPI  ──► get_current_user()  ──► decode JWT  ──► TokenData(user_id, role)
 │
 ▼
run_query(query, user_id, user_role, session_id)
 │
 ▼
LangGraph Pipeline (QueryState flows through each node)
 │
 ├─ [1] start_timer          record start timestamp
 │
 ├─ [2] auth                 lookup user in SQLite, verify active
 │        └─ fail ──────────────────────────────────► error_response ─┐
 │                                                                     │
 ├─ [3] rbac                 check role is valid                       │
 │        └─ fail ──────────────────────────────────► error_response ─┤
 │                                                                     │
 ├─ [4] classify             Groq llama-3.1-8b → query_type label      │
 │                                                                     │
 ├─ [5] rewrite              Groq llama-3.1-8b → 3 variants + HyDE    │
 │                                                                     │
 ├─ [6] search               FAISS semantic + BM25 + RRF fusion        │
 │        └─ no results ────────────────────────────► generate ──────┐ │
 │                                                                   │ │
 ├─ [7] rbac_filter          drop chunks user cannot see             │ │
 │        └─ all filtered ──────────────────────────► generate ──────┤ │
 │                                                                   │ │
 ├─ [8] rerank               cross-encoder re-scores chunks          │ │
 │                                                                   │ │
 ├─ [9] assemble_context     token-budgeted context window           │ │
 │                                                                   │ │
 ├─[10] generate  ◄──────────────────────────────────────────────────┘ │
 │                           Groq llama-3.3-70b → answer text          │
 │                                                                     │
 ├─[11] format_citations     structured source list                    │
 │                                                                     │
 ├─[12] stop_timer ◄──────────────────────────────────────────────────-┘
 │                           record end timestamp
 │
 ├─[13] audit                write to audit_logs in SQLite
 │
 ▼
QueryState { response, citations, confidence, latency_ms }
 │
 ▼
HTTP Response JSON
```

---

## 8. Tech Stack Summary

| Component | Technology | Notes |
|---|---|---|
| API framework | FastAPI | Async, automatic Swagger UI at `/docs` |
| Auth | JWT (python-jose) + bcrypt (passlib) | HS256, configurable expiry |
| Pipeline orchestration | LangGraph | Compiled DAG, conditional edges |
| LLM (generation) | Groq `llama-3.3-70b-versatile` | Replaces Citi Stellar API for POC |
| LLM (routing/classify) | Groq `llama-3.1-8b-instant` | Cheap fast calls for classification/rewriting |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Local, 384-dim, no API key needed |
| Vector DB | FAISS `IndexFlatIP` | In-memory, file-persisted |
| Keyword search | BM25Okapi (`rank-bm25`) | Hybrid search partner |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Local cross-encoder, no API cost |
| Metadata / Audit | SQLite (WAL mode) | Same schema as roadmap's PostgreSQL |
| PDF parsing | PyMuPDF + pdfplumber + pytesseract | Native text + OCR fallback + tables |
| DOCX parsing | python-docx | Paragraph extraction |
| Token counting | tiktoken | cl100k_base encoding |
| Enterprise connectors | Stubs only | SharePoint, Confluence, Jira, Outlook |
