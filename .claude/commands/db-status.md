---
description: Show what's actually loaded in the active Neon DB — matches, innings, ball counts, field coverage — and flag SQLite drift
---

You are reporting the live state of the cricket-intelligence database.

**The active store is Neon Postgres** (via the `DATABASE_URL` env var in `.env`).
The local `data/cricket_intelligence.db` SQLite file is a legacy fallback and is
NOT kept in sync — never report it as the source of truth. Your job is to query
Neon, print a clean summary, and warn if SQLite disagrees.

## Steps

1. **Query Neon** for per-innings ball counts and key-field coverage. Run this
   from the project root (venv active):

   ```bash
   python - <<'PY'
   import os, sqlalchemy as sa
   from dotenv import load_dotenv; load_dotenv(".env")   # explicit path: find_dotenv() fails under stdin/heredoc
   url = os.environ.get("DATABASE_URL")
   assert url and url.startswith("postgres"), f"DATABASE_URL not set to Neon: {url!r}"
   e = sa.create_engine(url)
   COV = ["line","length","shot_type","bowler_type","contact_quality","footwork",
          "bowler_crease","bowling_speed_kmph","dismissal_type"]
   with e.connect() as c:
       print("== matches ==")
       for r in c.execute(sa.text("SELECT match_id, team_a, team_b, format, venue, date FROM matches ORDER BY match_id")):
           print(f"  {r.match_id}  {r.team_a} v {r.team_b}  {r.format}  {r.venue or ''} {r.date or ''}")
       print("== balls per innings ==")
       total = 0
       for r in c.execute(sa.text("SELECT match_id, innings, COUNT(*) n FROM balls GROUP BY match_id, innings ORDER BY match_id, innings")):
           print(f"  {r.match_id}  innings {r.innings}: {r.n}")
           total += r.n
       print(f"  TOTAL ball rows: {total}")
       print("== field coverage (% non-null / non-'unknown') ==")
       for col in COV:
           q = sa.text(f"SELECT 100.0*SUM(CASE WHEN {col} IS NOT NULL AND CAST({col} AS TEXT) NOT IN ('unknown','-1','') THEN 1 ELSE 0 END)/COUNT(*) FROM balls")
           pct = c.execute(q).scalar() or 0
           print(f"  {col:<20} {float(pct):5.0f}%")
   PY
   ```

2. **Flag SQLite drift (sanity check, optional but recommended).** If the file
   exists, compare its total to Neon's and warn if they differ:

   ```bash
   sqlite3 data/cricket_intelligence.db "SELECT COUNT(*) FROM balls;" 2>/dev/null
   ```
   If the SQLite total differs from Neon's total, say so explicitly:
   "⚠️ SQLite (legacy) shows N rows vs Neon's M — SQLite is stale, trust Neon."

3. **Report** to the user:
   - matches table, per-innings counts, grand total (from **Neon**)
   - the coverage table, calling out any field that's surprisingly low
   - the drift warning if applicable

## Rules
- Never present the SQLite file as authoritative — it's a fallback.
- If `DATABASE_URL` is missing or not a Neon `postgres://` URL, STOP and tell the
  user their `.env` isn't pointed at Neon (the app would silently fall back to SQLite).
- Read-only. Never write to either database.
