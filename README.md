<div align="center">

# 🏦 CITI BRAIN
### AI-Powered Banking Knowledge Chatbot — RAG POC

**Built for Citi Banking Operations Teams**
Virtusa AI Centre of Excellence · 16-Week Proof of Concept

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-FF6B6B)](https://langchain-ai.github.io/langgraph/)
[![Groq](https://img.shields.io/badge/LLM-Groq%20Llama%203-F55036?logo=meta&logoColor=white)](https://groq.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

</div>

---

## 📋 Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Solution Overview](#2-solution-overview)
3. [Key Features](#3-key-features)
4. [System Architecture](#4-system-architecture)
5. [Pipeline Deep-Dive](#5-pipeline-deep-dive)  
   5a. [Ingestion Pipeline](#5a-ingestion-pipeline)  
   5b. [Query & Answer Pipeline](#5b-query--answer-pipeline)
6. [Security & Access Control](#6-security--access-control)
7. [Database Schema](#7-database-schema)
8. [API Reference](#8-api-reference)
9. [Tech Stack](#9-tech-stack)
10. [Quick Start](#10-quick-start)
11. [Demo Guide](#11-demo-guide)
12. [Sample Interactions](#12-sample-interactions)
13. [Performance Benchmarks](#13-performance-benchmarks)
14. [Implementation Status & Roadmap](#14-implementation-status--roadmap)

---

## 1. Problem Statement

Banking operations staff at Citi regularly need to look up information across hundreds of internal policy documents, SOPs, and compliance guidelines. The current process involves:

- Manually searching SharePoint / Confluence for relevant documents
- Calling senior staff for procedural questions
- Risk of referencing outdated policy versions
- No audit trail of information lookups

**This results in operational delays, inconsistent answers, and compliance risk.**

---

## 2. Solution Overview

**CITI BRAIN** is a Retrieval-Augmented Generation (RAG) chatbot that lets operations staff query internal knowledge in plain English and instantly receive precise, cited answers grounded in current documents.

```
"How do I initiate a wire transfer above $100K?"
        ↓
  CITI BRAIN retrieves the exact SOP section,
  cites the source, and answers in under 5 seconds.
```

### Core Design Principles

| Principle | How We Achieve It |
|---|---|
| **Accuracy** | Answers strictly grounded in retrieved documents — LLM cannot hallucinate beyond context |
| **Security** | Every response filtered by user role and document sensitivity level |
| **Speed** | Greeting short-circuit, compiled LangGraph DAG, batch embedding |
| **Auditability** | Every query, user, retrieved chunk, and response logged to immutable audit table |
| **Extensibility** | Modular node-based pipeline — new nodes without touching existing code |

---

## 3. Key Features

- 🔍 **Hybrid Search** — FAISS semantic search + BM25 keyword search, fused with Reciprocal Rank Fusion (RRF)
- 🔁 **Query Rewriting** — Multi-query expansion + HyDE (Hypothetical Document Embedding) for higher recall
- 🎯 **Cross-Encoder Reranking** — Local `ms-marco-MiniLM` reranker for precision beyond bi-encoder retrieval
- 🛡️ **Double RBAC** — Role checked at login (JWT) AND at retrieval (per-chunk sensitivity level)
- 🚦 **Content Safety Filter** — Blocks jailbreak / harmful queries before any LLM call
- 👋 **Greeting Short-Circuit** — Casual messages skip the entire retrieval pipeline (instant response)
- 💬 **Multi-Turn Memory** — Last 3 conversation turns included in every context window
- 📚 **Structured Citations** — Every answer lists exact source file, page number, and section
- 📝 **Persistent Chat History** — Sessions stored in SQLite; full history retrievable via API
- 🔄 **Auto-Sync Scheduler** — APScheduler polls live connectors (Confluence, Jira) every N hours

---

## 4. System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT LAYER                             │
│   React/Vite Frontend  ←──→  FastAPI REST API (port 8000)      │
└────────────────────────────────┬────────────────────────────────┘
                                 │  JWT Bearer Token
                                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH PIPELINE                           │
│                                                                 │
│   Auth → RBAC → ContentFilter → Classify                       │
│                                    ↓          ↓                │
│                              Greeting    Rewrite → Search      │
│                              (short-     → RBACFilter → Rerank │
│                              circuit)    → Context → Generate  │
│                                    ↓          ↓                │
│                              StopTimer → Audit → Response      │
└────────────────────┬────────────────────────────┬──────────────┘
                     │                            │
          ┌──────────▼──────────┐    ┌────────────▼────────────┐
          │   VECTOR STORE      │    │     METADATA STORE      │
          │  FAISS (semantic)   │    │  SQLite WAL (chatbot.db) │
          │  BM25  (keyword)    │    │  users, chunks, audit    │
          └─────────────────────┘    └─────────────────────────┘
```

### Directory Structure

```
knowledge_base/
├── src/
│   ├── api/
│   │   ├── main.py               # FastAPI app + CORS + lifespan
│   │   ├── auth.py               # JWT encode/decode, bcrypt, OAuth2
│   │   ├── models.py             # Pydantic request/response schemas
│   │   └── routes/
│   │       ├── auth_routes.py    # /api/auth/login, /register, /me
│   │       ├── chat.py           # /api/chat — runs full pipeline
│   │       ├── chat_history.py   # /api/chat/history/{session_id}
│   │       └── admin.py          # /api/admin/ingest, /stats, /sync
│   ├── query/
│   │   ├── graph.py              # LangGraph DAG builder + run_query()
│   │   ├── state.py              # QueryState Pydantic model (shared state)
│   │   └── nodes/
│   │       ├── auth_node.py
│   │       ├── rbac_node.py
│   │       ├── content_filter_node.py
│   │       ├── classifier_node.py
│   │       ├── query_router_node.py
│   │       ├── hybrid_search_node.py
│   │       ├── rbac_filter_node.py
│   │       ├── reranker_node.py
│   │       ├── context_assembly_node.py
│   │       ├── llm_generation_node.py
│   │       ├── citation_formatter_node.py
│   │       └── audit_log_node.py
│   ├── ingestion/
│   │   ├── pipeline.py           # IngestionPipeline orchestrator
│   │   ├── deduplicator.py       # SHA-256 content hash dedup
│   │   ├── connectors/
│   │   │   ├── file_connector.py # PDF/DOCX/TXT/MD parser
│   │   │   └── live_connectors.py# Confluence, Jira, Outlook, SharePoint
│   │   └── processors/
│   │       └── chunker.py        # Semantic chunker (512 tokens)
│   ├── storage/
│   │   ├── vector_store.py       # FAISS + BM25 singleton
│   │   └── database.py           # SQLite helpers (478 lines)
│   └── config.py                 # Pydantic-settings from .env
├── frontend/                     # React + Vite + TypeScript
├── scripts/
│   ├── setup_db.py               # One-time DB init + seed users
│   ├── ingest_sample.py          # Ingest documents from a directory
│   ├── demo.py                   # End-to-end smoke test (this session)
│   └── watch_and_ingest.py       # Watchdog: auto-ingest on file change
├── data/
│   ├── chatbot.db                # SQLite database
│   ├── faiss_index.bin           # FAISS vector index
│   ├── faiss_index_meta.pkl      # FAISS position → chunk metadata map
│   ├── faiss_index_bm25.pkl      # Serialised BM25Okapi object
│   └── sample_docs/              # Demo documents (3 files)
├── ARCHITECTURE.md               # Full technical architecture
├── requirements.txt
└── .env.example
```

---

## 5. Pipeline Deep-Dive

### 5a. Ingestion Pipeline

Triggered manually via script or via `POST /api/admin/ingest` (admin role only).

```
Files / Docs
    │
    ▼ Step 1 — FileConnector
    │  • PDF  → PyMuPDF (native text) + pytesseract (OCR fallback for scanned pages)
    │           + pdfplumber (table extraction)
    │  • DOCX → python-docx (paragraph extraction)
    │  • TXT/MD → raw text read
    │  Output: RawDocument(text, pages, tables, metadata)
    │
    ▼ Step 2 — Chunker
    │  • Splits text into ~512-token chunks, respecting page boundaries
    │  • Each chunk gets: chunk_id (UUID), chunk_index, content_hash (SHA-256)
    │  • Inherits allowed_roles and sensitivity_level from parent document
    │
    ▼ Step 3 — Deduplicator
    │  • Checks content_hash against SQLite text_chunks table
    │  • Existing hash → skip (no re-embedding, no extra cost)
    │  • New/changed hash → proceed to embedding
    │
    ▼ Step 4 — Embedding (batches of 50)
    │  • Model: sentence-transformers/all-MiniLM-L6-v2 (local, 384-dim, free)
    │  • Vectors L2-normalised → inner-product search ≡ cosine similarity
    │  • Stored in FAISS IndexFlatIP
    │
    ▼ Step 5 — Store
       • FAISS .bin + metadata .pkl + BM25 .pkl → disk
       • Full chunk metadata → SQLite text_chunks table
       • Ingestion log entry → SQLite ingestion_log table
```

### 5b. Query & Answer Pipeline

Every chat message runs through a compiled LangGraph DAG. State is a single immutable `QueryState` Pydantic object passed through each node — no global mutation.

```
User HTTP Request  →  FastAPI  →  Decode JWT  →  run_query()
                                                      │
                              ┌───────────────────────▼────────────────────────┐
                              │  LangGraph Compiled DAG                        │
                              │                                                │
Node 1  start_timer           │  Record start_time_ms                         │
Node 2  auth                  │  Lookup user in SQLite; verify is_active       │
          └─ fail ────────────┼──────────────────────────────► error_response  │
Node 3  rbac                  │  Validate role ∈ {analyst,ops,compliance,admin}│
          └─ fail ────────────┼──────────────────────────────► error_response  │
Node 4  content_filter        │  LLM prompt: block jailbreaks / harmful queries│
          └─ blocked ─────────┼──────────────────────────────► error_response  │
Node 5  classify              │  Groq llama-3.1-8b: classify into 6 types      │
          └─ greeting ────────┼────────────────────► greeting_response         │
Node 6  rewrite               │  Groq llama-3.1-8b: 3 alt phrasings + HyDE    │
Node 7  search                │  FAISS + BM25 → RRF fusion → raw_results       │
          └─ no results ──────┼──────────────────────────────► generate        │
Node 8  rbac_filter           │  Drop chunks user cannot see (sensitivity lvl) │
          └─ all filtered ────┼──────────────────────────────► generate        │
Node 9  rerank                │  cross-encoder/ms-marco-MiniLM → precision sort│
Node 10 assemble_context      │  Token budget 6000; reserve 800 for history    │
Node 11 generate              │  Groq llama-3.3-70b-versatile; temp=0.1        │
Node 12 format_citations      │  Dedup & structure source list                 │
Node 13 stop_timer            │  Record end_time_ms; compute latency_ms        │
Node 14 audit                 │  Append-only write to audit_logs table          │
                              └────────────────────────────────────────────────┘
                                                      │
                              QueryState { response, citations, confidence, latency_ms }
                                                      │
                                              HTTP JSON Response
```

#### Query Rewriting Detail

For every non-greeting query, two rewriting strategies run in parallel:

| Strategy | What it does | Why it helps |
|---|---|---|
| **Multi-query expansion** | Asks LLM for 3 alternative phrasings; expands acronyms | Catches documents using different terminology |
| **HyDE** | Asks LLM to write a hypothetical answer paragraph | Hypothetical answer uses same language as real docs → better embedding match |

All variants (original + 3 expanded + 1 HyDE) are deduplicated → 3–5 search queries total.

#### Hybrid Search Detail

For each query variant:
1. **Semantic**: Embed query → FAISS inner-product search → top-K by cosine similarity
2. **Keyword**: BM25Okapi over all chunk texts → top-K by BM25 score
3. **RRF Fusion**: `score += 1 / (60 + rank)` for each ranked list → merge across all variants

Final ranking: highest RRF score per `chunk_id` → `raw_results`.

#### Confidence Score Calculation

```
top_reranker_score ∈ [-10, +10]  (raw cross-encoder output)
confidence = (top_reranker_score + 10) / 20   → normalised to [0, 1]
```

---

## 6. Security & Access Control

### Authentication Flow

```
Client                      FastAPI                     SQLite
  │                             │                          │
  │── POST /api/auth/login ──►  │                          │
  │   {username, password}      │── get_user_by_username ─►│
  │                             │◄─ {user_id, hash, role} ─│
  │                             │── bcrypt.verify()        │
  │◄── {access_token, role} ───  │── create_access_token() │
  │                             │   JWT {sub, role, exp}   │
  │── POST /api/chat ──────────►│                          │
  │   Authorization: Bearer JWT │── decode_token()         │
  │                             │── TokenData(user_id,role)│
```

### RBAC Matrix

| Role | Public | Internal | Confidential | Restricted |
|---|:---:|:---:|:---:|:---:|
| `analyst` | ✅ | ✅ | ❌ | ❌ |
| `operations` | ✅ | ✅ | ✅ | ❌ |
| `compliance` | ✅ | ✅ | ✅ | ✅ |
| `admin` | ✅ | ✅ | ✅ | ✅ |

**Double enforcement:**
- **Pre-retrieval**: Document tagged with `allowed_roles` at ingest time
- **Post-retrieval**: `rbac_filter` node checks `sensitivity_level` per chunk at query time

---

## 7. Database Schema

SQLite database (`data/chatbot.db`) in WAL mode for concurrent read access.

| Table | Key Columns | Purpose |
|---|---|---|
| `text_chunks` | chunk_id, content_hash, sensitivity_level, allowed_roles | Document chunk metadata + RBAC |
| `users` | user_id, username, hashed_password, role, is_active | User accounts |
| `role_permissions` | role, sensitivity_level, can_access | RBAC matrix (seeded on init) |
| `user_sessions` | session_id, user_id, last_active | Session tracking |
| `audit_logs` | user_id, query, query_type, retrieved_chunks, latency_ms | Immutable audit trail |
| `ingestion_log` | source_path, status, chunks_created | Ingestion run history |
| `chat_sessions` | session_id, user_id, title | Persistent chat sessions |
| `chat_messages` | message_id, session_id, role, content, metadata | Full message history + citations |
| `connector_sync_state` | source_key, last_synced, docs_synced | Incremental sync tracking |

---

## 8. API Reference

Full interactive Swagger UI: **http://localhost:8000/docs**

### Authentication

```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=analyst1&password=analyst123!
```
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user_id": "uuid",
  "username": "analyst1",
  "role": "analyst"
}
```

### Chat

```http
POST /api/chat
Authorization: Bearer <token>
Content-Type: application/json

{
  "query": "How do I initiate a wire transfer above $100,000?",
  "session_id": "optional-uuid",
  "chat_history": []
}
```
```json
{
  "response": "To initiate a wire transfer above $100,000...",
  "citations": [
    {
      "index": 1,
      "source_name": "wire_transfer_sop.txt",
      "page_number": 2,
      "section": "Dual-Control Approval",
      "relevance_score": 0.923
    }
  ],
  "query_type": "procedural",
  "confidence": 0.77,
  "latency_ms": 4051,
  "session_id": "uuid"
}
```

### All Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/api/auth/login` | None | Login — returns JWT |
| `POST` | `/api/auth/register` | None | Register new user |
| `GET` | `/api/auth/me` | JWT | Current user info |
| `POST` | `/api/chat` | JWT | Send chat message — runs full pipeline |
| `GET` | `/api/chat/history/{session_id}` | JWT | Retrieve message history |
| `GET` | `/api/chat/sessions` | JWT | List user's chat sessions |
| `DELETE` | `/api/chat/sessions/{session_id}` | JWT | Delete a session |
| `POST` | `/api/admin/ingest` | JWT (admin) | Trigger document ingestion |
| `GET` | `/api/admin/stats` | JWT (admin) | System statistics |
| `GET` | `/api/admin/audit-logs` | JWT (admin) | Recent audit log entries |
| `POST` | `/api/admin/sync/{source}` | JWT (admin) | Trigger live connector sync |
| `GET` | `/health` | None | Health check |

---

## 9. Tech Stack

| Layer | Component | Technology | Notes |
|---|---|---|---|
| **API** | Framework | FastAPI 0.115+ | Async, auto Swagger UI |
| **API** | Auth | python-jose + passlib/bcrypt | HS256 JWT |
| **API** | Server | Uvicorn (standard) | ASGI, production-ready |
| **Pipeline** | Orchestration | LangGraph 0.2+ | Compiled DAG, conditional edges |
| **LLM** | Generation | Groq `llama-3.3-70b-versatile` | High-quality, low-latency |
| **LLM** | Routing | Groq `llama-3.1-8b-instant` | Fast cheap calls for classify/rewrite |
| **Embeddings** | Encoder | `all-MiniLM-L6-v2` (local) | 384-dim, no API cost |
| **Vector DB** | Index | FAISS `IndexFlatIP` | In-memory, cosine similarity |
| **Keyword** | Search | BM25Okapi (`rank-bm25`) | Hybrid search partner |
| **Reranker** | Cross-encoder | `ms-marco-MiniLM-L-6-v2` (local) | Precision scoring, no API cost |
| **Database** | Metadata & Audit | SQLite (WAL mode) | Zero-config, 7-table schema |
| **Document** | PDF | PyMuPDF + pdfplumber + pytesseract | Native text + OCR + tables |
| **Document** | DOCX | python-docx | Paragraph extraction |
| **Token** | Counting | tiktoken (cl100k_base) | GPT-4 compatible token budget |
| **Scheduler** | Auto-sync | APScheduler | Background connector polling |
| **Frontend** | UI | React + Vite + TypeScript | Chat interface |
| **Connectors** | Enterprise | Confluence, Jira, Outlook, SharePoint | Stubs ready for credentials |

---

## 10. Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (frontend only)
- Groq API key — free at [console.groq.com/keys](https://console.groq.com/keys)

### Setup (5 steps)

```bash
# 1. Create virtual environment
cd knowledge_base
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# → Edit .env: set GROQ_API_KEY=gsk_your_key_here

# 4. Initialise database and seed demo users
python scripts/setup_db.py

# 5. Ingest sample documents
python scripts/ingest_sample.py
```

### Run

```bash
# API server (required)
uvicorn src.api.main:app --reload --port 8000

# Frontend (optional)
cd frontend && npm install && npm run dev
```

| Service | URL |
|---|---|
| API (Swagger UI) | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |
| Frontend | http://localhost:5173 |

---

## 11. Demo Guide

### Default Credentials

| Username | Password | Role | Document Access |
|---|---|---|---|
| `admin` | `admin123!` | admin | All documents |
| `analyst1` | `analyst123!` | analyst | Public + internal |
| `ops_lead` | `opsLead123!` | operations | Public + internal + confidential |
| `compliance1` | `comply123!` | compliance | All except restricted |

> ⚠️ For demo only — change all passwords before any real deployment.

### Automated End-to-End Test

```bash
# With API server running:
python scripts/demo.py
```

Outputs 3 representative queries with full response details. Must exit with code 0.

### Manual Demo (Swagger UI)

1. Open **http://localhost:8000/docs**
2. Click `POST /api/auth/login` → **Try it out** → enter `analyst1 / analyst123!` → Execute
3. Copy the `access_token` value
4. Click **Authorize** (top right) → paste token
5. Click `POST /api/chat` → **Try it out** → send any question below

---

## 12. Sample Interactions

### Factual Query
> **Q:** "What is the daily wire transfer limit for standard operators?"
>
> **A:** The daily wire transfer limit for standard wire transfer operators (WTO) is $500,000 per transaction. Senior operators have a higher limit of $2,000,000 per transaction...
>
> **Citations:** `wire_transfer_sop.txt p.1` | Confidence: 0.77

### Procedural Query
> **Q:** "How do I initiate a wire transfer?"
>
> **A:** To initiate a wire transfer, follow these steps:
> 1. Ensure you are an authorised wire transfer operator (WTO) with active Flexcube access...
> 10. Send confirmation email to client within 15 minutes of submission.
>
> **Citations:** `wire_transfer_sop.txt p.2` `new_joiner_guide.txt p.1` | Confidence: 0.77

### RBAC Demo — Access Denied
> **User:** `analyst1` (role: analyst)
>
> **Q:** "What are the KYC requirements for high-risk customers?"
>
> **A:** *You do not have access to view this content.* (kyc_policy.txt is confidential — requires operations role or higher)

### Greeting Short-Circuit
> **Q:** "Hello!"
>
> **A:** "Hello there, it's great to chat with you! How's your day going so far?"
>
> **Latency: 848ms** (no retrieval, no embedding, no reranking)

---

## 13. Performance Benchmarks

*Measured on Apple M2, 16 GB RAM, Groq free-tier API.*

| Scenario | Latency | Notes |
|---|---|---|
| Greeting (short-circuit) | ~850 ms | One Groq call, no retrieval |
| Warm query (model cached) | 3–6 s | 2 Groq calls + FAISS + reranker |
| Cold start (first query) | 45–60 s | Downloads + loads embedding models |
| Document ingest (3 files) | ~15 s | First run; subsequent: near-instant (dedup) |

> **Cold start only happens once.** After the embedding model (`all-MiniLM-L6-v2`) and reranker (`ms-marco-MiniLM-L-6-v2`) are cached locally, all subsequent queries run in 3–6 seconds.

---

## 14. Implementation Status & Roadmap

### ✅ Implemented

| Feature | Details |
|---|---|
| 13-node LangGraph RAG pipeline | Full pipeline with conditional routing |
| JWT authentication + RBAC | 4-role model, bcrypt passwords |
| Hybrid search (FAISS + BM25 + RRF) | Configurable weights via `.env` |
| Cross-encoder reranking | Local `ms-marco-MiniLM-L-6-v2` |
| Query classification | 6 types (factual, procedural, policy, exception, general, greeting) |
| Multi-query rewriting + HyDE | Improves retrieval recall |
| Greeting short-circuit | Instant response for casual messages |
| Content safety filter | Blocks jailbreak / harmful queries |
| Persistent chat history | Sessions + full message archive with citations |
| Audit logging | Append-only, every query logged |
| Auto-sync scheduler | APScheduler background job |
| PDF OCR fallback | pytesseract for scanned documents |
| Context token budgeting | 6K token window, 800 reserved for history |
| React + Vite frontend | Full UI with chat history sidebar |
| Admin API (ingest, stats, sync) | Role-gated admin endpoints |
| Enterprise connector stubs | Confluence, Jira, Outlook, SharePoint ready |

### 📋 Production Roadmap

| Feature | Priority | Effort |
|---|---|---|
| Wire enterprise connector credentials (Confluence/Jira) | High | Low |
| Migrate SQLite → PostgreSQL | High | Medium |
| PII redaction layer (before audit log) | High | Medium |
| Streaming responses (Server-Sent Events) | Medium | Low |
| Document version tracking (delta sync) | Medium | Medium |
| Horizontal scaling (Redis for FAISS sync) | Medium | High |
| Feedback loop (thumbs up/down → finetuning signal) | Low | Medium |
| Citi Stellar LLM integration (replace Groq) | High | Low |
