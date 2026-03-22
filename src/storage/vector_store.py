"""FAISS-backed vector store with BM25 hybrid search support.
Uses local sentence-transformers for embeddings (no API key required).
"""
import os
import pickle
from pathlib import Path
from typing import Optional
import numpy as np

import faiss
from rank_bm25 import BM25Okapi

from src.config import settings

FAISS_BIN = f"{settings.faiss_index_path}.bin"
META_PKL  = f"{settings.faiss_index_path}_meta.pkl"
BM25_PKL  = f"{settings.faiss_index_path}_bm25.pkl"

EMBEDDING_DIM = settings.embedding_dim  # 384 for all-MiniLM-L6-v2

# Lazy-loaded embedding model
_embedder = None


def _get_embedder():
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer
        print(f"[VectorStore] Loading embedding model '{settings.embedding_model}'...")
        _embedder = SentenceTransformer(settings.embedding_model)
        print("[VectorStore] Embedding model loaded.")
    return _embedder


class VectorStore:
    """In-memory FAISS index with file persistence and BM25 companion."""

    def __init__(self):
        Path(settings.faiss_index_path).parent.mkdir(parents=True, exist_ok=True)
        self._load_or_init()

    # ── Init / Persistence ─────────────────────────────────────────────────────

    def _load_or_init(self):
        if os.path.exists(FAISS_BIN) and os.path.exists(META_PKL):
            self.index = faiss.read_index(FAISS_BIN)
            with open(META_PKL, "rb") as f:
                self.metadata = pickle.load(f)   # list[dict]
            self.chunk_ids = [m["chunk_id"] for m in self.metadata]
            self.texts     = [m["text"] for m in self.metadata]
        else:
            self.index    = faiss.IndexFlatIP(EMBEDDING_DIM)  # inner-product (cosine on normalised vecs)
            self.metadata = []
            self.chunk_ids = []
            self.texts     = []

        if os.path.exists(BM25_PKL):
            with open(BM25_PKL, "rb") as f:
                self.bm25 = pickle.load(f)
        else:
            self.bm25 = None

    def save(self):
        faiss.write_index(self.index, FAISS_BIN)
        with open(META_PKL, "wb") as f:
            pickle.dump(self.metadata, f)
        if self.bm25 is not None:
            with open(BM25_PKL, "wb") as f:
                pickle.dump(self.bm25, f)

    def _rebuild_bm25(self):
        if self.texts:
            tokenized = [t.lower().split() for t in self.texts]
            self.bm25 = BM25Okapi(tokenized)
        else:
            self.bm25 = None

    # ── Embedding ──────────────────────────────────────────────────────────────

    def embed_texts(self, texts: list[str]) -> np.ndarray:
        """Embed a list of texts locally using sentence-transformers."""
        embedder = _get_embedder()
        vecs = embedder.encode(texts, convert_to_numpy=True, show_progress_bar=False).astype("float32")
        faiss.normalize_L2(vecs)
        return vecs

    def embed_query(self, query: str) -> np.ndarray:
        return self.embed_texts([query])

    # ── Add chunks ─────────────────────────────────────────────────────────────

    def add_chunks(self, chunks: list[dict]):
        """
        chunks: list of {chunk_id, text, source_name, source_type, page_number, section}
        """
        if not chunks:
            return

        # Skip already-indexed chunk_ids
        existing = set(self.chunk_ids)
        new_chunks = [c for c in chunks if c["chunk_id"] not in existing]
        if not new_chunks:
            return

        texts = [c["text"] for c in new_chunks]
        vecs  = self.embed_texts(texts)

        self.index.add(vecs)
        for chunk, vec in zip(new_chunks, vecs):
            self.metadata.append({
                "chunk_id":    chunk["chunk_id"],
                "text":        chunk["text"],
                "source_name": chunk.get("source_name", ""),
                "source_type": chunk.get("source_type", ""),
                "page_number": chunk.get("page_number"),
                "section":     chunk.get("section"),
            })
            self.chunk_ids.append(chunk["chunk_id"])
            self.texts.append(chunk["text"])

        self._rebuild_bm25()
        self.save()

    # ── Semantic search ────────────────────────────────────────────────────────

    def semantic_search(self, query: str, top_k: int = 20) -> list[dict]:
        """Return top_k results with score and metadata."""
        if self.index.ntotal == 0:
            return []
        q_vec = self.embed_query(query)
        k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(q_vec, k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            meta = self.metadata[idx].copy()
            meta["semantic_score"] = float(score)
            results.append(meta)
        return results

    # ── BM25 search ───────────────────────────────────────────────────────────

    def bm25_search(self, query: str, top_k: int = 20) -> list[dict]:
        """Return top_k BM25 results."""
        if self.bm25 is None or not self.texts:
            return []
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            if scores[idx] == 0:
                continue
            meta = self.metadata[idx].copy()
            meta["bm25_score"] = float(scores[idx])
            results.append(meta)
        return results

    # ── Hybrid search (RRF) ────────────────────────────────────────────────────

    def hybrid_search(self, query: str, top_k: int = 20) -> list[dict]:
        """Reciprocal Rank Fusion of semantic + BM25 results."""
        semantic_results = self.semantic_search(query, top_k=top_k * 2)
        bm25_results     = self.bm25_search(query, top_k=top_k * 2)

        k_rrf = 60  # RRF constant
        rrf_scores: dict[str, float] = {}
        chunk_meta: dict[str, dict]  = {}

        for rank, res in enumerate(semantic_results):
            cid = res["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0) + 1 / (k_rrf + rank + 1)
            chunk_meta[cid] = res

        for rank, res in enumerate(bm25_results):
            cid = res["chunk_id"]
            rrf_scores[cid] = rrf_scores.get(cid, 0) + 1 / (k_rrf + rank + 1)
            if cid not in chunk_meta:
                chunk_meta[cid] = res

        ranked = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        for cid, rrf_score in ranked:
            meta = chunk_meta[cid].copy()
            meta["rrf_score"] = rrf_score
            results.append(meta)
        return results

    def get_chunk_by_id(self, chunk_id: str) -> Optional[dict]:
        for m in self.metadata:
            if m["chunk_id"] == chunk_id:
                return m
        return None

    @property
    def total_chunks(self) -> int:
        return self.index.ntotal


# Singleton
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
