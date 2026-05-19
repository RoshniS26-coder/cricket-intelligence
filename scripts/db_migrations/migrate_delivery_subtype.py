"""
Idempotent migration: add swing_direction, swing_type, spin_direction,
ball_age_phase columns to the existing `balls` table.

Safe to run multiple times. All new columns default to 'unknown' so existing
rows remain valid.

Usage:
    python scripts/migrate_delivery_subtype.py
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()

NEW_COLUMNS = {
    "swing_direction": "TEXT DEFAULT 'unknown'",
    "swing_type":      "TEXT DEFAULT 'unknown'",
    "spin_direction":  "TEXT DEFAULT 'unknown'",
    "ball_age_phase":  "TEXT DEFAULT 'unknown'",
}


def migrate() -> int:
    """Add missing columns. Returns the number of columns added."""
    url = os.getenv("DATABASE_URL", "sqlite:///./data/cricket_intelligence.db")
    engine = create_engine(url)

    added = 0
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(balls)")).fetchall()}
        for col, ddl in NEW_COLUMNS.items():
            if col in existing:
                console.print(f"  [dim]·[/dim] {col} already present, skipping")
                continue
            conn.execute(text(f"ALTER TABLE balls ADD COLUMN {col} {ddl}"))
            console.print(f"  [green]+[/green] added column: [cyan]{col}[/cyan]")
            added += 1

    console.print(f"[bold green]✓ migration complete[/bold green] — {added} column(s) added")
    return added


if __name__ == "__main__":
    migrate()
