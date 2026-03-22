"""Semantic chunker with sliding window and section-aware splitting."""
import hashlib
import re
import uuid
from dataclasses import dataclass, field
from typing import Optional

from src.config import settings


@dataclass
class Chunk:
    chunk_id: str
    source_id: str
    source_name: str
    source_type: str
    source_path: str
    text: str
    content_hash: str
    chunk_index: int
    page_number: Optional[int] = None
    section: Optional[str] = None
    allowed_roles: list[str] = field(default_factory=list)
    sensitivity_level: str = "internal"


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode()).hexdigest()


def _make_chunk_id(source_id: str, chunk_index: int) -> str:
    return hashlib.md5(f"{source_id}:{chunk_index}".encode()).hexdigest()


def _detect_section(text: str) -> Optional[str]:
    """Try to detect a section header from the first line."""
    first_line = text.strip().split("\n")[0].strip()
    if len(first_line) < 80 and re.match(r"^[A-Z0-9#]", first_line):
        return first_line[:120]
    return None


def _split_into_sentences(text: str) -> list[str]:
    """Basic sentence splitter that preserves newlines."""
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(
    text: str,
    source_id: str,
    source_name: str,
    source_type: str,
    source_path: str,
    allowed_roles: list[str],
    sensitivity_level: str = "internal",
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
    page_number: Optional[int] = None,
    start_index: int = 0,
) -> list[Chunk]:
    """
    Sliding-window token-approximate chunker.
    Uses word count as a proxy for token count (≈ 0.75 tokens/word average).
    """
    chunk_size = chunk_size or settings.chunk_size
    chunk_overlap = chunk_overlap or settings.chunk_overlap

    # Approx words for target chunk (512 tokens ≈ 384 words)
    words_per_chunk = int(chunk_size * 0.75)
    overlap_words   = int(chunk_overlap * 0.75)

    words = text.split()
    if not words:
        return []

    chunks: list[Chunk] = []
    i = 0
    chunk_index = start_index

    while i < len(words):
        window = words[i : i + words_per_chunk]
        chunk_text_str = " ".join(window).strip()

        if not chunk_text_str:
            break

        section = _detect_section(chunk_text_str)
        c_hash = _content_hash(chunk_text_str)
        c_id   = _make_chunk_id(source_id, chunk_index)

        chunks.append(Chunk(
            chunk_id=c_id,
            source_id=source_id,
            source_name=source_name,
            source_type=source_type,
            source_path=source_path,
            text=chunk_text_str,
            content_hash=c_hash,
            chunk_index=chunk_index,
            page_number=page_number,
            section=section,
            allowed_roles=allowed_roles,
            sensitivity_level=sensitivity_level,
        ))

        chunk_index += 1
        step = max(1, words_per_chunk - overlap_words)
        i += step

    return chunks


def chunk_document(raw_doc) -> list[Chunk]:
    """
    Chunk a RawDocument, respecting page boundaries if available.
    """
    from src.ingestion.connectors.base import RawDocument

    all_chunks: list[Chunk] = []
    idx = 0

    if raw_doc.pages:
        for page in raw_doc.pages:
            page_chunks = chunk_text(
                text=page["text"],
                source_id=raw_doc.source_id,
                source_name=raw_doc.source_name,
                source_type=raw_doc.source_type,
                source_path=raw_doc.source_path,
                allowed_roles=raw_doc.allowed_roles,
                sensitivity_level=raw_doc.sensitivity_level,
                page_number=page.get("page_num"),
                start_index=idx,
            )
            all_chunks.extend(page_chunks)
            idx += len(page_chunks)
    else:
        # Plain text, no page info
        plain_chunks = chunk_text(
            text=raw_doc.content,
            source_id=raw_doc.source_id,
            source_name=raw_doc.source_name,
            source_type=raw_doc.source_type,
            source_path=raw_doc.source_path,
            allowed_roles=raw_doc.allowed_roles,
            sensitivity_level=raw_doc.sensitivity_level,
            start_index=0,
        )
        all_chunks.extend(plain_chunks)

    return all_chunks
