# T20 Cricket Intelligence — Product, Value, and Market Position

> A pitch-ready overview of what's built, what's unique, who uses it for what, and what the next 8-match corpus expansion unlocks.

---

## 1. The one-line pitch

**A queryable, structured, multi-source dataset of T20 cricket at the ball-by-ball technique level — built entirely on public data, accessible without broadcaster licensing, designed for franchise opposition prep and weakness analysis.**

---

## 2. What's built (Phase 1 status vs. the original MVP spec)

The original spec laid out a 4-module pipeline: Video Ingestion → Ball Segmentation → Vision Extraction → Validation → Storage → Human Review UI. Here's where we are:

| Module from original spec | Status | What we actually built |
|---|---|---|
| Video Ingestion | ✅ Done | yt-dlp downloader + metadata extractor |
| Ball Segmentation | ✅ Done (per-over batches) | Cricsheet ball-IDs + ESPN-timestamp join — no manual segmentation needed |
| Vision Extraction (Gemini) | ✅ Done (optional path) | Gemini-on-video for `bowling_speed_kmph` + `bowler_crease` (the two fields only visible in broadcast) |
| Structured Extraction | ✅ Done | 28-field Pydantic schema, Gemini returns valid JSON directly via response schema |
| Validation Layer | ✅ Done | `src/validation/normalizer.py` — normalizes prose to enums, handles aliases |
| Storage Layer | ✅ Done | SQLite with innings-qualified ball_id PK (prevents the cross-innings collision we hit early) |
| Confidence Scoring | ✅ Done | Per-field confidence scores in `confidence_scores` JSON column |
| Human Review UI | ⚠️ Partial | Streamlit UI for *browsing* + CSV export; correction-editing not built yet |
| Continuous Learning Loop | ❌ Not yet | Reserved for after we hit corpus scale |

### What we did *differently* from the original spec

The big architectural pivot: **we don't rely on video as the primary signal**. Instead we use a **three-source synthesis**:

1. **Cricsheet** (open-source ball-by-ball JSON) — authoritative for *who bowled, who batted, runs, dismissal*
2. **ESPNCricinfo commentary** (PDF, parsed with pypdf) — primary truth for *technique fields* (line, length, shot, footwork, contact)
3. **Gemini-on-video** (optional) — adds *bowling speed* and *crease angle* — fields visible only in broadcast

`gemini-2.5-pro` synthesizes one record per ball from all three sources. Text-only path costs ~$0.50 per innings and runs in ~17 minutes. Video path adds ~$5-6 and ~2-3 hrs but only adds 2 fields.

**Why this is better than video-only:**
- Avoids paying Gemini to read a scoreboard it can't reliably parse on every broadcaster's overlay
- Captures the analyst's expert interpretation (ESPN prose) instead of asking a model to invent technique labels from pixels
- Cricsheet gives perfect ball-by-ball ground truth for "what happened" — so the model never disagrees with reality on the outcome

---

## 3. What's in the market today

| Source | What it offers | What it lacks |
|---|---|---|
| **Cricsheet** | Open ball-by-ball JSON. Authoritative outcomes (runs/wicket/who). | No technique fields. No line/length/shot/footwork. No video signal. Raw data only — no analytics layer. |
| **ESPNCricinfo** | Rich human-written commentary per ball. Career stats via Statsguru. Scorecards. | All prose, not structured. Statsguru can't compose "vs left-arm pace, full length, in the death" queries. No machine-readable export. |
| **Cricbuzz** | Live scores, scorecards, basic post-match summaries, news. | Prose-heavy. No queryable structured data. Not designed for analysts. |
| **CricHeroes** | Amateur/league cricket tracking. Match scoring app. Player stats for grassroots cricket. | Pro/T20I matches not the target. No technique analysis. No video-derived data. |
| **CricViz / Hawkeye** | Full ball-tracking + technique tagging — the gold standard for analytics. | **Walled garden.** Locked behind broadcaster partnerships. Not accessible to franchises without licensing deals (5-7 figures/year). |
| **CricketGuru / other coaching apps** | Drill libraries, training videos, individual coaching plans. | Not match-data based. No opposition scouting. No batter-vs-bowler matchup analytics. |

### The market gap

**There is no public-data product that gives you CricViz-equivalent analytical depth at a per-ball level in a queryable form.** Franchises either (a) license CricViz at high cost, (b) hire a team of video analysts to do it manually, or (c) work with whatever scorecard-level summaries Cricbuzz/ESPN provide.

This project fills that gap.

---

## 4. The competitive moat (what we add that nothing else has)

| Capability | Us | Cricsheet | ESPN | Cricbuzz | CricHeroes | CricViz |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Per-ball outcome (runs/wicket/who) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Per-ball **structured** line/length | ✅ | ❌ | prose only | prose only | ❌ | ✅ (walled) |
| Per-ball **structured** shot type | ✅ | ❌ | prose only | prose only | ❌ | ✅ (walled) |
| Per-ball footwork + contact quality | ✅ | ❌ | prose only | prose only | ❌ | ✅ (walled) |
| Per-ball **bowling speed** | ✅ (video) | ❌ | ❌ | ❌ | ❌ | ✅ (walled) |
| Per-ball **bowler crease angle** | ✅ (video) | ❌ | ❌ | ❌ | ❌ | ✅ (walled) |
| **Multi-match queryable DB** | ✅ | raw only | ❌ | ❌ | basic | ✅ (walled) |
| Pre-built scouting reports (per-batter / per-bowler) | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ (walled) |
| Pitch maps + wagon wheels (regeneratable) | ✅ | ❌ | static | static | ❌ | ✅ (walled) |
| **Public-data, queryable, customisable** | **✅** | partial | ❌ | ❌ | ❌ | ❌ |

The unique row is the last: **public-data, queryable, customisable** — what a franchise analyst actually needs to compose questions like *"how does Pant score against round-the-wicket left-arm pace at 135+ kph in the death overs?"*

---

## 5. Use cases by persona

### 5.1 The franchise head coach (pre-series prep)

**Question:** "What are England's batters' weaknesses we should target in the next T20I?"

**Workflow:**
1. Open Streamlit UI → Weakness Analysis tab
2. Select batter (e.g., "JC Buttler")
3. View **weakness heatmap** — 5×5 line × length grid with cells colored by danger score (dismissals + dot balls)
4. Read **AI-generated bilingual narrative** ("Buttler is vulnerable to back-of-length on off stump — dismissed twice in 18 balls in this zone")
5. Cross-reference with **per-bowler matchup table** to see which of our bowlers historically trouble him

**Without this tool:** Coach watches 3-4 hours of England's recent T20Is, tallies notes by hand, gets at best 30-40 balls of context.

### 5.2 The performance analyst (mid-series adjustment)

**Question:** "Our pace plan isn't working. What length should we go to in the powerplay?"

**Workflow:**
- SQL query against the DB: `SELECT length, AVG(runs_scored), SUM(CASE WHEN outcome='wicket' THEN 1 ELSE 0 END) FROM balls WHERE phase='powerplay' AND bowler_type='pace' AND match_id IN (last 5 matches) GROUP BY length`
- Compare against the OPPOSITION's powerplay length-split aggregated from our DB
- Adjust the plan with concrete numbers, not gut feel

**Without this tool:** Manual scrubbing of CricViz's broadcaster feed (which the analyst doesn't have access to), or guess from Statsguru's career-level aggregates that lump T20s with ODIs.

### 5.3 The scout (player evaluation for franchise auction)

**Question:** "How does this uncapped player perform against left-arm spin in the middle overs?"

**Workflow:**
- Filter DB for that player + `bowler_type='spin'` + `phase='middle'`
- Compute SR, dot %, dismissal rate, scoring zones
- Visualise the **wagon wheel** to see if they're a leg-side dominant scorer or an all-rounder

**Without this tool:** YouTube highlight reels (cherry-picked) + scorecard stats (no breakdown).

### 5.4 The developer (downstream applications)

**Question:** "I want to build a coaching app that recommends drills based on a batter's weakest zone."

**What we offer:** A SQL-queryable DB with 28 fields per ball, exportable as CSV/JSON, joinable across matches. The application layer just queries our DB and renders.

**Examples of apps that can be built on top:**

| App | Uses our DB to… |
|---|---|
| Fantasy cricket recommender | Predict points based on opposition matchup patterns |
| AI commentary generator | Compose technique-aware ball-by-ball commentary using historical patterns |
| Coaching drill app | Recommend drills matched to a player's weakness heatmap |
| Broadcast graphics overlay | Real-time "this batter has been dismissed N times to this length" insights |
| Pitch behavior model | Aggregate per-venue length × outcome to characterise a pitch |
| Bowler matchup advisor | "Whom to throw the new ball to" decision support |
| Talent scouting engine | Find uncapped players whose patterns match elite-batter profiles |
| Coaching academy LMS | Track student progression by ingesting their net practice clips |

None of these can be built on Cricsheet alone (no technique) or ESPN alone (no structure) or CricHeroes (no pro-level data).

---

## 6. Batting analysis — concrete uses

Each batter in the DB gets a generated scouting card. Example output for SA Yadav (innings 2 of match 1276906):

```
SA Yadav (right_handed)
117 (55b) · SR 212.73 · 14×4, 6×6 · dot% 20.0 · OUT
Dismissal: caught b. MM Ali (18.7), c. PD Salt
```

Plus 8 detailed sections:

| Section | What it tells a coach |
|---|---|
| Line faced (38% outside off, 22% middle…) | Did the opposition stick to a plan? Did it work? |
| Length faced (36% full, 15% yorker) | Did they try to yorker him at the death? |
| Shot type distribution | Is he flick-dominant, drive-dominant, sweep-dominant? |
| Footwork (8 front-foot / 4 back-foot) | Does he commit forward early — exploitable with short ball? |
| Contact quality (67% clean / 17% mistimed / 17% miss) | Was the innings controlled or fortunate? |
| Scoring zones (wagon wheel) | Where to set the field |
| Per-bowler matchups | "Topley got Rohit out; Willey got Kohli — who do we throw the new ball to?" |
| Phase split (powerplay/middle/death) | When is he most dangerous? |

**Multi-match value:** Above is 1 match (55 balls). With 8 matches, top-order batters accumulate 150-240 balls each — enough for every cell of the pitch map to fill with statistical signal.

---

## 7. Bowling analysis — concrete uses

Per-bowler scouting card. Same 28-field DB, sliced from the bowler's perspective:

| Section | Coach value |
|---|---|
| Length distribution | Is this bowler a yorker specialist or back-of-length operator? |
| Line accuracy | Stays on off stump or sprays? |
| Phase split | Powerplay specialist vs. death finisher? |
| **Per-batter matchups** | "Buttler scored 24 off 8 balls against this bowler in past 3 matches — avoid him at the death" |
| Dismissals taken | What method? (caught at deep cover vs. bowled vs. LBW) |
| Speed range (when video available) | "Tops out at 145 but average 138 — flag pacing change" |
| Crease usage (when video available) | "Goes round-the-wicket 20% to LHB only" |

**A franchise's bowling coach** uses this to (a) prep our bowlers for what to expect from opposition pacers, and (b) identify which of our bowlers matches up best with each opposition batter.

---

## 8. What 7-8 T20 matches will unlock

Today: **1 match in the DB** → analytics are descriptive (what happened in this game).

After 8 matches → analytics become **predictive** (what TENDS to happen):

| Threshold | What it unlocks |
|---|---|
| 1 match (today) | Single-game scouting cards. Pitch map cells have 0-5 balls each — too thin to be meaningful. |
| 3-5 matches | Initial matchup patterns visible. "Bowler X has bowled to Batter Y 12 times across 4 innings" — anecdotal but useful. |
| **8 matches (target)** | **Top-order batters cross 150-240 balls each. Wagon wheels statistically valid. Pitch maps fill out. Weakness heatmaps for top 6 batters become reliable.** |
| 15-20 matches | Weakness heatmaps cross statistical significance for top order. Per-bowler-type splits become reliable (e.g., "vs left-arm pace specifically"). |
| 30+ matches | Phase-specific patterns emerge. Per-venue analysis becomes possible. |

**For the 8-match expansion target (2024 IND vs ENG T20I series):**

Expected concrete outcomes:
- **Per-batter pitch maps for 12 marquee players** (India top 6 + England top 6) with 150-240 balls each
- **Per-bowler economy + dot% + dismissal patterns** for both attacks across 8 matches
- **Cross-match matchup tables**: "Bumrah vs Buttler across 8 matches — N balls, N runs, N wickets"
- **Phase-split analysis**: India's powerplay scoring vs death scoring; England's defense in middle overs
- **Comparative weakness maps**: Pant's weakness vs left-arm spin in 2022 vs 2024 (technique evolution)
- **Total cost**: ~$4 (text-only synthesis) + ~3 hours wall-time + manual ESPN-PDF saving for 8 matches

This is the moment the dataset becomes a **product** instead of a **demo**.

---

## 9. How AI is used here (vs. what already exists)

### Existing AI in cricket

| Use case | Who does it | How |
|---|---|---|
| Ball-tracking (LBW review) | Hawkeye | Computer vision on multi-camera tracking |
| Hot Spot (edge detection) | Snickometer + thermal | Broadcaster-only hardware |
| Predictive scoring (win probability) | Cricbuzz, ESPN | Statistical regression on scorecard data |
| Highlights generation | Broadcasters | Scene-change detection + crowd-noise spikes |
| Coaching apps | Various | Mostly template-based drill recommendations, no AI |

### How we use AI differently

| AI capability | What we do | Why it's different |
|---|---|---|
| **Gemini-2.5-pro for ball-level synthesis** | Combines Cricsheet + ESPN prose + optional video into one structured record per ball, with field-level confidence scores | No other tool synthesizes across heterogeneous public sources. Most use video alone (hard, expensive) or text alone (no visual signal). |
| **Gemini for prose-to-enum mapping** | ESPN commentary "drove uppishly through cover" → `shot_type=cover_drive, contact_quality=mistimed` | This is the hardest part of building a queryable dataset from prose. We solved it with a curated mapping prompt + confidence scoring. |
| **Bilingual coaching narrative** | `weakness_narrator.py` generates English + Hindi narrative on the weakness heatmap | Makes outputs usable for grassroots Indian coaches who don't read technical English. No competitor offers this. |
| **Gemini-on-video for scoreboard fields** | Speed + crease from broadcast, parsed per chunk | Cheap, optional, and only invoked when those fields are the deliverable |
| **Structured outputs via response schema** | Gemini returns validated JSON conforming to `BallRecord` schema | No prompt-engineering string parsing — model is constrained to return valid data |

### What we explicitly do *not* do (and why that's a feature)

- **No real-time inference** — batch processing is cheaper and good enough for opposition prep
- **No ball-tracking from video** — Hawkeye already does this, broadcasters license it; we don't need pixel-level trajectories
- **No fine-tuning** — gemini-2.5-pro out of the box is good enough; fine-tuning would lock us to a model version and create maintenance burden
- **No AI commentary generation** — that's a downstream app someone could build *on top of* our DB
- **No "AI captain" decision engine** — Phase 4 in the original spec; we're delivering the data layer that any such engine would need

### Where RAG fits (and where it doesn't)

**RAG is not our primary direction — SQL on the structured DB is.** ~90% of realistic franchise workflows (weakness zones, per-bowler matchups, scoring zones, phase splits, cross-match aggregation, pitch maps, wagon wheels) are exact structured queries that the 28-field `balls` table answers faster, cheaper, and more accurately than any vector retrieval could. Coaches and analysts don't ask *"show me dismissals commentators called unplayable"* — they ask *"who should bowl to Buttler in the death?"* That's a `GROUP BY` query, not a semantic search. Picking SQL over RAG here is the thoughtful-engineer choice, not the trend-chasing one. RAG becomes a justified **optional Phase 2 enhancement** in exactly two scenarios: (a) the **AI Coach product** if the coaching tutorial corpus grows past ~30 entries and the current prompt-injection approach stops fitting in context — RAG would then make drill recommendations specific and citable; and (b) a future **natural-language commentary search** feature for analysts if a customer specifically asks for it, where prose qualifiers like "unplayable" or "momentum-shifting" can't be expressed as SQL. Both are ~half-a-day local-only builds (sentence-transformers + SQLite, no new infra) and we'll ship them on demand, not pre-emptively. The structured DB is the moat — RAG is a query interface someone might bolt on for the prose-flavored 10% of questions.

---

## 10. Roadmap (alignment with the original 4-phase vision)

| Phase | Original spec | Status | Next |
|---|---|---|---|
| **Phase 1 — Ball Intelligence** | Video → ball-level structured records | ✅ **Done** (text-only synthesis pipeline + optional video pass; 1 match in DB) | Scale to 8-match T20I corpus |
| **Phase 2 — Player/Pitch Insights** | Player weakness engine, bowler patterns | ⚠️ Partial — per-match weakness maps + scouting cards work; cross-match aggregation needs the 8-match corpus | Build cross-match weakness/strength aggregator once corpus exists |
| **Phase 3 — Strategy & AI Coach** | Pitch behavior modeling, match simulation | ❌ Not started | After Phase 2 validates the data layer |
| **Phase 4 — AI Captain** | Real-time decision engine | ❌ Not started | Long-term — needs corpus + Phase 2 + Phase 3 done first |

**Note:** The original spec called the AI Coach a Phase 3 deliverable. We've already built a separate **AI Coach product** (`ai_coach/` folder) for *student-clip critique + briefing PDFs* — this is adjacent to the original Phase 3 vision but focuses on coaching INDIVIDUAL players rather than match strategy.

---

## 11. Summary for the manager pitch

**One sentence:** "We've built a structured, queryable, public-data-only equivalent of CricViz's per-ball technique dataset, accessible without broadcaster licensing — and the next 8-match expansion unlocks statistically-valid weakness analytics that no other public source offers."

**Three things to remember:**

1. **The moat is structure + queryability + public sourcing.** CricViz has more data per ball; ESPN has more prose. We have the only combination that lets a franchise analyst compose arbitrary queries across matches.

2. **8 matches is the threshold.** Below that, analytics are descriptive; above that, they become predictive scouting. The cost to cross that threshold is ~$4 + 1 work-day.

3. **The DB is the product, not the UI.** The Streamlit interface is one consumer; the same DB can serve fantasy apps, coaching apps, broadcast overlays, scouting tools, and AI commentary generators — none of which can be built on Cricsheet/ESPN alone.

---

## Appendix — links to deeper docs

- [`../README.md`](../README.md) — project entry point + install + 10-step recipe
- [`architecture.md`](architecture.md) — system design + competitive moat detail
- [`schema.md`](schema.md) — DB schema + field provenance
- [`heatmaps_explained.md`](heatmaps_explained.md) — when to use frequency vs danger heatmap
- [`../match_intelligence/README.md`](../match_intelligence/README.md) — Match Intelligence product details
- [`../ai_coach/README.md`](../ai_coach/README.md) — AI Coach product details
