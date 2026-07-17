# Context-Window Splits — Calendar Event Titles

Sizing companion to `00-overview.md`. Each split is **one fresh Claude
Code session ending in exactly one commit**, budgeted at roughly **300k
total session tokens** — reads, edits, test iterations, and gate runs
included.

## Honest sizing: this is ONE split

The whole feature is an optional parameter threaded through one region
plus two app-layer call sites, with zero contract/spec/schema work, zero
scheduler churn, and zero frontend work. Splitting T-A…T-D across
sessions would spend the ~55k fixed overhead twice for no benefit.

## Budget model (heuristic priors)

- **Fixed per-session overhead: ~55k.** CLAUDE.md + AGENTS.md + this
  folder + the `calendar_writer/` region (adapter, google_adapter,
  in_memory_adapter, manager ≈ 2.5k lines) + the relevant slices of
  `app/cycle.py` and the four test files, before the first edit.
- **T-A adapter surface: ~40k.** Small edits in three files + 4 new / 1
  rewritten adapter tests; no cross-file churn.
- **T-B manager threading: ~40k.** Param threading to three create
  sites + 3 manager tests against existing fixtures.
- **T-C app wiring + E2E: ~55k.** Two `cycle.py` call paths + helper,
  one stub fix, cycle E2E + write-recovery tests — the write-recovery
  fixture setup is the least predictable cost here.
- **T-D docs + gates: ~25k.** Claim-sweep grep, axiom sentence, full
  `make check` (the suite is ~2.8k tests; budget one failure-fix
  iteration).
- **Total: ~215k** against the 300k budget. The slack is deliberate —
  overshoot (a session dying mid-commit) is the real failure mode.

## Overflow rule

The split ends in one commit, with one **internal fallback boundary**:
after T-B, the adapter + manager plumbing is green and honest on its own
(feature inert — no caller passes titles yet). If the session approaches
budget mid-T-C, commit at that boundary stating plainly that app wiring
is not included, and resume in a fresh session with this kickoff prompt
plus "T-A/T-B are already committed; resume at T-C".

## The split

| Split | Phases | One-commit theme | Est. total | Gate |
| --- | --- | --- | --- | --- |
| 1 | T-A + T-B + T-C + T-D | Real task titles on new calendar writes, fallback preserved, claims aligned | ~215k (55 + 40 + 40 + 55 + 25) | — |

## Conventions

- **Branch:** `calendar-event-titles`, created from `main` once this plan
  folder has merged. If `docs/implementation-plans/calendar-event-titles/`
  is missing from `main`, stop and ask.
- **One commit** at the end of the session (authorized by this prompt);
  never push.
- **Gates green before the commit:** `uv run make check` from `backend/`.
- `graphify update .` after code changes.
- **Reference drift:** line numbers in the phase docs were verified
  2026-07-16 on `resume-intake-onboarding`. If a cited line no longer
  matches, trust the named symbol over the line number and note the
  drift in the session summary.
- **Hard constraints (not to be relitigated):** no canonicalization or
  hash-version change; no `docs/specs/` or contract-model change; no
  `make schemas`; no backfill of existing events; descriptions never
  written; inbound title rule untouched.

## Split 1 — T-A…T-D · Real task titles on new writes — ~215k

**Primary docs:** `00-overview.md` (context + decisions + reference
table), then `01`–`04` in order.

Kickoff prompt:

```
Read docs/implementation-plans/calendar-event-titles/00-overview.md and
SPLITS.md, then 01-adapter-surface.md, 02-manager-threading.md,
03-app-wiring-and-e2e.md, 04-docs-and-gates.md in that folder. Then read
backend/src/agentic_calendar/calendar_writer/ (adapter.py,
google_adapter.py, in_memory_adapter.py, manager.py), the write() /
retry_write() / draft_view() regions of
backend/src/agentic_calendar/app/cycle.py, and the four test files the
phase docs name. Create branch calendar-event-titles from main (stop and
ask if the plan folder is missing from main). Implement T-A through T-D
as ONE commit per CLAUDE.md: real task titles on new Google Calendar
writes via a task_titles map from the app layer, EVENT_SUMMARY demoted
to fallback, all three manager create sites and both retry_write call
sites covered, docstring claim sweep done. Hard constraints: no hashing/
canonicalization change, no contract or docs/specs change, no make
schemas, no backfill of existing events, descriptions never written.
uv run make check green from backend/ before the commit; run graphify
update . after code changes. You may commit at the end; do not push.
```
