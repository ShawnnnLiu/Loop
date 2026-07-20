# Context-Window Splits — User Plan Direction

Sizing companion to `00-overview.md`. Each split is **one fresh Claude
Code session ending in exactly one commit**, budgeted at roughly **300k
total session tokens** — reads, edits, test iterations, and gate runs
included.

## Honest sizing: this is ONE split

One optional profile field down a paved road (`resume_text` is the
template for every layer): spec + contract + fixtures + one prompt block
+ one textarea. Splitting PD-A…PD-D across sessions would pay the ~55k
fixed overhead twice for no benefit.

## Budget model (heuristic priors)

- **Fixed per-session overhead: ~55k.** CLAUDE.md + AGENTS.md + this
  folder + `docs/specs/user-profile.schema.md` + the contract, the
  Strategist regions of `anthropic_adapter.py`, and the named test
  files, before the first edit.
- **PD-A contract + spec: ~50k.** Spec prose, field + validator, 1
  valid + 3 invalid fixture pairs, `make schemas`, contract tests.
- **PD-B strategist + injection: ~50k.** Exclusion set, block append,
  system-prompt edits, 4 prompt-shape tests + 2 injection tests; the
  two-response fake-transport setup is the least predictable cost.
- **PD-C app + frontend: ~45k.** Cycle-level onboard/propose tests,
  2 type sites, constant, textarea + counter + submit mapping, vitest.
- **PD-D security review + gates: ~30k.** Threat-table walk, claim
  sweep greps, full backend + frontend gates (~3.9k backend tests;
  budget one failure-fix iteration).
- **Total: ~230k** against the 300k budget. The slack is deliberate —
  overshoot (a session dying mid-commit) is the real failure mode.

## Overflow rule

The split ends in one commit, with one **internal fallback boundary**:
after PD-B, backend behavior is green and honest on its own (the field
exists, the Strategist consumes it, nothing sets it from the UI yet).
If the session approaches budget mid-PD-C, commit at that boundary
stating plainly that the frontend is not included, and resume in a
fresh session with this kickoff prompt plus "PD-A/PD-B are already
committed; resume at PD-C".

## The split

| Split | Phases | One-commit theme | Est. total | Gate |
| --- | --- | --- | --- | --- |
| 1 | PD-A + PD-B + PD-C + PD-D | Optional `plan_direction` profile field, Strategist-only labeled block, injection-hardened, one-page cap | ~230k (55 + 50 + 50 + 45 + 30) | — |

## Conventions

- **Branch:** `user-plan-direction`, created from `main` once this plan
  folder has merged. If `docs/implementation-plans/completed/user-plan-direction/`
  is missing from `main`, stop and ask.
- **One commit** at the end of the session (authorized by this prompt);
  never push.
- **Gates green before the commit:** `uv run make check` from
  `backend/`; `npm run typecheck && npm run lint && npm test &&
  npm run build` from `frontend/`.
- `graphify update .` after code changes.
- **Reference drift:** line numbers verified 2026-07-18 on `main`. If a
  cited line no longer matches, trust the named symbol over the line
  number and note the drift in the session summary.
- **Hard constraints (not to be relitigated):** the field never reaches
  the Planner, ResumeIntake, Reflection, or Explanation prompts; no
  routing/validation/scheduling logic reads it; no new endpoints; no
  replan wiring; `resume_text` posture untouched; cap is 4,000 chars
  server-side; absent field ⇒ byte-identical Strategist prompt.

## Split 1 — PD-A…PD-D · Plan-direction field, injection-hardened — ~230k

**Primary docs:** `00-overview.md` (context + decisions + reference
table), then `01`–`04` in order.

Kickoff prompt:

```
Read docs/implementation-plans/completed/user-plan-direction/00-overview.md and
SPLITS.md, then 01-contract-and-spec.md,
02-strategist-prompt-and-injection.md, 03-app-api-and-frontend.md,
04-security-review-and-gates.md in that folder. Then read
docs/specs/user-profile.schema.md,
backend/src/agentic_calendar/contracts/user_profile.py, the
AnthropicStrategist region of
backend/src/agentic_calendar/llm_nodes/anthropic_adapter.py (exclusion
set, run(), _STRATEGIST_SYSTEM),
backend/tests/contracts/test_user_profile.py, the résumé-block tests in
backend/tests/llm_nodes/test_anthropic_adapter.py, and
frontend/src/screens/Onboarding.tsx + frontend/src/api/types.ts +
frontend/src/lib/intake.ts. Create branch user-plan-direction from main
(stop and ask if the plan folder is missing from main). Implement PD-A
through PD-D as ONE commit per CLAUDE.md: optional plan_direction
profile field (max 4,000 chars, min 1 when present, C0 controls other
than \n\r\t rejected), spec updated FIRST (field row, untrusted-input
paragraph, Prompt Exposure row, exclusion set = {"resume_text",
"experience", "plan_direction"}, validation rules, update-policy row),
make schemas (user_profile.schema.json only), Strategist-only labeled
data-not-instructions block appended after the résumé block
(byte-identical prompt when absent), translate-the-user's-plan system
prompt rule + hedge extension, prompt-shape tests, two deterministic
injection tests (constraint-override and fabricated-claim), SPA
textbox with cap + live counter (trimmed-empty submits null), and the
04 threat-table walk with claim sweep. Hard constraints: the field
never reaches Planner/ResumeIntake/Reflection/Explanation prompts; no
deterministic component reads it; no new endpoints; no replan wiring;
resume_text posture untouched. uv run make check green from backend/
and npm run typecheck && npm run lint && npm test && npm run build
green from frontend/ before the commit; run graphify update . after
code changes. You may commit at the end; do not push.
```
