"""
Setup script: initialize the database and create default users.
Run once before starting the API server.

Usage:
    python scripts/setup_db.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.storage.database import init_db
from src.api.auth import register_user
from rich.console import Console

console = Console()


def setup():
    console.print("[bold blue]Banking Chatbot POC — DB Setup[/bold blue]")
    console.print("=" * 50)

    # Initialize database schema
    init_db()
    console.print("[green]✓[/green] Database schema initialized")

    # Create default users (one per role)
    default_users = [
        ("admin",      "admin123!",      "admin",      "IT"),
        ("analyst1",   "analyst123!",    "analyst",    "Operations"),
        ("ops_lead",   "opsLead123!",    "operations", "Operations"),
        ("compliance1","comply123!",     "compliance", "Compliance"),
    ]

    console.print("\n[bold]Creating default users...[/bold]")
    for username, password, role, dept in default_users:
        try:
            user = register_user(username, password, role, dept)
            console.print(f"  [green]✓[/green] {username} ({role}) — ID: {user['user_id']}")
        except Exception as e:
            # User may already exist from a previous setup run
            console.print(f"  [yellow]~[/yellow] {username}: {e}")

    console.print("\n[bold green]Setup complete![/bold green]")
    console.print("\nDefault credentials:")
    console.print("  Admin      : admin / admin123!")
    console.print("  Analyst    : analyst1 / analyst123!")
    console.print("  Operations : ops_lead / opsLead123!")
    console.print("  Compliance : compliance1 / comply123!")
    console.print("\n[yellow]Change all passwords before production use![/yellow]")


if __name__ == "__main__":
    setup()
