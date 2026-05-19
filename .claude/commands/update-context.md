---
description: Append a new dated entry to docs/project_context.md summarising this session's work
---

You are about to update `docs/project_context.md` with a session summary.

## Steps

1. **Read the current `docs/project_context.md`** so you preserve all existing entries.

2. **Gather today's facts:**
   - Today's date (from system date — use it verbatim, do not guess)
   - Run `git status --short` to see what files changed this session
   - Run `git log --oneline -5` to see recent commits (if any commits happened)
   - Query the DB for current state:
     ```bash
     sqlite3 data/cricket_intelligence.db "
     SELECT match_id, innings, COUNT(*) AS balls
     FROM balls
     GROUP BY match_id, innings
     ORDER BY match_id, innings;
     "
     ```
   - Note any new files in `data/`, `features/`, `src/`, `docs/`, `scripts/`, `ui/`

3. **Write a new entry at the TOP** of the `## Current state` section. The existing
   entries must be preserved below — this is an append-to-top, not a rewrite. Use
   this template:

   ```markdown
   ### YYYY-MM-DD — <one-line headline of what this session was about>

   **Done today:**
   - <bullet 1>
   - <bullet 2>
   - ...

   **DB state:**
   - <X matches total / Y total ball rows>
   - <any per-innings notes if interesting>
   - <coverage stats if anything notable changed>

   **Reports + artifacts added/changed:**
   - <list any new CSV/JSON/MD files or moved/deleted ones>

   **Open questions / decisions pending:**
   - <anything left open>

   **Next session (next priority):**
   - <what the user should pick up first next time>

   ---
   ```

4. **Write the file back** using the Edit tool (preserve all prior entries below
   the new one — never delete old entries; this is an append-only log).

5. **Confirm** to the user: print which date the entry was added under, plus a
   one-line summary of the new entry's headline.

## Rules

- Be concise — bullet points, not prose paragraphs.
- Include FACTS (file paths, row counts, decisions) not vague summaries
  ("worked on stuff" is useless; "added bowler_report.py + ran for 1276906/innings 1" is useful).
- Always preserve all previous entries — this is an append-only log.
- If the conversation didn't materially change the project state, ask the user
  whether to skip the update rather than writing a noise entry.
- If you can't determine the date programmatically, ASK the user before writing.
