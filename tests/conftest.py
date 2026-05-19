"""
pytest configuration shared across all test modules.

- Adds the project root to sys.path so `from src.X import Y` works without
  installing the package.
- Provides shared fixtures (in-memory DB, sample BallRecord factory).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Make `src.*` importable regardless of CWD when pytest runs.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
#  Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def in_memory_db(tmp_path, monkeypatch):
    """Provide a fresh, isolated CricketDB backed by a temp-file SQLite.

    We use a temp file (not :memory:) because CricketDB opens a new
    connection per call, and SQLite ':memory:' DBs are per-connection — a
    write in one session would not be visible in the next read.
    """
    db_path = tmp_path / "cricket_test.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    from src.storage.db import CricketDB
    return CricketDB(db_url=db_url)


@pytest.fixture
def sample_ball_record():
    """Factory fixture: returns a fully-populated BallRecord builder.

    Use as:
        def test_x(sample_ball_record):
            br = sample_ball_record(ball_id="x_1_1", outcome="4")
    """
    from src.intelligence.schema import (
        BallRecord, ConfidenceScores,
        BowlerType, Line, Length, ShotType, Footwork, ContactQuality, Outcome,
        ShotDirection, DismissalType, BowlerCrease, EdgeType,
        InningsPhase, Handedness,
    )

    def _make(**overrides):
        defaults = dict(
            ball_id="test_ball_1_1",
            match_id="test_match",
            innings=1,
            over=1,
            ball_number=1,
            bowler_name="Test Bowler",
            batsman_name="Test Batsman",
            bowler_type=BowlerType.PACE,
            line=Line.OFF_STUMP,
            length=Length.GOOD,
            shot_type=ShotType.COVER_DRIVE,
            footwork=Footwork.FRONT_FOOT,
            contact_quality=ContactQuality.CLEAN,
            outcome=Outcome.FOUR,
            runs_scored=4,
            shot_direction=ShotDirection.COVER,
            dismissal_type=DismissalType.NONE,
            bowler_crease=BowlerCrease.OVER_THE_WICKET,
            edge_type=EdgeType.NONE,
            phase=InningsPhase.POWERPLAY,
            batsman_handedness=Handedness.RIGHT_HANDED,
            confidence=ConfidenceScores(line=0.9, length=0.9, shot_type=0.9, outcome=1.0, contact_quality=1.0, bowler_type=1.0),
            raw_description="A fine cover drive for four.",
        )
        defaults.update(overrides)
        return BallRecord(**defaults)

    return _make
