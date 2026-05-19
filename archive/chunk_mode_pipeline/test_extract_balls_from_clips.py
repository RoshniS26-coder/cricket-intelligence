"""
Unit tests for the cross-clip ball-record merge in
features/ball_extraction/extract_balls_from_clips.py.

We test the merge_records_across_clips() function directly (no Gemini
calls). Loading it requires putting features/ on sys.path because it's not
a package.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    """Load extract_balls_from_clips.py as a module so we can import the
    merge function. The file isn't part of a Python package, hence this
    importlib dance."""
    project_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(project_root))
    path = project_root / "features" / "ball_extraction" / "extract_balls_from_clips.py"
    spec = importlib.util.spec_from_file_location("extract_balls_from_clips", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


extract_balls = _load_module()


def _rec(over: int, ball: int, *, conf: float = 0.9, chunk: int = 0,
         shot_type: str = "drive", innings: int = 1) -> dict:
    """Build a minimal ball record for testing."""
    return {
        "over": over,
        "ball_number": ball,
        "innings": innings,
        "shot_type": shot_type,
        "_chunk_index": chunk,
        "confidence": {
            "line": conf, "length": conf, "shot_type": conf,
            "outcome": conf, "contact_quality": conf,
        },
    }


class TestRecordAvgConfidence:
    def test_basic_average(self):
        r = _rec(1, 1, conf=0.8)
        assert extract_balls._record_avg_confidence(r) == 0.8

    def test_missing_confidence_returns_zero(self):
        r = {"over": 1, "ball_number": 1}
        assert extract_balls._record_avg_confidence(r) == 0.0

    def test_empty_confidence_dict_returns_zero(self):
        r = {"over": 1, "ball_number": 1, "confidence": {}}
        assert extract_balls._record_avg_confidence(r) == 0.0


class TestMergeRecordsAcrossClips:
    def test_empty_input(self):
        merged, stats = extract_balls.merge_records_across_clips([])
        assert merged == []
        assert stats["total_after_merge"] == 0

    def test_no_duplicates_pass_through(self):
        records = [
            _rec(1, 1, conf=0.9),
            _rec(1, 2, conf=0.9),
            _rec(1, 3, conf=0.9),
        ]
        merged, stats = extract_balls.merge_records_across_clips(records)
        assert len(merged) == 3
        assert stats["unique_scored_balls"] == 3

    def test_duplicate_keeps_higher_confidence(self):
        # Two records for (1, 2). Chunk 0 has conf=0.6, chunk 1 has conf=0.9.
        # Chunk 1's version should win.
        records = [
            _rec(1, 2, conf=0.6, chunk=0, shot_type="drive"),
            _rec(1, 2, conf=0.9, chunk=1, shot_type="cover_drive"),
        ]
        merged, stats = extract_balls.merge_records_across_clips(records)
        assert len(merged) == 1
        assert merged[0]["_chunk_index"] == 1
        assert merged[0]["shot_type"] == "cover_drive"
        assert stats["unique_scored_balls"] == 1

    def test_duplicate_ties_keep_first(self):
        # Same confidence — first encountered wins (insertion order).
        records = [
            _rec(1, 2, conf=0.8, chunk=0, shot_type="drive"),
            _rec(1, 2, conf=0.8, chunk=1, shot_type="flick"),
        ]
        merged, stats = extract_balls.merge_records_across_clips(records)
        assert len(merged) == 1
        assert merged[0]["_chunk_index"] == 0   # first wins on tie

    def test_unscored_records_kept_separately(self):
        # Records with over=0 AND ball=0 → no scoreboard read.
        # Should NOT be deduped against each other; should be appended at end.
        records = [
            _rec(1, 1, conf=0.9, chunk=0),
            {"over": 0, "ball_number": 0, "_chunk_index": 0, "abs_start_sec": 50},
            {"over": 0, "ball_number": 0, "_chunk_index": 1, "abs_start_sec": 200},
            _rec(1, 2, conf=0.9, chunk=1),
        ]
        merged, stats = extract_balls.merge_records_across_clips(records)
        assert stats["unique_scored_balls"] == 2
        assert stats["unscored_records"] == 2
        # First two records in merged are sorted scored ones
        assert (merged[0]["over"], merged[0]["ball_number"]) == (1, 1)
        assert (merged[1]["over"], merged[1]["ball_number"]) == (1, 2)
        # Unscored come last, sorted by abs_start_sec
        assert merged[2]["abs_start_sec"] == 50
        assert merged[3]["abs_start_sec"] == 200

    def test_sorted_by_innings_over_ball(self):
        # Insert intentionally out of order
        records = [
            _rec(2, 1, conf=0.9),
            _rec(1, 6, conf=0.9),
            _rec(1, 1, conf=0.9),
            _rec(3, 2, conf=0.9),
        ]
        merged, stats = extract_balls.merge_records_across_clips(records)
        ids = [(r["over"], r["ball_number"]) for r in merged]
        assert ids == [(1, 1), (1, 6), (2, 1), (3, 2)]

    def test_innings_separates_keys(self):
        # Same (over, ball) but different innings = different deliveries
        records = [
            _rec(1, 1, conf=0.9, innings=1),
            _rec(1, 1, conf=0.9, innings=2),
        ]
        merged, stats = extract_balls.merge_records_across_clips(records)
        assert len(merged) == 2
        assert stats["unique_scored_balls"] == 2

    def test_real_world_scenario_overlap_region(self):
        # Simulates the overlap region of two chunks both seeing balls 1.4, 1.5.
        # Chunk 0 saw them clearly (conf 0.9). Chunk 1 saw them at the edge,
        # less clearly (conf 0.6). Plus chunk 1 saw 1.6 cleanly.
        records = [
            # chunk 0 had a strong read on 1.4 and 1.5
            _rec(1, 4, conf=0.9, chunk=0, shot_type="cover_drive"),
            _rec(1, 5, conf=0.9, chunk=0, shot_type="defend"),
            # chunk 1 also saw 1.4, 1.5 (overlap) plus the new 1.6
            _rec(1, 4, conf=0.6, chunk=1, shot_type="drive"),       # weaker
            _rec(1, 5, conf=0.6, chunk=1, shot_type="defend"),      # weaker
            _rec(1, 6, conf=0.9, chunk=1, shot_type="flick"),       # only chunk 1
        ]
        merged, stats = extract_balls.merge_records_across_clips(records)
        assert stats["unique_scored_balls"] == 3
        ball_map = {(r["over"], r["ball_number"]): r for r in merged}
        # chunk 0's clearer 1.4 should have won
        assert ball_map[(1, 4)]["_chunk_index"] == 0
        assert ball_map[(1, 4)]["shot_type"] == "cover_drive"
        # chunk 0's clearer 1.5 should have won
        assert ball_map[(1, 5)]["_chunk_index"] == 0
        # 1.6 only existed in chunk 1
        assert ball_map[(1, 6)]["_chunk_index"] == 1
