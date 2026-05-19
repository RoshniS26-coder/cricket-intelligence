"""
Tests for src.storage.db — schema integrity, save/read round-trip,
batsman queries. Uses in-memory SQLite via the in_memory_db fixture.
"""

from __future__ import annotations

import pytest

from src.intelligence.schema import (
    BowlerType, Line, Length, ShotType, ContactQuality, Outcome,
    ShotDirection, DismissalType, BowlerCrease, EdgeType,
    InningsPhase, Handedness,
)


class TestMatchOperations:
    def test_create_and_get_match(self, in_memory_db):
        in_memory_db.create_match({
            "match_id": "m1", "format": "T20", "team_a": "India", "team_b": "England",
        })
        m = in_memory_db.get_match("m1")
        assert m is not None
        assert m.match_id == "m1"
        assert m.team_a == "India"

    def test_list_matches_empty(self, in_memory_db):
        assert in_memory_db.list_matches() == []

    def test_list_matches_returns_all(self, in_memory_db):
        in_memory_db.create_match({"match_id": "m1"})
        in_memory_db.create_match({"match_id": "m2"})
        ids = sorted(m.match_id for m in in_memory_db.list_matches())
        assert ids == ["m1", "m2"]

    def test_create_match_idempotent(self, in_memory_db):
        # Same match_id called twice should merge, not duplicate
        in_memory_db.create_match({"match_id": "m1", "team_a": "Old"})
        in_memory_db.create_match({"match_id": "m1", "team_a": "New"})
        assert len(in_memory_db.list_matches()) == 1
        assert in_memory_db.get_match("m1").team_a == "New"


class TestBallRoundtrip:
    def test_save_and_read(self, in_memory_db, sample_ball_record):
        in_memory_db.create_match({"match_id": "test_match"})
        br = sample_ball_record(ball_id="test_match_1_1")
        in_memory_db.save_ball(br)

        read = in_memory_db.get_ball("test_match_1_1")
        assert read is not None
        assert read.ball_id == "test_match_1_1"
        assert read.batsman_name == "Test Batsman"
        assert read.line == Line.OFF_STUMP.value
        assert read.shot_type == ShotType.COVER_DRIVE.value
        assert read.outcome == Outcome.FOUR.value

    def test_tier1_fields_persist(self, in_memory_db, sample_ball_record):
        in_memory_db.create_match({"match_id": "test_match"})
        br = sample_ball_record(
            ball_id="test_match_18_4",
            shot_direction=ShotDirection.MID_WICKET,
            dismissal_type=DismissalType.NONE,
            bowling_speed_kmph=143.5,
            bowler_crease=BowlerCrease.ROUND_THE_WICKET,
            edge_type=EdgeType.NONE,
            phase=InningsPhase.DEATH,
            batsman_handedness=Handedness.LEFT_HANDED,
        )
        in_memory_db.save_ball(br)

        read = in_memory_db.get_ball("test_match_18_4")
        assert read.shot_direction == "mid_wicket"
        assert read.bowling_speed_kmph == 143.5
        assert read.bowler_crease == "round_the_wicket"
        assert read.phase == "death"
        assert read.batsman_handedness == "left_handed"

    def test_save_balls_batch(self, in_memory_db, sample_ball_record):
        in_memory_db.create_match({"match_id": "m1"})
        records = [
            sample_ball_record(ball_id=f"m1_1_{i}", match_id="m1", ball_number=i, runs_scored=i % 6)
            for i in range(1, 7)
        ]
        count = in_memory_db.save_balls_batch(records)
        assert count == 6

    def test_get_balls_for_match_ordered(self, in_memory_db, sample_ball_record):
        """get_balls_for_match should return rows ordered by innings → over → ball."""
        in_memory_db.create_match({"match_id": "m1"})
        # Insert deliberately out of order
        in_memory_db.save_ball(sample_ball_record(ball_id="m1_5_3", match_id="m1", over=5, ball_number=3))
        in_memory_db.save_ball(sample_ball_record(ball_id="m1_2_1", match_id="m1", over=2, ball_number=1))
        in_memory_db.save_ball(sample_ball_record(ball_id="m1_5_1", match_id="m1", over=5, ball_number=1))

        rows = in_memory_db.get_balls_for_match("m1")
        ids = [r.ball_id for r in rows]
        assert ids == ["m1_2_1", "m1_5_1", "m1_5_3"]


class TestBatsmanQueries:
    def test_list_batsmen(self, in_memory_db, sample_ball_record):
        in_memory_db.create_match({"match_id": "m1"})
        in_memory_db.save_ball(sample_ball_record(ball_id="m1_1_1", match_id="m1", ball_number=1, batsman_name="Virat Kohli"))
        in_memory_db.save_ball(sample_ball_record(ball_id="m1_1_2", match_id="m1", ball_number=2, batsman_name="Rohit Sharma"))
        in_memory_db.save_ball(sample_ball_record(ball_id="m1_1_3", match_id="m1", ball_number=3, batsman_name="Virat Kohli"))

        batsmen = in_memory_db.list_batsmen()
        assert sorted(batsmen) == ["Rohit Sharma", "Virat Kohli"]

    def test_list_batsmen_excludes_null_and_empty(self, in_memory_db, sample_ball_record):
        in_memory_db.create_match({"match_id": "m1"})
        in_memory_db.save_ball(sample_ball_record(ball_id="m1_1_1", match_id="m1", ball_number=1, batsman_name="Real Player"))
        in_memory_db.save_ball(sample_ball_record(ball_id="m1_1_2", match_id="m1", ball_number=2, batsman_name=""))
        in_memory_db.save_ball(sample_ball_record(ball_id="m1_1_3", match_id="m1", ball_number=3, batsman_name=None))

        batsmen = in_memory_db.list_batsmen()
        assert batsmen == ["Real Player"]

    def test_get_balls_for_batsman_partial_match(self, in_memory_db, sample_ball_record):
        from src.intelligence.schema import ConfidenceScores
        in_memory_db.create_match({"match_id": "m1"})
        in_memory_db.save_ball(sample_ball_record(
            ball_id="m1_1_1", match_id="m1", ball_number=1, batsman_name="Virat Kohli",
            confidence=ConfidenceScores(line=0.9, length=0.9, shot_type=0.9),
        ))
        in_memory_db.save_ball(sample_ball_record(
            ball_id="m1_1_2", match_id="m1", ball_number=2, batsman_name="Rohit Sharma",
            confidence=ConfidenceScores(line=0.9, length=0.9, shot_type=0.9),
        ))

        rows = in_memory_db.get_balls_for_batsman("Kohli", min_confidence=0.5)
        assert len(rows) == 1
        assert rows[0].batsman_name == "Virat Kohli"

    def test_get_balls_for_batsman_filters_low_confidence(self, in_memory_db, sample_ball_record):
        from src.intelligence.schema import ConfidenceScores
        in_memory_db.create_match({"match_id": "m1"})
        in_memory_db.save_ball(sample_ball_record(
            ball_id="m1_1_1", match_id="m1", ball_number=1, batsman_name="Virat Kohli",
            confidence=ConfidenceScores(line=0.2, length=0.2, shot_type=0.2),
        ))

        rows = in_memory_db.get_balls_for_batsman("Kohli", min_confidence=0.5)
        assert rows == []


class TestStats:
    def test_empty_db_stats(self, in_memory_db):
        stats = in_memory_db.get_stats()
        assert stats["total"] == 0

    def test_stats_aggregates_outcomes(self, in_memory_db, sample_ball_record):
        in_memory_db.create_match({"match_id": "m1"})
        in_memory_db.save_ball(sample_ball_record(ball_id="m1_1_1", match_id="m1", ball_number=1, outcome=Outcome.FOUR))
        in_memory_db.save_ball(sample_ball_record(ball_id="m1_1_2", match_id="m1", ball_number=2, outcome=Outcome.FOUR))
        in_memory_db.save_ball(sample_ball_record(ball_id="m1_1_3", match_id="m1", ball_number=3, outcome=Outcome.WICKET))

        stats = in_memory_db.get_stats("m1")
        assert stats["total"] == 3
        assert stats["outcomes"]["4"] == 2
        assert stats["outcomes"]["wicket"] == 1
