"""
Tests for src.validation.normalizer — alias resolution, phase derivation,
cross-field consistency rules.
"""

from __future__ import annotations

import pytest

from src.intelligence.schema import (
    BowlerType, ContactQuality, Outcome, ShotType, SwingDirection,
    SpinDirection, InningsPhase,
)
from src.validation.normalizer import (
    BallRecordValidator, derive_phase, resolve_player_name,
)


# ─────────────────────────────────────────────────────────────────────────────
#  derive_phase()
# ─────────────────────────────────────────────────────────────────────────────

class TestDerivePhase:
    @pytest.mark.parametrize("over,expected", [
        (1, InningsPhase.POWERPLAY),
        (3, InningsPhase.POWERPLAY),
        (6, InningsPhase.POWERPLAY),
        (7, InningsPhase.MIDDLE_OVERS),
        (10, InningsPhase.MIDDLE_OVERS),
        (15, InningsPhase.MIDDLE_OVERS),
        (16, InningsPhase.DEATH),
        (20, InningsPhase.DEATH),
    ])
    def test_t20_phases(self, over, expected):
        assert derive_phase(over, "T20") == expected

    @pytest.mark.parametrize("over,expected", [
        (1, InningsPhase.POWERPLAY),
        (10, InningsPhase.POWERPLAY),
        (11, InningsPhase.MIDDLE_OVERS),
        (40, InningsPhase.MIDDLE_OVERS),
        (41, InningsPhase.DEATH),
        (50, InningsPhase.DEATH),
    ])
    def test_odi_phases(self, over, expected):
        assert derive_phase(over, "ODI") == expected

    def test_t20i_alias(self):
        # T20I should map to T20 rules
        assert derive_phase(5, "T20I") == InningsPhase.POWERPLAY

    def test_test_format_returns_unknown(self):
        # Test cricket has no enum-style phases
        assert derive_phase(50, "Test") == InningsPhase.UNKNOWN

    def test_zero_over_returns_unknown(self):
        assert derive_phase(0, "T20") == InningsPhase.UNKNOWN

    def test_none_format_returns_unknown(self):
        assert derive_phase(5, "") == InningsPhase.UNKNOWN
        assert derive_phase(5, None) == InningsPhase.UNKNOWN


# ─────────────────────────────────────────────────────────────────────────────
#  resolve_player_name()
# ─────────────────────────────────────────────────────────────────────────────

class TestResolvePlayerName:
    def test_known_short_form(self):
        # data/player_aliases.yaml maps "Iyer" → "Shreyas Iyer"
        assert resolve_player_name("Iyer") == "Shreyas Iyer"

    def test_case_insensitive(self):
        assert resolve_player_name("iyer") == "Shreyas Iyer"
        assert resolve_player_name("IYER") == "Shreyas Iyer"

    def test_whitespace_tolerant(self):
        assert resolve_player_name("  Iyer  ") == "Shreyas Iyer"

    def test_unknown_name_passes_through(self):
        # Names not in the YAML are returned unchanged
        assert resolve_player_name("Unknown Player") == "Unknown Player"

    def test_already_canonical_unchanged(self):
        assert resolve_player_name("Virat Kohli") == "Virat Kohli"

    def test_none_input(self):
        assert resolve_player_name(None) is None

    def test_empty_string_input(self):
        assert resolve_player_name("") == ""

    def test_multiple_aliases(self):
        """Spot-check several aliases from the seed YAML."""
        cases = [
            ("Rohit", "Rohit Sharma"),
            ("Suryakumar", "Suryakumar Yadav"),
            ("Munro", "Colin Munro"),
            ("Willey", "David Willey"),
        ]
        for short, full in cases:
            assert resolve_player_name(short) == full


# ─────────────────────────────────────────────────────────────────────────────
#  BallRecordValidator — cross-field consistency
# ─────────────────────────────────────────────────────────────────────────────

class TestBallRecordValidator:
    def test_alias_resolution_in_validate(self, sample_ball_record):
        br = sample_ball_record(batsman_name="Iyer", bowler_name="Willey")
        v = BallRecordValidator()
        nv, warnings = v.validate_record(br, format_str="T20")
        assert nv.batsman_name == "Shreyas Iyer"
        assert nv.bowler_name == "David Willey"
        # Warnings should mention both canonicalisations
        joined = " ".join(warnings)
        assert "Iyer" in joined and "Shreyas Iyer" in joined

    def test_phase_derivation_when_unknown(self, sample_ball_record):
        br = sample_ball_record(over=18, phase=InningsPhase.UNKNOWN)
        v = BallRecordValidator()
        nv, _ = v.validate_record(br, format_str="T20")
        assert nv.phase == InningsPhase.DEATH

    def test_phase_not_overwritten_when_set(self, sample_ball_record):
        # Gemini-set phase wins over derivation
        br = sample_ball_record(over=18, phase=InningsPhase.MIDDLE_OVERS)
        v = BallRecordValidator()
        nv, _ = v.validate_record(br, format_str="T20")
        assert nv.phase == InningsPhase.MIDDLE_OVERS

    def test_pace_clears_spin_direction(self, sample_ball_record):
        # Pace bowler with a non-NONE spin_direction → cleared
        br = sample_ball_record(
            bowler_type=BowlerType.PACE,
            spin_direction=SpinDirection.OFF_BREAK,
        )
        v = BallRecordValidator()
        nv, warnings = v.validate_record(br, format_str="T20")
        assert nv.spin_direction == SpinDirection.NONE
        assert any("spin_direction" in w for w in warnings)

    def test_spin_clears_swing_direction(self, sample_ball_record):
        br = sample_ball_record(
            bowler_type=BowlerType.SPIN,
            swing_direction=SwingDirection.IN_SWING,
        )
        v = BallRecordValidator()
        nv, warnings = v.validate_record(br, format_str="T20")
        assert nv.swing_direction == SwingDirection.NONE
        assert any("swing_direction" in w for w in warnings)

    def test_leave_forces_miss_contact(self, sample_ball_record):
        br = sample_ball_record(
            shot_type=ShotType.LEAVE,
            contact_quality=ContactQuality.CLEAN,  # contradiction
        )
        v = BallRecordValidator()
        nv, warnings = v.validate_record(br, format_str="T20")
        assert nv.contact_quality == ContactQuality.MISS
        assert any("leave" in w.lower() or "miss" in w.lower() for w in warnings)

    def test_outcome_to_runs_scored(self, sample_ball_record):
        # extract_from_clip doesn't always populate runs_scored; validator does
        br = sample_ball_record(outcome=Outcome.SIX, runs_scored=0)
        v = BallRecordValidator()
        nv, _ = v.validate_record(br, format_str="T20")
        assert nv.runs_scored == 6

        br2 = sample_ball_record(outcome=Outcome.DOT, runs_scored=4)
        nv2, _ = v.validate_record(br2, format_str="T20")
        assert nv2.runs_scored == 0

    def test_low_confidence_warning(self, sample_ball_record):
        from src.intelligence.schema import ConfidenceScores
        br = sample_ball_record(
            confidence=ConfidenceScores(line=0.2, length=0.2, shot_type=0.2),
        )
        v = BallRecordValidator()
        _, warnings = v.validate_record(br, format_str="T20")
        assert any("confidence" in w.lower() for w in warnings)
