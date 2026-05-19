"""
Tests for src.intelligence.prompt — verify the prompt accessors return
non-empty strings and contain the rules / rubrics they're supposed to.

These tests deliberately do NOT assert exact wording (so prompt-tuning
doesn't break tests). They only assert that the structural anchors are
present so we know the rubrics survive future edits.
"""

from __future__ import annotations

import pytest

from src.intelligence.prompt import (
    get_system_prompt, get_single_ball_prompt, get_batch_prompt,
)


class TestPromptAccessors:
    def test_system_prompt_non_empty(self):
        p = get_system_prompt()
        assert isinstance(p, str)
        assert len(p) > 100

    def test_single_ball_prompt_non_empty(self):
        p = get_single_ball_prompt()
        assert isinstance(p, str)
        assert len(p) > 500

    def test_batch_prompt_non_empty(self):
        p = get_batch_prompt()
        assert isinstance(p, str)
        assert len(p) > 1000


class TestSingleBallPromptContent:
    """Anchor checks on the single-ball EXTRACTION_PROMPT."""

    @pytest.fixture
    def prompt(self):
        return get_single_ball_prompt()

    def test_mentions_shot_type_rubric(self, prompt):
        # Key shot families that the rubric must spell out
        assert "DRIVE family" in prompt or "drive family" in prompt.lower()
        assert "cover_drive" in prompt
        assert "slog_sweep" in prompt

    def test_lh_flip_rule_present(self, prompt):
        # Both swing and spin rules must mention left-hander flip
        assert "LEFT-HANDED" in prompt or "left-handed" in prompt.lower()
        assert "flip" in prompt.lower()

    def test_tier1_analytics_block_present(self, prompt):
        # The Tier-1 enrichment fields should be documented
        assert "shot_direction" in prompt or "Shot direction" in prompt
        assert "dismissal_type" in prompt or "Dismissal type" in prompt
        assert "bowling_speed" in prompt.lower() or "kmph" in prompt.lower()
        assert "bowler_crease" in prompt or "over_the_wicket" in prompt
        assert "edge_type" in prompt or "Edge type" in prompt
        assert "phase" in prompt.lower()
        assert "handedness" in prompt.lower()

    def test_field_map_positions_listed(self, prompt):
        # Spot-check key field positions from the 16-position map
        for pos in ("cover", "mid_off", "mid_on", "fine_leg", "third_man"):
            assert pos in prompt


class TestBatchPromptContent:
    """Anchor checks on the multi-ball BATCH_EXTRACTION_PROMPT."""

    @pytest.fixture
    def prompt(self):
        return get_batch_prompt()

    def test_broadcast_vs_nets_branching(self, prompt):
        # Both contexts must be addressed
        assert "BROADCAST" in prompt
        assert "NET" in prompt or "net practice" in prompt.lower()

    def test_replay_rules(self, prompt):
        assert "REPLAY" in prompt or "replay" in prompt.lower()
        assert "scoreboard" in prompt.lower()
        # Skip-replays rule
        assert "SKIP" in prompt

    def test_replay_timing_heuristic(self, prompt):
        # The 5–25s heuristic added in the recent prompt fixes
        assert "5" in prompt and "25" in prompt
        assert "replay" in prompt.lower()

    def test_dedup_rule(self, prompt):
        assert "dedup" in prompt.lower() or "deduplication" in prompt.lower()

    def test_exhaustive_enumeration_rule(self, prompt):
        assert "exhaustive" in prompt.lower() or "every" in prompt.lower()

    def test_tier1_analytics_block_present(self, prompt):
        for required in (
            "shot_direction",
            "dismissal_type",
            "bowling_speed_kmph",
            "bowler_crease",
            "edge_type",
            "phase",
            "batsman_handedness",
        ):
            assert required in prompt, f"missing Tier-1 field in batch prompt: {required}"

    def test_lh_flip_in_batch(self, prompt):
        assert "left-handed" in prompt.lower() or "LH" in prompt
        assert "flip" in prompt.lower() or "FLIP" in prompt

    def test_name_confidence_guidance(self, prompt):
        # The note about bowler_name/batsman_name being noisy
        assert "confidence" in prompt.lower()
        assert "bowler_name" in prompt or "batsman_name" in prompt


class TestPromptAccessorsAreStable:
    """Calling the accessor twice should return the same string (no randomness)."""

    def test_system_prompt_stable(self):
        assert get_system_prompt() == get_system_prompt()

    def test_single_ball_prompt_stable(self):
        assert get_single_ball_prompt() == get_single_ball_prompt()

    def test_batch_prompt_stable(self):
        assert get_batch_prompt() == get_batch_prompt()
