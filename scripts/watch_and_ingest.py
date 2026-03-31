"""
Auto-ingestion file watcher.

Monitors a folder and automatically ingests any new file dropped into it.

Usage:
    python scripts/watch_and_ingest.py

    # Custom folder / roles:
    python scripts/watch_and_ingest.py --path data/sample_docs --roles analyst operations admin --sensitivity internal
"""
import sys
import os
import time
import argparse
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent
except ImportError:
    print("❌  watchdog not installed. Run:  pip install watchdog")
    sys.exit(1)

from rich.console import Console
from src.storage.database import init_db
from src.ingestion.pipeline import ingest_file

console = Console()

# File types the ingestion pipeline can handle
SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx", ".doc", ".csv", ".xlsx", ".png", ".jpg", ".jpeg"}

# Cooldown (seconds) before ingesting a file — avoids triggering while it's still being written
SETTLE_DELAY = 2.0


class IngestHandler(FileSystemEventHandler):
    def __init__(self, allowed_roles: list[str], sensitivity_level: str):
        super().__init__()
        self.allowed_roles = allowed_roles
        self.sensitivity_level = sensitivity_level
        # Track pending timers so we don't double-ingest
        self._pending: dict[str, threading.Timer] = {}

    def on_created(self, event: FileCreatedEvent):
        if event.is_directory:
            return
        path = event.src_path
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            console.print(f"[dim]  ⚠ Ignored (unsupported type): {os.path.basename(path)}[/dim]")
            return

        # Cancel any existing timer for this file (handles rapid writes)
        if path in self._pending:
            self._pending[path].cancel()

        timer = threading.Timer(SETTLE_DELAY, self._ingest, args=[path])
        self._pending[path] = timer
        timer.start()
        console.print(f"[yellow]  ⏳ Detected:[/yellow] {os.path.basename(path)} — ingesting in {SETTLE_DELAY}s...")

    def _ingest(self, path: str):
        self._pending.pop(path, None)
        filename = os.path.basename(path)
        console.print(f"\n[bold cyan]→ Ingesting:[/bold cyan] {filename}")
        try:
            summary = ingest_file(
                path=path,
                allowed_roles=self.allowed_roles,
                sensitivity_level=self.sensitivity_level,
            )
            new   = summary.get("chunks_created", 0)
            skip  = summary.get("chunks_skipped", 0)
            errs  = summary.get("errors", [])
            if errs:
                console.print(f"  [red]✗ Errors:[/red] {errs}")
            else:
                console.print(f"  [green]✓ Done:[/green] {new} new chunk(s), {skip} skipped (duplicates)")
        except Exception as exc:
            console.print(f"  [bold red]✗ Ingestion failed:[/bold red] {exc}")


def main():
    parser = argparse.ArgumentParser(description="Watch a folder and auto-ingest new files")
    parser.add_argument("--path",        default="data/sample_docs",  help="Folder to watch")
    parser.add_argument("--roles",       nargs="+",
                        default=["analyst", "operations", "compliance", "admin"],
                        help="Allowed roles for ingested documents")
    parser.add_argument("--sensitivity", default="internal",
                        choices=["public", "internal", "confidential", "restricted"],
                        help="Sensitivity level for ingested documents")
    args = parser.parse_args()

    watch_path = os.path.abspath(args.path)
    os.makedirs(watch_path, exist_ok=True)

    console.print("[bold blue]Banking Chatbot — Auto-Ingestion Watcher[/bold blue]")
    console.print("=" * 50)
    console.print(f"  Watching : [bold]{watch_path}[/bold]")
    console.print(f"  Roles    : {args.roles}")
    console.print(f"  Sensitivity: {args.sensitivity}")
    console.print(f"  Supported: {', '.join(SUPPORTED_EXTENSIONS)}")
    console.print()
    console.print("[green]✓ Ready — drop files into the folder above to ingest them automatically.[/green]")
    console.print("[dim]  Press Ctrl+C to stop.[/dim]\n")

    init_db()

    handler  = IngestHandler(allowed_roles=args.roles, sensitivity_level=args.sensitivity)
    observer = Observer()
    observer.schedule(handler, watch_path, recursive=True)
    observer.start()

    try:
        while observer.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping watcher...[/yellow]")
        observer.stop()

    observer.join()
    console.print("[bold]Watcher stopped.[/bold]")


if __name__ == "__main__":
    main()
