"""
Idempotent migration: add `pose_features` JSON column to the `balls` table, and
create the `ground_truth` table used by the flywheel.

Safe to run multiple times.

Usage:
    python scripts/migrate_add_pose.py
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()
console = Console()


def migrate() -> None:
    url = os.getenv("DATABASE_URL", "sqlite:///./data/cricket_intelligence.db")
    engine = create_engine(url)

    with engine.begin() as conn:
        # 1. balls.pose_features column
        cols = {r[1] for r in conn.execute(text("PRAGMA table_info(balls)")).fetchall()}
        if "pose_features" not in cols:
            conn.execute(text("ALTER TABLE balls ADD COLUMN pose_features TEXT"))
            console.print("  [green]+[/green] added balls.pose_features (TEXT / JSON)")
        else:
            console.print("  [dim]·[/dim] balls.pose_features already present")

        # 2. ground_truth table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ground_truth (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ball_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT NOT NULL,
                coach_id TEXT NOT NULL DEFAULT 'anonymous',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                pose_features_snapshot TEXT,
                source TEXT DEFAULT 'ui'
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ground_truth_ball ON ground_truth(ball_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ground_truth_field ON ground_truth(field_name)"))
        console.print("  [green]+[/green] ground_truth table ready")

    console.print("[bold green]✓ migration complete[/bold green]")


if __name__ == "__main__":
    migrate()
