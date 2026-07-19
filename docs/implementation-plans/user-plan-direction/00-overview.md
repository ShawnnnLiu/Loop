# User Plan Direction — Overview

Users who already know what they want to study — a plan they wrote, a
course sequence, "Blind 75 first, then system design" — currently have no
way to tell the Strategist. Their only levers are structured profile
fields (goal, role, weaknesses) and the résumé box, which is the wrong
place for a plan.

This plan adds **one optional free-text field, `plan_direction`**, pasted
into a dedicated textbox during onboarding (and editable via re-onboard,
which is the existing profile-edit path). The Strategist consumes it as a
labeled context block and **translates the user's freeform plan into the
`SyllabusUnits` socket** — the same validated shape the Planner already
consumes. Every downstream socket is untouched.

Planned 2026-07-18; all references verified the same day against `main`.

## Locked user decisions (2026-07-18)

1. **Separate field** — a new textbox, not the résumé box. The résumé
   describes who the user is; this describes what they want to do.
2. **Strategist-only consumer.** The Strategist is the translator from
   freeform plan → syllabus socket. The Planner, ResumeIntake,
   Reflection, and Explanation prompts never see the field; the syllabus
   carries the translated structure forward.
3. **One-page limit: 4,000 characters**, enforced server-side in the
   contract (the frontend cap is UX, not enforcement). Non-empty when
   present; trimmed-empty becomes `null`.
4. **Security hardening is in scope, prompt injection first.** The
   threat model and its per-threat verification live in
   `04-security-review-and-gates.md` and are part of the deliverable,
   not an afterthought.

## What this is NOT

- **Not a Strategist or Planner bypass.** Free text can never reach the
  Scheduler; the pipeline (Strategist → syllabus validation → Planner →
  plan validation → Scheduler → approval gate) is unchanged. The user's
  plan is an *anchoring prior*, exactly like the replan block anchors
  the Planner on a prior approved plan
  (`llm_nodes/anthropic_adapter.py:952-959`).
- **Not control-plane state.** No routing, validation, prerequisite,
  confidence, or scheduling code reads the field. It is excluded from
  the Strategist's canonical input JSON and appended only as a labeled
  raw block, mirroring `resume_text`.
- **Not a replan input.** Recovery replans reuse the stored syllabus or
  deterministic drafts (`app/cycle.py:672` `_replan_plan_source`) and
  never re-run the Strategist — the field shapes **fresh proposes
  only** (`_propose_fresh`, `app/cycle.py:532`, Strategist call at
  `:576`). Rebuilding a plan = re-onboard (profile edit,
  `app/cycle.py:318`) → fresh propose. No replan wiring in this plan.
- **Not a new LLM node.** Consistent with the narrative-pathways
  decision: no new node class in Loop.

## The template: `resume_text`

The repo already solved "optional untrusted free text into the
Strategist" once. This plan is a copy of that paved road:

- Field with documented posture: `contracts/user_profile.py:126`.
- Exclusion from the canonical bundle + labeled raw block append:
  `llm_nodes/anthropic_adapter.py:1104` and `:1157-1176` — when the
  field is absent the prompt is **byte-identical** to a profile without
  it (the D-A acceptance-criterion pattern).
- Injection hedge in the system prompt: `anthropic_adapter.py:915-918`.
- Normative **Prompt Exposure table** in
  `docs/specs/user-profile.schema.md` (§ "Prompt Exposure"), asserted in
  `tests/contracts/test_user_profile.py:78-81`.
- Char caps precedent: `contracts/resume_intake_input.py:23-24`
  (résumé: min 50 / max 40,000; this field: max 4,000, no floor —
  a one-line directive is valid).
- Call-log posture: hashes and counts only, never raw text
  (axiom 22) — the new field inherits this automatically.

## Why the change is safe

"LLMs propose; deterministic infrastructure disposes" survives intact.
An adversarial or malformed `plan_direction` can at most steer the
*content* of a proposal, and every proposal still passes through:

1. `_check_against_constraints` (module cap, allowed priorities, time
   budget, company-specific evidence — `llm_nodes/strategist.py:83`,
   run post-generation by the adapter engine).
2. `validate_syllabus_units` (shape + source-claim integrity; unknown,
   expired, or fabricated claim ids are rejected —
   `validation/__init__.py:108`).
3. The bounded repair loop (≤ 2 attempts, typed `reason_code`,
   `app/cycle.py:574-606`).
4. Planner validation (graph, coverage, user-fit) and scheduler
   preconditions, unchanged.
5. The human approval gate before any calendar write.

## Phases

| Phase | Doc | Content |
| --- | --- | --- |
| PD-A | `01-contract-and-spec.md` | Spec first (field row, untrusted-input paragraph, Prompt Exposure row, validation rules), contract field + validators, fixtures, `make schemas`, contract tests |
| PD-B | `02-strategist-prompt-and-injection.md` | Exclusion set, labeled block, system-prompt translate rule + hedge, prompt-shape tests, deterministic injection tests |
| PD-C | `03-app-api-and-frontend.md` | Onboard passthrough verification, SPA textbox + live counter + copy, types, vitest |
| PD-D | `04-security-review-and-gates.md` | Threat-model checklist walk, claim sweep, full gates |

Sizing and the kickoff prompt live in `SPLITS.md` (single split,
PD-A→PD-D).

## Reference table (verified 2026-07-18 on `main`)

If a cited line number no longer matches, trust the named symbol over
the line number and note the drift in the session summary.

| Symbol | Location |
| --- | --- |
| `UserProfile` / `resume_text` | `contracts/user_profile.py:89` / `:126` |
| `StrategistInput` | `contracts/strategist_input.py:20` |
| `STRATEGIST_BUNDLE_EXCLUDED_PROFILE_FIELDS` | `llm_nodes/anthropic_adapter.py:1104` |
| `AnthropicStrategist.run` (bundle + résumé block) | `anthropic_adapter.py:1137` (`:1157-1176`) |
| `_STRATEGIST_SYSTEM` (hedge at `:915-918`) | `anthropic_adapter.py:897-922` |
| `_check_against_constraints` | `llm_nodes/strategist.py:83` |
| `validate_syllabus_units` | `validation/__init__.py:108` |
| `CycleService.onboard` | `app/cycle.py:318` |
| `CycleService._propose_fresh` (Strategist call) | `app/cycle.py:532` (`:576`) |
| `_replan_plan_source` (no Strategist on replan) | `app/cycle.py:672` |
| Onboard route + trust boundary | `app/web/routes_cycle.py:130` (docstring `:14`) |
| Exclusion-set assertion | `tests/contracts/test_user_profile.py:78-81` |
| Optional-block prompt tests | `tests/llm_nodes/test_anthropic_adapter.py:422,488` |
| Injection-test precedent | `tests/llm_nodes/test_anthropic_resume_intake.py:189` |
| Résumé caps precedent | `contracts/resume_intake_input.py:23-24` |
| Valid/invalid profile fixtures | `tests/fixtures/{valid,invalid}/user_profile/` |
| Generated schema | `schemas/user_profile.schema.json` |
| SPA résumé textbox + counter | `frontend/src/screens/Onboarding.tsx:517-546` (submit map `:241`) |
| SPA types | `frontend/src/api/types.ts:61,99` |
