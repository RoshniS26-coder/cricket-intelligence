"""Technique-only Gemini prompt — used when WHO/WHAT/RUNS are already known
from a Cricsheet ground-truth context.

Inverts the responsibility split of BATCH_EXTRACTION_PROMPT:
  - Cricsheet provides bowler / batter / runs / outcome / dismissal_type
  - Gemini provides shot_type / footwork / contact_quality / line / length /
    swing_direction / bowler_crease / edge_type / bowling_speed_kmph /
    batsman_handedness

Use with `prompt_technique_only.format(cricsheet_context=...)` where the
context is a JSON-serialized list of ground-truth ball dicts.
"""

TECHNIQUE_SYSTEM_PROMPT = (
    "You are a cricket video TECHNIQUE analyst. You receive (a) a broadcast "
    "video clip and (b) a list of ball deliveries with bowler/batter/runs "
    "already known from official records. Your only job is to fill in the "
    "TECHNIQUE fields (shot_type, line, length, footwork, contact, swing, "
    "bowler_crease, edge_type, speed) by observing the video and listening "
    "to the commentary. You MUST NOT modify any field given to you."
)


TECHNIQUE_PROMPT_TEMPLATE = """You are a cricket TECHNIQUE analyst for T20 broadcast video.

━━━ INPUTS ━━━
1. A broadcast video clip (uploaded with this prompt)
2. A list of {n_balls} ball deliveries that occurred in this clip,
   with WHO/WHAT/RUNS already known (Cricsheet ground truth, 100% accurate)
3. PER-BALL COMMENTARY transcribed from the broadcast audio
   (when available — see the block below)

GROUND-TRUTH BALLS (chronological order):
{cricsheet_context}

━━━ BROADCAST COMMENTARY (Whisper transcription, time-aligned) ━━━
{commentary_block}

The commentary is your STRONGEST signal for technique. Commentators describe
shot type, footwork, length, line, and contact quality almost every ball —
often more reliably than the visual frame alone. Cross-reference visual +
commentary, but PREFER the commentary when they disagree on technique fields.

━━━ YOUR JOB ━━━
For each ball in the list above, observe the corresponding delivery in
the video and fill in the TECHNIQUE fields by combining what you SEE and
what the COMMENTARY says.

DO NOT modify any field that was given to you (over, ball_number,
bowler_name, batsman_name, runs_scored, outcome, dismissal_type,
dismissal_fielder, ball_id). Copy them verbatim into your output.

━━━ FIELDS TO FILL FROM VIDEO + COMMENTARY ━━━

Use the EXACT enum values listed below. If the shot/ball genuinely does
not fit any listed value, set the field to "unknown" (or "none" for
variation/edge_type/spin/swing) and describe what you saw in
`raw_description` — never make up an enum value.

BOWLING (what the bowler did):
  bowler_type        — pace | spin | unknown
  line               — outside_off | off_stump | middle | leg | outside_leg | unknown
                       (relative to a right-handed batsman; mirror for left-handers)
  length             — yorker | full | good | short_of_length | short | unknown
                       (yorker = at toes, full = below knee-roll, good = pitched
                        ~6-8m, short_of_length = ~8-10m, short = ~10m+ chest-height)
  variation          — none | slower | cutter | bouncer | yorker | spin_variation | unknown
                       (variation describes a CHANGE from stock ball; if a pacer's
                        bowling speed drops 15+ km/h vs over avg → slower)
  movement           — none | swing | seam | turn | unknown
  swing_direction    — in_swing | out_swing | none | unknown
                       (for spin, set this to none and use spin_direction)
  swing_type         — conventional | late | reverse | none | unknown
  spin_direction     — off_break | leg_break | googly | arm_ball | doosra |
                       carrom | top_spin | slider | none | unknown
                       (off_break = right-arm finger-spin turning into a RHB)
  bowler_crease      — over_the_wicket | round_the_wicket | wide_of_crease | unknown
                       (over_the_wicket = bowler's arm passes CLOSE to the stumps;
                        round_the_wicket = arm passes AWAY from the stumps;
                        readable from the runup angle in the first 1-2 seconds)
  bowling_speed_kmph — integer ONLY when the scoreboard's speed gun reading
                       is visible on screen; else null. Do NOT cite spoken-only
                       speeds from the commentator.
  ball_age_phase     — new_ball | old | reverse_window | unknown
                       (T20: overs 0-6 = new_ball, 7-19 = old; reverse_window is
                        rare in T20s, usually only after over 12 in dry conditions)

BATTING (what the batter did):
  shot_type with brief visual exemplars:
    cover_drive         — front-foot stride, bat through line, ball travels cover/mid-off region.
    straight_drive      — front-foot, bat vertical, ball back past the bowler.
    on_drive            — front-foot, leg-side of straight, ball to mid-on/long-on.
    off_drive           — front-foot, off-side of straight, ball to mid-off/long-off.
    square_drive        — front-foot drive squarer than cover, towards point.
    drive               — any drive you can't precisely sub-classify; use sparingly.
    pull                — back/across, horizontal bat, leg-side from short-of-length+.
    hook                — pull aimed UP at a head-height short ball; often aerial to fine-leg.
    cut                 — back-foot, slap down through point/cover-point on wide ball.
    square_cut          — cut hit squarer (towards point, not late).
    late_cut            — cut deflected fine to third-man, bat almost vertical.
    upper_cut           — back-foot cut UPWARDS on a chest-high short ball, ball over slips.
    flick               — wristy stroke off pads to leg side (mid-wicket / fine-leg).
    glance              — soft deflection off pads, fine to fine-leg.
    leg_glance          — explicit glance from pads, fine-leg region.
    sweep               — front knee down, bat horizontal, leg-side stroke vs spin.
    paddle_sweep        — sweep with bat angled steeper, finer (deep fine-leg).
    slog_sweep          — sweep hit aerial over mid-wicket / deep mid-wicket.
    reverse_sweep       — sweep with hands reversed, ball travels OFF side.
    front_foot_defence  — front-foot push, no run intended.
    back_foot_defence   — back-foot push, no run intended.
    defend              — defensive stroke when foot direction is unclear.
    leave               — bat pulled away, no shot attempted.
    lofted              — any aerial drive over the infield; use if more specific
                          drive subtype not identifiable.
    scoop               — bat angled UP to deflect over the keeper (T20 innovation).
    helicopter          — full bat-rotation follow-through, leg-side six from yorker length.
    unknown             — use ONLY if you genuinely cannot classify; describe in raw_description.

  footwork           — front_foot | back_foot | neutral | unknown
                       (neutral = bat-pad together at point of contact, common
                        on quick reactive shots and many T20 strokes)
  contact_quality    — clean | mistimed | edge | miss | unknown
                       (clean = middle of bat; mistimed = bat-face right but
                        off centre, ball wobbles; edge = bat-edge contact;
                        miss = no bat contact at all, including pad-only)
  edge_type          — inside_edge | outside_edge | top_edge | bottom_edge | none | unknown
                       (set NONE when contact_quality is not "edge")
  shot_direction     — third_man | deep_third | point | deep_point |
                       cover | deep_cover | mid_off | long_off |
                       straight | long_on | mid_on | mid_wicket |
                       deep_mid_wicket | square_leg | deep_square_leg |
                       fine_leg | deep_fine_leg | behind_wicket | none | unknown
                       (16-position field map from BATSMAN's POV;
                        behind_wicket = past the keeper, e.g. ramp shot;
                        none = leave / dot ball where bat didn't make contact)
  batsman_handedness — right_handed | left_handed | unknown
                       (will usually be supplied in context; only fill if not given)

CONFIDENCE: per-field 0.0–1.0 based on how clearly you saw / heard it.

━━━ COMMENTARY AUDIO — secondary signal ━━━

The broadcast audio contains live commentary describing each delivery.
Use it to corroborate or refine your visual reading. Commentators
almost always verbalize:
  - shot_type: "cover drive", "pulled away", "swept", "defended", "leave"
  - footwork:  "front foot", "back and across", "down the track"
  - length:    "good length", "back of a length", "short ball", "yorker"
  - line:      "outside off", "on the pads", "wide of off-stump"
  - contact:   "middled", "edged", "thick edge", "missed", "padded away"
  - speed:     "144 ks", "87 mph"  (cite only if the speed gun is visible)

CAUTIONS:
  - Commentary LAGS the visual by 1-3 seconds. Match each comment to
    the ball that just happened on screen, not the next one.
  - Commentary on REPLAYS may re-discuss the same ball ("watch this
    again"). Use the input ball_id list as the source of truth — do
    NOT emit an extra record for a replay-discussion segment.

━━━ REPLAY HANDLING ━━━

The video may include slow-motion replays of recent balls. They look
identical to the live ball but at half-speed and from a different angle.
DO NOT emit a separate record for a replay. Each ball_id in the input
list corresponds to ONE physical delivery. If you see a replay, use it
to refine your technique reading of the ball it depicts (the immediately
preceding live ball), then move on.

━━━ PRECISION RULES — common error patterns to avoid ━━━

RULE A — LENGTH IS NOT A DEFAULT TO "good"
  Do not pick `length=good` as a safe middle when uncertain. Use the
  visual cues below:
    FULL          = ball pitches in the batter's hitting arc, forward
                    of the popping crease; batter can comfortably play
                    a front-foot drive. Yorker-length is below knee-roll;
                    "full" is anywhere between yorker and good length.
    GOOD          = pitches roughly 6-8m from the batter; bounces to
                    waist/thigh height by the time it reaches them.
                    Defended off the back foot or driven on the up.
    SHORT_OF_LENGTH = pitches 8-10m from the batter; bounces to chest
                    height. Often punched to the off side or pulled.
    SHORT         = pitches 10m+ from the batter; bounces to head/shoulder
                    height. Pulled, hooked, or evaded.
  If you genuinely cannot tell from the video, set length="unknown" and
  confidence_length<0.5. Do NOT pick "good" as the safe fallback —
  defaulting to "good" loses signal and is the most common error type.

RULE B — SHOT DIRECTION IS FROM THE BATTER'S POV, NOT THE CAMERA'S
  shot_direction names (cover, mid_off, mid_wicket, fine_leg, etc.) are
  defined relative to the BATTER, regardless of handedness.
  - For a RIGHT-HANDER: off side is to YOUR LEFT in a standard side-on
    broadcast shot. Leg side is to YOUR RIGHT.
  - For a LEFT-HANDER: MIRROR EVERYTHING. Off side is to YOUR RIGHT in
    the same camera shot. Leg side is to YOUR LEFT.
  When you see a LEFT-handed batter glance/flick to what looks like the
  camera-LEFT side of the screen, that is the LEG SIDE → mid_wicket,
  square_leg, or fine_leg — NOT cover or point.
  Always check the batter's handedness FIRST before naming the field
  position the ball travelled to.

RULE C — CONTACT QUALITY: STRICT VISUAL RUBRIC
  CLEAN  = bat middle hits ball with a clear thunk; ball travels along
           the intended line; batter's body balance is stable.
  MISTIMED = bat connects but off-centre; ball wobbles or loops slowly;
             batter often looks at the bat afterward.
  EDGE   = thin contact with bat edge (NOT middle); ball deflects at an
           odd angle (e.g. straight ball going slips-ward); keeper or
           slip cordon reacts.
  MISS   = bat passes through the ball entirely OR ball hits pad/body
           without any bat contact at all. Beaten outside off = MISS.
  PAD    = ball clearly hits the pad first (LBW shouts apply).
  A defensive shot that meets the ball cleanly and DROPS at the batter's
  feet is CLEAN, not miss. The ball being "stopped dead" by the bat is
  clean contact, not a miss.

RULE D — DRIVE SUB-TYPE PRECISION (use the granular enum, not "drive")
  When you call a drive, pick the specific direction:
    cover_drive    = ball travels through cover region (off side, ~30°
                     from straight for RHB)
    straight_drive = ball goes BACK PAST THE BOWLER (no deviation)
    on_drive       = ball travels to mid_on / long_on (leg side of
                     straight) — full ball on middle/leg, flick-like
                     wristy motion
    off_drive      = ball travels through mid_off (off side, less square
                     than cover)
    square_drive   = ball goes squarer than cover, toward point
  PULL vs ON_DRIVE: a PULL is back-foot horizontal-bat against a
  short-of-length+ ball. An ON_DRIVE is front-foot, vertical-bat against
  a fuller delivery. If the batter is on the front foot and the ball
  goes to mid-on/long-on, it is ON_DRIVE, not PULL.

RULE E — edge_type INVARIANT
  If contact_quality != "edge", then edge_type MUST be "none".
  Do not set inside_edge/outside_edge/top_edge/bottom_edge unless you
  ALSO set contact_quality="edge". The fields are coupled.

RULE F — raw_description GROUNDING
  Only describe what you OBSERVED in the video. Do NOT paraphrase the
  ESPN commentary in raw_description. Do NOT invent details.
  - State what the bowler did (line/length/movement)
  - State what the batter did (shot, footwork, contact)
  - State where the ball went (direction, fielder if visible)
  - For wickets, state HOW the wicket fell
  Bad (fabricated): "Willey bowls a beautiful inswinger that Pant
    plays masterfully to mid-on for a single."
  Good (grounded):  "Length ball on off stump, Pant works it off his
    pads to deep square leg, completes a quick single."

━━━ OUTPUT FORMAT ━━━

Return a JSON ARRAY of exactly {n_balls} objects, in the SAME ORDER as
the input. Each object MUST have:

  COPIED VERBATIM from input:
    ball_id, over, ball_number, bowler_name, batsman_name,
    runs_scored, outcome, dismissal_type, dismissal_fielder

  FILLED FROM VIDEO + COMMENTARY (use enums above; "unknown" allowed):
    bowler_type, line, length, variation, movement, swing_direction,
    swing_type, spin_direction, bowler_crease, bowling_speed_kmph,
    ball_age_phase,
    shot_type, footwork, contact_quality, edge_type, shot_direction,
    batsman_handedness,
    confidence (dict)

━━━ RULES ━━━

1. Output EXACTLY {n_balls} records, in input order.
2. If you cannot observe a field for a particular ball, set it to
   "unknown" (or "none" for variation/edge_type/spin/swing) with
   confidence < 0.5.
3. NEVER invent technique details — better "unknown" than wrong.
4. NEVER modify the WHO/WHAT/RUNS fields. They are ground truth.
5. NEVER skip a ball. If you genuinely cannot see ball N at all, still
   emit a record for it with all technique fields = "unknown" and a
   raw_description noting the visual gap.
6. ALWAYS write `raw_description` as a 1-2 sentence prose summary of what
   actually happened on that ball. Include detail the enums lose:
     - The bat path / shot intent ("late cut squeezed past short third")
     - The bowler's intent ("yorker length aimed at the boot, swung in")
     - Any improvisation ("ramped over the keeper") or mishit signal
       ("got high on the bat, mistimed")
     - Fielder interaction ("caught at slip", "dropped at point",
       "saved on the boundary")
   This free-text is the audit trail when the enum compresses too much.
"""


def build_technique_prompt(
    cricsheet_balls: list[dict],
    commentary_by_ball: dict[str, list[str]] | None = None,
) -> str:
    """Render the technique-only prompt with the given Cricsheet balls
    as ground-truth context and optionally Whisper commentary per ball."""
    import json

    # Trim to the fields Gemini needs as context (drop verbose internals)
    context = [
        {
            "ball_id": b["ball_id"],
            "over": b["over"],
            "ball_number": b["ball_number"],
            "bowler_name": b["bowler_name"],
            "batsman_name": b["batsman_name"],
            "non_striker_name": b.get("non_striker_name"),
            "runs_scored": b.get("runs_scored", 0),
            "runs_total": b.get("runs_total", 0),
            "outcome": b["outcome"],
            "dismissal_type": b.get("dismissal_type", "none"),
            "dismissal_fielder": b.get("dismissal_fielder"),
            "extras_kind": b.get("extras_kind"),
        }
        for b in cricsheet_balls
    ]

    # Build the commentary block (or a placeholder when not supplied)
    if commentary_by_ball:
        commentary_lines = []
        for b in cricsheet_balls:
            segs = commentary_by_ball.get(b["ball_id"], [])
            if segs:
                joined = " ".join(segs).replace("\n", " ")
                commentary_lines.append(f"  {b['ball_id']}: \"{joined}\"")
            else:
                commentary_lines.append(f"  {b['ball_id']}: (no commentary aligned)")
        commentary_block = "\n".join(commentary_lines)
    else:
        commentary_block = "  (no Whisper transcript provided — rely on video + audio in the clip)"

    return TECHNIQUE_PROMPT_TEMPLATE.format(
        n_balls=len(context),
        cricsheet_context=json.dumps(context, indent=2),
        commentary_block=commentary_block,
    )
