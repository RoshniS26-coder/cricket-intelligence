"""
Tests for src.intelligence.schema — BallRecord, enums, ConfidenceScores,
GEMINI_JSON_SCHEMA mirror.

These are pure-data tests; no Gemini API, no DB.
"""

from __future__ import annotations

import pytest

from src.intelligence.schema import (
    BallRecord, ConfidenceScores, MatchMetadata, GEMINI_JSON_SCHEMA,
    BowlerType, Line, Length, Variation, ShotType, Footwork, ContactQuality,
    Outcome, BounceBehavior, Movement,
    SwingDirection, SwingType, SpinDirection, BallAgePhase,
    ShotDirection, DismissalType, BowlerCrease, EdgeType,
    InningsPhase, Handedness,
)


class TestBallRecordDefaults:
    def test_minimum_required_fields(self):
        br = BallRecord(ball_id="x", match_id="m")
        assert br.ball_id == "x"
        assert br.match_id == "m"
        assert br.innings == 1
        assert br.over == 0
        assert br.ball_number == 1
        assert br.runs_scored == 0

    def test_enum_defaults_are_unknown_or_none(self):
        br = BallRecord(ball_id="x", match_id="m")
        assert br.bowler_type == BowlerType.UNKNOWN
        assert br.line == Line.UNKNOWN
        assert br.length == Length.UNKNOWN
        assert br.shot_type == ShotType.UNKNOWN
        assert br.contact_quality == ContactQuality.UNKNOWN
        assert br.outcome == Outcome.UNKNOWN
        # Variation defaults to NONE (because most balls have no variation)
        assert br.variation == Variation.NONE

    def test_tier1_field_defaults(self):
        """Tier-1 analytics fields should default to safe sentinels."""
        br = BallRecord(ball_id="x", match_id="m")
        assert br.shot_direction == ShotDirection.UNKNOWN
        assert br.dismissal_type == DismissalType.NONE
        assert br.dismissal_fielder is None
        assert br.bowling_speed_kmph is None
        assert br.bowler_crease == BowlerCrease.UNKNOWN
        assert br.edge_type == EdgeType.NONE
        assert br.phase == InningsPhase.UNKNOWN
        assert br.batsman_handedness == Handedness.UNKNOWN

    def test_runs_scored_bounded(self):
        # ge=0 enforced by Pydantic
        with pytest.raises(Exception):
            BallRecord(ball_id="x", match_id="m", runs_scored=-1)


class TestEnumValues:
    """Verify every enum is well-formed and round-trips through .value."""

    @pytest.mark.parametrize("enum_cls,expected_unknown", [
        (BowlerType, "unknown"),
        (Line, "unknown"),
        (Length, "unknown"),
        (Footwork, "unknown"),
        (ContactQuality, "unknown"),
        (Outcome, "unknown"),
        (BounceBehavior, "unknown"),
        (Movement, "unknown"),
        (SwingDirection, "unknown"),
        (SwingType, "unknown"),
        (SpinDirection, "unknown"),
        (BallAgePhase, "unknown"),
        (BowlerCrease, "unknown"),
        (InningsPhase, "unknown"),
        (Handedness, "unknown"),
    ])
    def test_enum_has_unknown(self, enum_cls, expected_unknown):
        assert any(m.value == expected_unknown for m in enum_cls)

    @pytest.mark.parametrize("enum_cls,expected_none", [
        (Variation, "none"),
        (SwingDirection, "none"),
        (SwingType, "none"),
        (SpinDirection, "none"),
        (Movement, "none"),
        (DismissalType, "none"),
        (EdgeType, "none"),
        (ShotDirection, "none"),
    ])
    def test_enum_has_none(self, enum_cls, expected_none):
        assert any(m.value == expected_none for m in enum_cls)

    def test_outcome_run_values_are_strings(self):
        assert Outcome.ONE.value == "1"
        assert Outcome.FOUR.value == "4"
        assert Outcome.SIX.value == "6"
        assert Outcome.WICKET.value == "wicket"

    def test_shot_type_has_granular_subtypes(self):
        """The drive/cut/sweep families should have granular subtypes."""
        granular = {
            ShotType.COVER_DRIVE.value, ShotType.STRAIGHT_DRIVE.value,
            ShotType.ON_DRIVE.value, ShotType.OFF_DRIVE.value,
            ShotType.SQUARE_DRIVE.value, ShotType.SQUARE_CUT.value,
            ShotType.LATE_CUT.value, ShotType.UPPER_CUT.value,
            ShotType.SLOG_SWEEP.value, ShotType.PADDLE_SWEEP.value,
            ShotType.REVERSE_SWEEP.value, ShotType.LEG_GLANCE.value,
            ShotType.FRONT_FOOT_DEFENCE.value, ShotType.BACK_FOOT_DEFENCE.value,
            ShotType.HELICOPTER.value, ShotType.SCOOP.value,
        }
        all_values = {m.value for m in ShotType}
        assert granular.issubset(all_values)

    def test_shot_direction_has_16_field_positions(self):
        """The 16-position field map plus none + unknown + behind_wicket."""
        # Spot-check coverage of key positions
        positions = {m.value for m in ShotDirection}
        for required in (
            "cover", "mid_off", "mid_on", "fine_leg", "third_man",
            "deep_cover", "long_on", "long_off", "deep_mid_wicket",
            "behind_wicket", "straight",
        ):
            assert required in positions, f"missing field position: {required}"


class TestConfidenceScores:
    def test_defaults_are_zero(self):
        cs = ConfidenceScores()
        assert cs.line == 0.0
        assert cs.length == 0.0
        assert cs.shot_type == 0.0
        assert cs.outcome == 0.0
        assert cs.contact_quality == 0.0

    def test_tier1_subfields_present(self):
        cs = ConfidenceScores()
        assert hasattr(cs, "shot_direction")
        assert hasattr(cs, "dismissal_type")
        assert hasattr(cs, "bowling_speed")
        assert hasattr(cs, "bowler_crease")
        assert hasattr(cs, "edge_type")
        assert hasattr(cs, "handedness")
        assert hasattr(cs, "bowler_name")
        assert hasattr(cs, "batsman_name")

    def test_bounded_zero_one(self):
        with pytest.raises(Exception):
            ConfidenceScores(line=1.5)
        with pytest.raises(Exception):
            ConfidenceScores(line=-0.1)

    def test_constructor_with_partial_kwargs(self):
        """Mimics how extractor.py builds it: ConfidenceScores(**raw_json.get('confidence', {}))."""
        cs = ConfidenceScores(line=0.9, shot_type=0.7)
        assert cs.line == 0.9
        assert cs.shot_type == 0.7
        assert cs.length == 0.0  # untouched fields stay default


class TestMatchMetadata:
    def test_minimum_required(self):
        mm = MatchMetadata(match_id="m1")
        assert mm.match_id == "m1"
        assert mm.format == "T20"
        assert mm.team_a == ""

    def test_tier1_match_fields(self):
        mm = MatchMetadata(match_id="m1", match_date="2026-05-09", day_or_night="night")
        assert mm.match_date == "2026-05-09"
        assert mm.day_or_night == "night"


class TestGeminiJSONSchemaMirror:
    """The GEMINI_JSON_SCHEMA dict must mirror every BallRecord field that
    Gemini is expected to emit. Drift here breaks structured-output mode.
    """

    def test_required_top_level_keys(self):
        props = GEMINI_JSON_SCHEMA["properties"]
        for required in (
            "bowler_type", "line", "length", "shot_type", "outcome",
            "footwork", "contact_quality",
            "bounce_behavior", "movement", "variation",
            "raw_description", "confidence",
        ):
            assert required in props, f"missing schema key: {required}"

    def test_tier1_keys_present(self):
        props = GEMINI_JSON_SCHEMA["properties"]
        for tier1 in (
            "shot_direction", "dismissal_type", "dismissal_fielder",
            "bowling_speed_kmph", "bowler_crease", "edge_type",
            "phase", "batsman_handedness",
        ):
            assert tier1 in props, f"missing Tier-1 schema key: {tier1}"

    def test_runs_scored_is_bounded(self):
        rs = GEMINI_JSON_SCHEMA["properties"]["runs_scored"]
        assert rs["type"] == "integer"
        assert rs.get("minimum") == 0
        assert rs.get("maximum") == 6

    def test_confidence_subschema_includes_tier1(self):
        conf = GEMINI_JSON_SCHEMA["properties"]["confidence"]
        sub = conf["properties"]
        for required in (
            "bowler_type", "line", "length", "shot_type", "outcome",
            "contact_quality",
            "shot_direction", "dismissal_type", "bowling_speed",
            "bowler_crease", "edge_type", "handedness",
            "bowler_name", "batsman_name",
        ):
            assert required in sub, f"missing confidence subkey: {required}"

    def test_required_array_present(self):
        assert "required" in GEMINI_JSON_SCHEMA
        for must_be_required in ("bowler_type", "line", "length", "shot_type", "outcome"):
            assert must_be_required in GEMINI_JSON_SCHEMA["required"]
