"""
Ingest sample documents into the knowledge base.
Run after setup_db.py.

Usage:
    python scripts/ingest_sample.py

    # Optionally specify a custom path:
    python scripts/ingest_sample.py --path /path/to/docs --role analyst operations --sensitivity internal
"""
import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import init_db
from src.ingestion.pipeline import ingest_directory
from rich.console import Console

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Ingest documents into the knowledge base")
    parser.add_argument("--path", default="data/sample_docs", help="Directory to ingest")
    parser.add_argument("--roles", nargs="+", default=["analyst", "operations", "compliance", "admin"],
                        help="Allowed roles for these documents")
    parser.add_argument("--sensitivity", default="internal",
                        choices=["public", "internal", "confidential", "restricted"],
                        help="Sensitivity level for these documents")
    parser.add_argument("--no-recursive", action="store_true", help="Do not recurse into subdirectories")
    args = parser.parse_args()

    console.print("[bold blue]Banking Chatbot POC — Document Ingestion[/bold blue]")
    console.print("=" * 50)
    console.print(f"Path       : {args.path}")
    console.print(f"Roles      : {args.roles}")
    console.print(f"Sensitivity: {args.sensitivity}")
    console.print()

    init_db()

    # Special handling: KYC policy is confidential (only operations + compliance + admin)
    kyc_path = os.path.join(args.path, "kyc_policy.txt")
    if os.path.exists(kyc_path):
        console.print("[yellow]→ Ingesting KYC policy as CONFIDENTIAL (operations, compliance, admin only)...[/yellow]")
        from src.ingestion.pipeline import ingest_file
        ingest_file(
            path=kyc_path,
            allowed_roles=["operations", "compliance", "admin"],
            sensitivity_level="confidential",
        )
        console.print()

    # Ingest everything else as internal
    console.print("[cyan]→ Ingesting remaining documents as INTERNAL...[/cyan]")
    summary = ingest_directory(
        path=args.path,
        allowed_roles=args.roles,
        sensitivity_level=args.sensitivity,
        recursive=not args.no_recursive,
    )

    console.print("\n[bold]Summary[/bold]")
    console.print(f"  Documents processed : {summary['documents_processed']}")
    console.print(f"  Chunks created      : {summary['chunks_created']}")
    console.print(f"  Chunks skipped      : {summary['chunks_skipped']} (deduplication)")
    if summary["errors"]:
        console.print(f"\n[red]Errors:[/red]")
        for e in summary["errors"]:
            console.print(f"  • {e}")


if __name__ == "__main__":
    main()
