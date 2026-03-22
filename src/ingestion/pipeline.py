"""
Main ingestion pipeline.
Orchestrates: fetch → chunk → deduplicate → embed → store metadata
"""
import uuid
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from src.ingestion.connectors.base import BaseConnector, RawDocument
from src.ingestion.connectors.file_connector import FileConnector
from src.ingestion.processors.chunker import chunk_document, Chunk
from src.ingestion.deduplicator import deduplicate_chunks
from src.storage.vector_store import get_vector_store
from src.storage.database import upsert_chunk_metadata, write_ingestion_log, init_db

console = Console()


class IngestionPipeline:
    """
    Full ingestion pipeline:
    1. Fetch documents from connectors
    2. Chunk each document
    3. Deduplicate against existing store
    4. Embed new chunks and store in FAISS
    5. Save metadata to SQLite
    6. Log ingestion status
    """

    def __init__(self, connectors: Optional[list[BaseConnector]] = None):
        self.connectors = connectors or []
        self.vector_store = get_vector_store()

    def add_connector(self, connector: BaseConnector):
        self.connectors.append(connector)

    def run(self) -> dict:
        init_db()
        summary = {
            "documents_processed": 0,
            "chunks_created": 0,
            "chunks_skipped": 0,
            "errors": [],
        }

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        ) as progress:

            fetch_task = progress.add_task("[cyan]Fetching documents...", total=len(self.connectors))
            all_docs: list[RawDocument] = []

            for connector in self.connectors:
                try:
                    docs = connector.fetch()
                    all_docs.extend(docs)
                    console.print(f"  [green]✓[/green] Fetched {len(docs)} doc(s) from {type(connector).__name__}")
                except Exception as e:
                    err = f"{type(connector).__name__}: {e}"
                    summary["errors"].append(err)
                    console.print(f"  [red]✗[/red] {err}")
                finally:
                    progress.advance(fetch_task)

            chunk_task = progress.add_task("[yellow]Chunking documents...", total=len(all_docs))
            all_chunks: list[Chunk] = []

            for doc in all_docs:
                try:
                    chunks = chunk_document(doc)
                    all_chunks.extend(chunks)
                    console.print(f"  [green]✓[/green] {doc.source_name}: {len(chunks)} chunks")
                except Exception as e:
                    err = f"Chunking {doc.source_name}: {e}"
                    summary["errors"].append(err)
                    console.print(f"  [red]✗[/red] {err}")
                finally:
                    progress.advance(chunk_task)

            # Deduplicate
            new_chunks, skipped = deduplicate_chunks(all_chunks)
            summary["chunks_skipped"] = skipped
            console.print(f"\n[blue]Dedup:[/blue] {len(new_chunks)} new, {skipped} skipped")

            if new_chunks:
                embed_task = progress.add_task("[magenta]Embedding & storing...", total=len(new_chunks))

                # Batch embedding (50 chunks per batch to stay within API limits)
                BATCH_SIZE = 50
                for i in range(0, len(new_chunks), BATCH_SIZE):
                    batch = new_chunks[i : i + BATCH_SIZE]
                    try:
                        # Convert chunks to dicts for vector store
                        chunk_dicts = [
                            {
                                "chunk_id":    c.chunk_id,
                                "text":        c.text,
                                "source_name": c.source_name,
                                "source_type": c.source_type,
                                "page_number": c.page_number,
                                "section":     c.section,
                            }
                            for c in batch
                        ]
                        self.vector_store.add_chunks(chunk_dicts)

                        # Save metadata to SQLite
                        for c in batch:
                            upsert_chunk_metadata(
                                chunk_id=c.chunk_id,
                                source_id=c.source_id,
                                source_type=c.source_type,
                                source_name=c.source_name,
                                source_path=c.source_path,
                                content_hash=c.content_hash,
                                chunk_index=c.chunk_index,
                                allowed_roles=c.allowed_roles,
                                sensitivity_level=c.sensitivity_level,
                                page_number=c.page_number,
                                section=c.section,
                            )

                        summary["chunks_created"] += len(batch)
                        progress.advance(embed_task, len(batch))

                    except Exception as e:
                        err = f"Embedding batch {i//BATCH_SIZE + 1}: {e}"
                        summary["errors"].append(err)
                        console.print(f"  [red]✗[/red] {err}")

            summary["documents_processed"] = len(all_docs)

        # Log each document's ingestion
        for doc in all_docs:
            write_ingestion_log(
                log_id=str(uuid.uuid4()),
                source_path=doc.source_path,
                source_type=doc.source_type,
                status="success" if not any(doc.source_name in e for e in summary["errors"]) else "partial",
                chunks_created=sum(1 for c in new_chunks if c.source_id == doc.source_id),
            )

        console.print(f"\n[bold green]Ingestion complete![/bold green]")
        console.print(f"  Documents : {summary['documents_processed']}")
        console.print(f"  New chunks: {summary['chunks_created']}")
        console.print(f"  Skipped   : {summary['chunks_skipped']} (duplicates)")
        console.print(f"  Errors    : {len(summary['errors'])}")
        console.print(f"  Total in store: {self.vector_store.total_chunks}")

        return summary


def ingest_directory(
    path: str,
    allowed_roles: Optional[list[str]] = None,
    sensitivity_level: str = "internal",
    recursive: bool = True,
) -> dict:
    """Convenience function to ingest a local directory."""
    connector = FileConnector(
        path=path,
        allowed_roles=allowed_roles,
        sensitivity_level=sensitivity_level,
        recursive=recursive,
    )
    pipeline = IngestionPipeline(connectors=[connector])
    return pipeline.run()


def ingest_file(
    path: str,
    allowed_roles: Optional[list[str]] = None,
    sensitivity_level: str = "internal",
) -> dict:
    """Convenience function to ingest a single file."""
    return ingest_directory(path, allowed_roles, sensitivity_level, recursive=False)
