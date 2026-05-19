# Tasks

Document-first task specifications for non-trivial work. Each task gets
its own dated Markdown file written **before** the code is written; the
implementation reads from the task doc and the doc is updated as the work
progresses or scope changes.

This sits next to `docs/architecture.md`, `docs/engineering.md`, and
`docs/features.md` as a fourth canonical doc class — the others describe
*what exists*; tasks here describe *what we're doing right now*.

## Convention

- File name: `YYYY-MM-DD-slug.md`
- Top-of-file metadata: `Created`, `Status` (in progress / completed / abandoned), `Owner` (or "see git blame")
- Standard sections (use these unless the task is trivial enough that some don't apply):
  1. Context — what's broken / what we're solving and why
  2. Goal — concrete success criteria
  3. Approach — the chosen architecture / sequence
  4. Files — table of new + modified files with line counts and purpose
  5. API contract — function signatures, CLI flags, output formats
  6. Acceptance criteria — testable claims (SQL queries, file checks, etc.)
  7. Verification checklist — checkboxes the implementer ticks off
  8. Out of scope — explicit non-goals to stop scope creep
  9. References — links to relevant existing files / external docs

## Lifecycle

1. **Plan first.** Discuss the approach until the spec is clear.
2. **Write the task doc** in this folder (status: in progress).
3. **Implement** against the doc. If the implementation deviates from the
   doc, update the doc — don't let them diverge silently.
4. **Mark done** at the top when acceptance criteria are met.
5. Tasks stay in this folder permanently as a historical record. Don't
   delete after completion.

## Index

| Date | Task | Status |
|---|---|---|
| 2026-05-11 | [PaddleOCR scoreboard timeline extraction](2026-05-11-paddle-ocr-scoreboard-timeline.md) | in progress |
