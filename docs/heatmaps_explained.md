# Two Heatmaps Explained

The codebase has two pitch-map style heatmaps that look similar but answer
completely different questions. This doc explains both in plain language,
with worked examples, and answers the "how much data do I need" question
honestly.

## TL;DR

| Heatmap | Question it answers | Works from | Trustworthy with |
|---|---|---|---|
| **Frequency Heatmap** (new — `features/heatmap/`) | "Where did the bowlers land the ball / where did the batter face balls?" | **Match 1** | Match 1 onwards |
| **Danger Heatmap** (Streamlit UI — `src/analytics/pitch_map.py`) | "Where should we bowl to dismiss this batter?" | Match 1 *technically*, but the colours lie until you have ~10-15 matches per batter | **10-15+ matches** *per batter* |

The new heatmap is descriptive (counts balls). The UI heatmap is
prescriptive (recommends a plan). Prescriptive advice needs lots of
data; descriptive counts don't.

---

## What each heatmap is actually showing

### Frequency Heatmap — what happened

- **One cell = one count.** "12 balls were bowled at off-stump good length"
  → that cell shows 12 and is shaded dark.
- **No statistical claim.** It doesn't say the batter is weak there, only
  that the bowlers chose to bowl there.
- **Symmetric:** the same renderer produces:
  - Bowler view: "where did this bowler pitch the ball this match?"
  - Batter view: "what lines/lengths did this batter face this match?"
- **Wagon wheel** (new addition): same idea, but circular —
  "how many runs did the batter score to each scoring zone?"
- **Use case:** match recap, fan-facing visuals, opponent scout's first-look
  view, sanity-checking the data.

### Danger Heatmap — what to do about it

Each cell carries a *danger score* between 0 and 1, computed roughly as:

```
danger_score = w1 × dismissal_rate + w2 × (1 / max(avg_runs_per_ball, 0.5))
```

- **Red** cell = batter is dismissed often there, or scores slowly there.
- **Green** cell = batter scores freely there with no fall.
- **Grey** cell = not enough data to judge.
- It is *not* a count. Two cells with very different ball counts can have
  the same colour, and two cells with the same colour can mean very
  different things.
- **Use case:** opposition planning — "what plan does the bowler bring
  to dismiss this batter in tomorrow's match?"

The current code uses `_MIN_SAMPLE = 2` — i.e. it will paint a cell red
even with **2 balls and 1 dismissal**. That's a 50% dismissal rate from
n = 2. Statistically, that's noise. The UI happily shows it anyway —
which is why you, the user, need to know how much data is behind a
red cell before you trust it.

---

## Same data, different stories

Take Suryakumar Yadav, real numbers from the IndvsEng match in the DB:

| Bucket | Frequency map cell | Danger map cell |
|---|---|---|
| **Outside off, good length** | "10 balls" — solid orange | Surya played 4 of these for fours → **green = strength** |
| **Off stump, yorker** | "5 balls" — solid blue | Dismissed once on one of them → **red = danger** |
| **Outside leg, short** | "2 balls" — pale yellow | One dismissal → **bright red** (but only from 2 balls!) |

The frequency map just shows the workload. The danger map turns those
counts into a recommendation — and the recommendation is only as
trustworthy as the sample size behind it.

The third row is the trap: in the UI, that "bright red" cell would
scream "BOWL HERE!" — but it's based on 2 balls. With more data
that cell could turn out to be a strength zone. **This is exactly why
the UI heatmap needs many matches before its colours mean something.**

---

## How much data is "enough" for the Danger Heatmap?

### How balls flow into cells

A T20 innings averages **~25 balls per top-order batter** (more for the
opener, less for #6+). Spread across 25 cells of the heatmap, that's
**~1 ball per cell per innings on average** — wildly unreliable.

### Rough confidence brackets

| Matches of THIS batter in your DB | Balls in DB for them | What you actually have |
|---:|---:|---|
| 1 match | ~25 balls | Frequency map works; danger map is **mostly noise** |
| 5 matches | ~125 balls | Top 2-3 weakness zones start to be real; rest is noise |
| **10-15 matches** | ~250-375 balls | **Solid top-5 weakness/strength zones** — production usable |
| 30+ matches | ~750 balls | Every cell is trustworthy; phase splits + bowler-type splits also work |
| 50+ matches | ~1250 balls | League-quality scouting depth |

### "Do I need 50 T20 matches?"

**No — not 50 matches *per batter*.** But the answer depends on what
you're trying to do:

1. **Generate a weakness map for one specific opponent batter you'll
   face soon** → You need ~10-15 matches **that include that batter**.
   If your DB has 30 matches but Suryakumar appears in only 3 of them,
   his danger map is unreliable regardless of how many total matches
   you have.

2. **Cover a full opposition squad of 11 batters** → You need
   ~10-15 matches where each of them played. In practice this is
   **30-50 total T20 matches in the corpus**, because not every match
   has every batter.

3. **Build league-wide insights / coach an academy** → 100+ matches
   becomes meaningful.

### What ESPN + Cricsheet gives you

You already have the pipeline that turns a match into a clean
ball-by-ball dataset in ~15 minutes + ~$0.50 of Gemini text calls
(once you have the ESPN PDF). So:

- **30 matches** ≈ 30 PDFs to save + 30 × $0.50 = $15 in API + ~8 hours
  of synthesis wall time
- **50 matches** ≈ $25 in API + ~13 hours wall time

Reaching 30 matches gives you working danger maps for any batter who
appears in 10+ of those 30 — i.e. all the top-order regulars of the
teams in your corpus. That's a realistic milestone, not a wall.

### What does NOT help

- Adding the same match more times (no extra information).
- Adding matches that don't include the batter you care about (doesn't
  fill their cells).
- Lowering the confidence threshold in the UI (just lets noise in faster).

### What DOES help even before 50 matches

- Increase `_MIN_SAMPLE` in `src/analytics/weakness.py` from 2 to 5 or 8
  — cells below that show as grey instead of misleading red. **One-line
  fix; recommended right now.**
- Show the cell ball-count alongside the colour in the UI, so users see
  whether a red cell is from 2 balls or 20.
- Aggregate across bowler type (pace vs spin) when per-line/length is
  too thin — gives you usable conclusions earlier.

---

## Practical workflow

For your immediate ICC franchise pitch:

1. **Frequency heatmaps (new) work today** — use them in demos to show
   "look, we extract clean ball-by-ball data from any T20 match in
   15 minutes with no manual coding". One match is enough.
2. **Danger heatmaps need a corpus** — show a working one for a batter
   you have many matches of (e.g. Kohli if your DB has 15+ of his T20I
   innings) instead of a fragile one from 1 match.
3. **Wagon wheel** sits in the middle — works from match 1 but gets
   richer with more matches.

If your demo is one match, lead with the frequency map and the wagon
wheel. If your demo is the full corpus (after 30+ matches), the danger
map becomes the centerpiece.

---

## File pointers

- Frequency heatmap renderer: `src/analytics/heatmaps.py`
- Frequency heatmap CLI: `features/heatmap/generate_heatmaps.py`
- Danger heatmap renderer: `src/analytics/pitch_map.py`
- Danger heatmap aggregator: `src/analytics/weakness.py`
  (this is the one to tune the `_MIN_SAMPLE` threshold in)
- UI integration: `ui/app.py` (Weakness Analysis mode shows both)
