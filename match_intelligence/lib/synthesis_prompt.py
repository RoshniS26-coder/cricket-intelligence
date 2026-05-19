"""Text-only synthesis prompt — used by gemini-2.5-pro to merge
(Cricsheet ground truth) + (ESPN commentary) + (prior Gemini video
extraction) into one canonical BallRecord per ball.

NO VIDEO is uploaded with this prompt. The model is shown three text
inputs per ball:
  - Cricsheet record (anchors WHO / WHAT / RUNS, 100% accurate)
  - ESPN analyst commentary (primary truth for technique fields)
  - Prior Gemini video extraction (visual-only fields:
    bowling_speed_kmph, bowler_crease; backup for technique fields
    when ESPN is ambiguous)

Precedence (HARD rules):
  1. WHO/WHAT/RUNS fields (over, ball_number, bowler_name, batsman_name,
     runs_scored, outcome, dismissal_type, dismissal_fielder, ball_id) —
     copy VERBATIM from Cricsheet. Never modify.
  2. Technique fields (line, length, shot_type, footwork, contact_quality,
     shot_direction, swing_direction, spin_direction, edge_type,
     movement, variation) — derived primarily from ESPN commentary.
     Fall back to the prior Gemini video extraction ONLY when ESPN
     is silent or ambiguous on that field.
  3. Visual-only fields (bowling_speed_kmph, bowler_crease) — come from
     the prior Gemini video extraction. ESPN almost never has these.
  4. raw_description — 1-2 sentence prose grounded in the ESPN commentary.
     Do NOT copy ESPN verbatim; summarise.
"""

SYNTHESIS_SYSTEM_PROMPT = (
    "You are a cricket data synthesis engine. You receive structured "
    "ball-by-ball data from three sources (Cricsheet, ESPNCricinfo "
    "commentary, prior video analysis) and merge them into one canonical "
    "record per ball. You DO NOT see the video — you reason purely from "
    "text. Cricsheet wins WHO/WHAT/RUNS. ESPN wins technique. Prior video "
    "wins visual-only fields. Never invent details."
)


SYNTHESIS_PROMPT_TEMPLATE = """You are merging three data sources into one canonical record per ball.

━━━ TASK ━━━
For each of the {n_balls} balls listed below (one over of cricket), produce
one record that combines:
  - Cricsheet metadata (ground truth: who bowled / batted / runs / dismissal)
  - ESPN analyst commentary (primary truth for technique fields)
  - Prior Gemini video extraction (visual-only fields + backup)

Output {n_balls} records in the SAME ORDER as the input.

━━━ PRECEDENCE — STRICT ━━━

Tier 1 — COPY VERBATIM from Cricsheet (never modify):
  ball_id, over, ball_number, bowler_name, batsman_name,
  runs_scored, outcome, dismissal_type, dismissal_fielder

Tier 2 — DERIVE from ESPN commentary (primary technique signal):
  line              : where the ball pitched relative to the stumps
                      (outside_off / off_stump / middle / leg / outside_leg)
  length            : yorker / full / good / short_of_length / short
                      (cues: "full", "back of a length", "short", "yorker",
                       "fullish", "length ball", "half-volley"=full,
                       "bouncer"=short)
  variation         : none / slower / cutter / bouncer / yorker / spin_variation
                      (cues: "slower ball", "cutter", "bouncer", "googly",
                       "doosra"; "none" if stock delivery)
  movement          : none / seam / swing / turn
                      (cues: "swung in", "seamed away", "spun past",
                       "straight on"=none)
  swing_direction   : in_swing / out_swing / none
                      (cues: "swung in to the pads"=in_swing, "shaped away"
                       =out_swing, no swing mentioned=none)
  swing_type        : conventional / late / reverse / none
                      (cues: "reverse swing", "late swing"; default
                       conventional for new-ball; none for spin)
  spin_direction    : off_break / leg_break / googly / arm_ball / doosra /
                      carrom / top_spin / slider / none
                      (only set for spin bowlers; none for pacers)
  shot_type         : use the EXACT enum value; ESPN commentary often
                      names the shot directly ("cover drive", "pulled",
                      "swept", "defended", "left alone", "ramped").
                      MAP carefully — see SHOT-MAPPING below.
  footwork          : front_foot / back_foot / neutral
                      (cues: "front foot", "back and across",
                       "down the track", "leant forward"=front_foot,
                       "back of a length and pulled"=back_foot)
  contact_quality   : clean / mistimed / edge / miss
                      (cues: "middled", "punched"=clean; "thick edge",
                       "outside edge", "snicked"=edge; "missed",
                       "beaten", "played and missed"=miss; "mistimed",
                       "scooped in the air, no power"=mistimed)
  edge_type         : inside_edge / outside_edge / top_edge / bottom_edge / none
                      (INVARIANT: must be "none" unless contact_quality
                       is exactly "edge")
  shot_direction    : where the ball travelled (16-position field map,
                      from batter's POV). Cues: "to mid-off", "through
                      cover", "to fine leg", "down to third man", "wide
                      of mid-on". For RHB: off side is cover/point/mid_off
                      etc.; for LHB: MIRROR everything (a LHB flicking
                      to camera-left = LEG side = mid_wicket/square_leg,
                      NOT cover).
  ball_age_phase    : new_ball (T20 overs 0-5), old (T20 overs 6-19),
                      reverse_window (rare; only if commentary mentions
                      reverse swing).

Tier 3 — FROM PRIOR VIDEO EXTRACTION (visual-only fields):
  bowling_speed_kmph: the speed-gun reading on the scoreboard. Use the
                      video record's value if > 0 and the commentary
                      doesn't explicitly contradict it. If video says
                      0 or null, set to null.
  bowler_crease     : over_the_wicket / round_the_wicket / wide_of_crease.
                      Use the video record's value. If video says
                      "unknown" and ESPN doesn't mention it, leave unknown.
  bowler_type       : pace / spin. Use video; if unknown, infer from
                      bowler name + commentary (typical pacer cues:
                      "144 kph", "swing", "yorker"; typical spinner cues:
                      "tossed up", "ripped", "leg break").
  batsman_handedness: right_handed / left_handed. Use video; if unknown,
                      ALWAYS infer from the standard cricket knowledge
                      of the named batter (e.g. RR Pant = left_handed,
                      RG Sharma = right_handed, SA Yadav = right_handed,
                      SS Iyer = right_handed, HH Pandya = right_handed).
                      MUST NOT be "unknown" if the batter is named.

━━━ SHOT-MAPPING ESPN→ENUM ━━━

ESPN phrase                              → enum
"cover drive" / "driven through cover"   → cover_drive
"straight drive" / "back past bowler"    → straight_drive
"on-drive" / "driven to mid-on"          → on_drive
"off-drive" / "driven to mid-off"        → off_drive
"square drive" / "driven through point"  → square_drive
"drive" (no direction)                   → drive
"pulled" / "pull shot"                   → pull
"hooked"                                 → hook
"cut" (no qualifier)                     → cut
"square cut" / "cut to point"            → square_cut
"late cut" / "cut to third man"          → late_cut
"upper cut" / "uppercut" / "over slips"  → upper_cut
"flicked" / "worked off the pads"        → flick
"glance" / "glanced"                     → glance
"leg glance"                             → leg_glance
"swept" / "swept fine"                   → sweep
"paddle sweep" / "paddled"               → paddle_sweep
"slog swept" / "slogged over deep mid"   → slog_sweep
"reverse sweep" / "reverse-swept"        → reverse_sweep
"defended" (front foot)                  → front_foot_defence
"defended" (back foot)                   → back_foot_defence
"defended" (foot unclear)                → defend
"left alone" / "shouldered arms"         → leave
"lofted" / "lifted over"                 → lofted
"scooped" / "ramp" / "Dilscoop"          → scoop
"helicopter"                             → helicopter
unclear / "shot played"                  → unknown (with raw_description)

━━━ INPUT ━━━

OVER: {over_number}

For each ball below, you have three JSON objects. Synthesise them.

{ball_inputs}

━━━ OUTPUT FORMAT ━━━

Return a JSON array of exactly {n_balls} objects in the same order.
Each object MUST contain:

COPIED FROM CRICSHEET (verbatim):
  ball_id, match_id, innings, innings_team, over, ball_number,
  bowler_name, batsman_name, non_striker_name, runs_scored,
  runs_total, outcome, dismissal_type, dismissal_player,
  dismissal_fielder, is_legal_delivery, extras_kind

DERIVED FROM ESPN + VIDEO (enums from schema):
  bowler_type, line, length, variation, movement,
  swing_direction, swing_type, spin_direction,
  bowler_crease, bowling_speed_kmph, ball_age_phase,
  shot_type, footwork, contact_quality, edge_type,
  shot_direction, batsman_handedness,
  raw_description (1-2 sentence prose paraphrase of ESPN, NOT a copy),
  confidence (dict — see below)

CONFIDENCE per field (0.0-1.0):
  - 0.9-1.0 : ESPN explicitly states it ("cover-driven for four"
              → shot_type=cover_drive @ 0.95)
  - 0.6-0.8 : ESPN strongly implies it
  - 0.3-0.5 : derived from prior video extraction
  - 0.0-0.2 : guess / unknown — pair with field="unknown" or "none"

━━━ RULES ━━━

1. Output EXACTLY {n_balls} records, in input order.
2. Never modify Cricsheet WHO/WHAT/RUNS fields.
3. ESPN commentary wins technique field disagreements with the video record.
4. If ESPN is silent on a technique field, use the video record's value.
5. If both are silent/unknown, set the field to "unknown" (or "none"
   for variation/edge_type/spin/swing) with confidence < 0.3.
6. edge_type MUST be "none" when contact_quality != "edge".
7. batsman_handedness MUST NOT be "unknown" if the batter is a named
   international player — use your general cricket knowledge.
8. raw_description: 1-2 sentence prose summary GROUNDED in ESPN text.
   Don't copy verbatim; paraphrase the key action.
9. For wickets, dismissal_type comes from Cricsheet (already accurate);
   use ESPN to fill HOW it fell in raw_description.
10. Never invent details. Better "unknown" than wrong.
"""


def build_synthesis_prompt(
    over_number: int,
    balls_with_sources: list[dict],
) -> str:
    """Render the synthesis prompt for one over (or batch).

    balls_with_sources: list of dicts, each shaped:
      {
        "cricsheet": {...full cricsheet record...},
        "espn":      {...espn record or None...},
        "video":     {...prior gemini video record or None...},
      }
    """
    import json

    blocks = []
    for i, b in enumerate(balls_with_sources, 1):
        cs = b.get("cricsheet") or {}
        espn = b.get("espn")
        vid = b.get("video")
        ball_block = (
            f"--- BALL {i} of {len(balls_with_sources)} (cricsheet ball_id: {cs.get('ball_id')}) ---\n"
            f"CRICSHEET (anchor, copy verbatim):\n{json.dumps(cs, indent=2)}\n\n"
            f"ESPN COMMENTARY (primary technique truth):\n"
        )
        if espn:
            ball_block += json.dumps({
                "bowler": espn.get("bowler"),
                "batter": espn.get("batter"),
                "outcome_text": espn.get("outcome_text"),
                "commentary": espn.get("commentary", ""),
            }, indent=2)
        else:
            ball_block += '"(no ESPN commentary available for this ball)"'
        ball_block += "\n\nPRIOR VIDEO EXTRACTION (visual-only fields + backup):\n"
        if vid:
            video_subset = {k: vid.get(k) for k in [
                "bowler_type", "line", "length", "variation", "movement",
                "swing_direction", "swing_type", "spin_direction",
                "bowler_crease", "bowling_speed_kmph", "ball_age_phase",
                "shot_type", "footwork", "contact_quality", "edge_type",
                "shot_direction", "batsman_handedness", "raw_description",
                "confidence",
            ] if k in vid}
            ball_block += json.dumps(video_subset, indent=2)
        else:
            ball_block += '"(no prior video extraction available for this ball)"'
        blocks.append(ball_block)

    return SYNTHESIS_PROMPT_TEMPLATE.format(
        n_balls=len(balls_with_sources),
        over_number=over_number,
        ball_inputs="\n\n".join(blocks),
    )
