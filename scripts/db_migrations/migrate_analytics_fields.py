"""
Idempotent migration: add Tier-1 analytics enrichment columns to the `balls`
and `matches` tables.

Adds 8 columns to balls (shot_direction, dismissal_type, dismissal_fielder,
bowling_speed_kmph, bowler_crease, edge_type, phase, batsman_handedness)
and 2 columns to matches (match_date, day_or_night).

Safe to run multiple times. All new columns default to 'unknown' / 'none' /
NULL so existing rows remain valid.

Usage:
    python features/db_migrations/migrate_analytics_fields.py
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()

BALLS_NEW_COLUMNS = {
    "shot_direction":     "TEXT DEFAULT 'unknown'",
    "dismissal_type":     "TEXT DEFAULT 'none'",
    "dismissal_fielder":  "TEXT",
    "bowling_speed_kmph": "REAL",
    "bowler_crease":      "TEXT DEFAULT 'unknown'",
    "edge_type":          "TEXT DEFAULT 'none'",
    "phase":              "TEXT DEFAULT 'unknown'",
    "batsman_handedness": "TEXT DEFAULT 'unknown'",
}

MATCHES_NEW_COLUMNS = {
    "match_date":   "TEXT",
    "day_or_night": "TEXT",
}


def _add_columns(conn, table: str, new_cols: dict) -> int:
    """Add each new column if not already present. Returns count added."""
    existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})")).fetchall()}
    added = 0
    for col, ddl in new_cols.items():
        if col in existing:
            console.print(f"  [dim]·[/dim] {table}.{col} already present, skipping")
            continue
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
        console.print(f"  [green]+[/green] added column: [cyan]{table}.{col}[/cyan]")
        added += 1
    return added


def migrate() -> int:
    url = os.getenv("DATABASE_URL", "sqlite:///./data/cricket_intelligence.db")
    engine = create_engine(url)

    total = 0
    with engine.begin() as conn:
        console.print("[bold]Migrating balls table...[/bold]")
        total += _add_columns(conn, "balls", BALLS_NEW_COLUMNS)

        console.print("\n[bold]Migrating matches table...[/bold]")
        total += _add_columns(conn, "matches", MATCHES_NEW_COLUMNS)

    console.print(
        f"\n[bold green]✓ migration complete[/bold green] — {total} column(s) added"
    )
    return total


if __name__ == "__main__":
    migrate()
