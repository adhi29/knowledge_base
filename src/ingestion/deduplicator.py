"""Content-hash-based deduplication using SQLite."""
from src.storage.database import hash_exists
from src.ingestion.processors.chunker import Chunk


def deduplicate_chunks(chunks: list[Chunk]) -> tuple[list[Chunk], int]:
    """
    Filter out chunks whose content_hash already exists in the DB.
    Returns (new_chunks, skipped_count).
    """
    new_chunks = []
    skipped = 0
    for chunk in chunks:
        if hash_exists(chunk.content_hash):
            skipped += 1
        else:
            new_chunks.append(chunk)
    return new_chunks, skipped
