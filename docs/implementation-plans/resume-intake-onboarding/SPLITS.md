# Context-Window Splits — Résumé Intake Onboarding

How to implement this feature across fresh Claude Code sessions. Each split
is sized to stay comfortably under ~300k tokens of session work (reads +
writes + gate iterations). Run them **in order**; each split is exactly one
plan increment and ends in exactly one commit (house convention).

Why one increment per session: RI-A and RI-B each involve heavy reads (all
axioms/specs/house contract patterns; the large `anthropic_adapter.py`) plus
the ~150-entry seed taxonomy, and RI-D ends in a real-browser CDP pass —
merging any two adjacent increments risks the cap. Five sessions is the safe
shape, and the commit boundaries already match.

| Split | Increment | Scope (one line) | Est. tokens |
| --- | --- | --- | --- |
| 1 | RI-A | Axioms 01/03/08/09 + 5 specs + Pydantic contracts + fixtures + seed taxonomy JSON + `make schemas` | ~150–250k |
| 2 | RI-B | Fixture twin + Anthropic adapter (Haiku, prompts, post-validator) + `skill_taxonomy/` kernel + call-log enum + Strategist exclusion | ~150–250k |
| 3 | RI-C | `POST /api/onboard/extract` + environment/bundle wiring + service normalization + keyless dev verify | ~100–180k |
| 4 | RI-D | Consolidated wizard step, Extract button, editable sections, api client, vitest + real-browser CDP pass | ~150–250k |
| 5 | RI-E | Eval-set cases + capture-CLI registration + observability checks + docs + whole-branch DoD | ~100–180k |

RI-F (corpus-evidence enrichment) is **not scheduled here** — it is gated on
grounding-RAG G-A–G-D landing first (see `06-skill-taxonomy.md`).

## Conventions that apply to every split

- Branch: `resume-intake-onboarding`, created in Split 1 from `main` **after
  the `calendar-authoritative-moves` PR merges** (README §Sequencing). Splits
  2–5 continue on it. If the expected prior-split commit is missing from
  `git log`, stop and ask the user.
- One commit per split, spec/axiom-first ordering inside the increment.
  Commit only when the user asks (operating contract) — end each session by
  presenting the diff summary and proposed commit message.
- Gates green before the commit: `uv run make check` from `backend/`; for
  Split 4 also `npm run typecheck && npm run lint && npm run test && npm run
  build` from `frontend/`.
- `graphify update .` after code changes.
- Ask-user gates: no new dependencies expected anywhere; the only networked
  step in the whole project is the **optional** live Haiku smoke in Split 5
  (~$0.01) — ask first.

## Split 1 — RI-A · Contracts and Axioms

**Primary doc:** `01-contracts-and-axioms.md` (plus the RI-A rows of
`06-skill-taxonomy.md`'s build-order table).

Scope highlights:
- Amend axioms 01 (fifth node class), 03 (two contract lines), 09 (Haiku
  pricing row + onboarding budget row), 08 ("Controlled vocabularies"
  subsection).
- New specs: `resume-extraction.schema.md`, `resume-intake-input.schema.md`,
  `skill-taxonomy.schema.md`; update `user-profile.schema.md` (incl. the
  normative prompt-exposure table) and `llm-call-log.schema.md`.
- Contract modules: `resume_extraction.py`, `resume_intake_input.py`
  (with `allowed_weak_spots`), `career_track.py`, `skill_taxonomy.py`;
  `user_profile.py` gains `experience` + `skills` (`ExperienceItem` lives in
  `user_profile.py`, imported by `resume_extraction.py`).
- Seed vocabulary `backend/taxonomy/skill_taxonomy_v1.json` (~60–100 SWE,
  ~30–40 each MLE/AI-engineer).
- Valid + invalid fixtures (structured violations), `make schemas`, tests.

Session-specific gates:
- **Check first** whether `contracts/career_track.py` already exists (the
  grounding-RAG branch may have landed it — whichever lands first creates
  it; reuse if present).
- **Present the seed taxonomy to the user for review before committing** —
  the review IS the curation gate (`06-skill-taxonomy.md`).
- The axiom-01 amendment wording is user-reviewed at commit time (README
  ask-user gates).
- The prompt-exposure-table test may be written `xfail`/skipped here; Split
  2 activates it. Leave a TODO naming RI-B.

Kickoff prompt:

```
Read docs/implementation-plans/resume-intake-onboarding/SPLITS.md (Split 1),
then README.md, 01-contracts-and-axioms.md, and 06-skill-taxonomy.md in that
folder. Then read docs/axioms/01-system-boundaries.md,
docs/axioms/03-data-contracts.md, docs/axioms/08-rag-source-claims.md,
docs/axioms/09-cost-and-metrics.md, docs/specs/user-profile.schema.md,
docs/specs/llm-call-log.schema.md, and skim
backend/src/agentic_calendar/contracts/ for house style (frozen models,
extra="forbid", fixture patterns). Implement increment RI-A only, following
CLAUDE.md (spec/axiom-first, uv run make check green from backend/). Before
proposing the commit, show me the seed skill_taxonomy_v1.json for review and
the axiom-01 amendment wording. Do not start RI-B.
```

## Split 2 — RI-B · Node and Harness

**Primary doc:** `02-node-and-harness.md` (plus the RI-B rows of
`06-skill-taxonomy.md`).

Scope highlights:
- `call_log.py`: `LlmNodeName.RESUME_INTAKE`.
- `llm_nodes/resume_intake.py`: `FixtureResumeIntake` (taxonomy-alias scan,
  aliases injected as plain data — no kernel import).
- `AnthropicResumeIntake` in `anthropic_adapter.py`: `RESUME_INTAKE_CONFIG`
  (claude-haiku-4-5, $1.00/$5.00), system prompt with the six rules, byte-
  stable exemplar, user-prompt assembly (bundle JSON sans résumé + allowed
  weak-spot block + labeled raw résumé block), post-validator
  `_check_resume_extraction` (groundedness, category denylist, uniqueness,
  weak-spot membership via injected callable).
- `skill_taxonomy/` kernel: `registry.py`, `normalize.py`,
  `resolve_track`; registered in `.importlinter` (imports `contracts/` +
  `common/` only; NOT imported by `llm_nodes/`).
- Strategist bundle exclusion widens to `{"resume_text", "experience"}`;
  activate the exposure-table test deferred from Split 1.
- Full test list in the doc §6 (incl. prompt-injection fixture, denylist
  unit tests, kernel property tests).

Session-specific gates:
- SDK-isolation boundary test must stay green with zero changes.
- The category denylist constant is quoted in the RI-A spec — keep the two
  in sync (read the spec Split 1 wrote before coding the constant).

Kickoff prompt:

```
Read docs/implementation-plans/resume-intake-onboarding/SPLITS.md (Split 2),
then README.md, 02-node-and-harness.md, and 06-skill-taxonomy.md in that
folder. Verify the RI-A commit exists on branch resume-intake-onboarding
(git log) — if not, stop and ask. Then read
backend/src/agentic_calendar/llm_nodes/base.py, strategist.py, call_log.py,
and anthropic_adapter.py (note _GenerationEngine and the Strategist résumé
handling), the specs RI-A added under docs/specs/, .importlinter, and one
existing adapter test module for the fake-transport pattern. Implement
increment RI-B only (node, adapter, prompts, post-validator, skill_taxonomy/
kernel, Strategist exclusion, tests), per CLAUDE.md. Gate: uv run make check
green from backend/, boundaries included. Do not start RI-C.
```

## Split 3 — RI-C · App Layer and API

**Primary doc:** `03-app-and-api.md` (plus the RI-C rows of
`06-skill-taxonomy.md`).

Scope highlights:
- `environment.py`: `ResumeIntakeNode` Protocol + fifth `LlmNodeBundle`
  member; both factories in `tools/run_cycle.py` updated.
- `cycle.py`: `extract_resume` — validate/force user_id, resolve track +
  fill `allowed_weak_spots`, mint `intake-` run_id, call node, normalize
  skills (`skills_canonical` / `skills_unmatched` / `taxonomy_version`),
  typed-reason-code failure mapping with NO run-state mutation. Strictly
  persistence-free.
- `results.py`: `ExtractResumeResult`.
- `routes_cycle.py`: `POST /api/onboard/extract` (200 + reason_code for LLM
  failures, 422 for contract-invalid payloads; deferred rate-limit note in
  the docstring).
- Verify onboard path unchanged; regression test: re-onboard preserves
  `experience`/`skills`.
- Test list in the doc §5 (incl. persistence-free assertion and the
  Flurbo.js unmatched-skill case); demo-server boots keyless with five
  nodes.

Kickoff prompt:

```
Read docs/implementation-plans/resume-intake-onboarding/SPLITS.md (Split 3),
then README.md, 03-app-and-api.md, and 06-skill-taxonomy.md in that folder.
Verify RI-A and RI-B commits exist on branch resume-intake-onboarding — if
not, stop and ask. Then read backend/src/agentic_calendar/app/environment.py,
app/cycle.py (onboard + _llm_failure mapping), app/results.py,
app/web/routes_cycle.py, app/web/__main__.py, tools/run_cycle.py, and the
skill_taxonomy/ kernel RI-B added. Implement increment RI-C only
(persistence-free extract endpoint + wiring + tests), per CLAUDE.md. Gate:
uv run make check green from backend/; verify the keyless demo server boots.
Do not start RI-D.
```

## Split 4 — RI-D · Frontend

**Primary doc:** `04-frontend.md`.

Scope highlights:
- Wizard 5 → 4 steps (Skills step absorbed into `Résumé & profile`); fix all
  `?step=` deep-link indices, with a vitest for the mapping.
- Consolidated step: paste textarea, explicit Extract button (pending
  state), five editable sections with structural provenance labels,
  unmatched-skills "not recognized" chip group, weak-areas "a guess" flag,
  target level stays manual.
- Merge policy: replace-on-extract with inline confirm when sections have
  user content; extraction state client-only.
- Failure banner with typed reason_code; skip path stays fully functional.
- `api/types.ts` + `extractResume` client; `buildPayload` / `initialForm`
  carry `experience` + `skills`.
- Vitest list in doc §4; then the real-browser CDP pass against the keyless
  dev server (paste → extract → edit → finish → reload → `/api/me` echoes
  confirmed values). The CDP smoke-harness recipe is in the ux-quality-pass
  session memory (`ux-quality-pass-plan`).

Kickoff prompt:

```
Read docs/implementation-plans/resume-intake-onboarding/SPLITS.md (Split 4),
then README.md and 04-frontend.md in that folder, and the visual target
docs/design-reference/design-loop/onboarding.jsx (step 5). Verify RI-A/B/C
commits exist on branch resume-intake-onboarding — if not, stop and ask.
Then read frontend/src/screens/Onboarding.tsx (or wherever Onboarding lives
— grep for STEP_LABELS), frontend/src/api/types.ts, the api client module,
and one existing screen test for the vitest pattern; grep the SPA for
?step= navigation sources. Implement increment RI-D only, per CLAUDE.md.
Gates: npm run typecheck && npm run lint && npm run test && npm run build
from frontend/, then a real-browser CDP smoke against
python -m agentic_calendar.app.web (paste, extract, edit a chip, delete an
experience row, finish, reload, verify /api/me). Do not start RI-E.
```

## Split 5 — RI-E · Evals, Observability, Docs

**Primary doc:** `05-evals-and-docs.md`.

Scope highlights:
- `llm_nodes/eval.py` TARGET_CONTRACTS; `tools/capture_eval_recordings.py`
  (`parse_case_inputs`, `_adapter_for`, `_NODE_CONFIGS`).
- `backend/evalsets/eval_set_v3.json`: ~7 synthetic-résumé cases (dense,
  career-switcher, sparse fabrication-trap, prompt-injection, non-tech,
  variant-casing, fabricated-skill Flurbo.js) — each stamps
  `taxonomy_version`.
- Fixture recording committed under `evalsets/recordings/`; Tier-1 grading
  thresholds (schema-valid 1.0, ≤3 attempts); grader checks weak-spot
  membership + groundedness.
- Observability tests: call-log rows via the service (node name, `intake-`
  prefix, Haiku cost fields, hashes only); `run_llm_eval.py --strict`
  fails on a planted groundedness breach.
- Docs: flip this folder's README status to IMPLEMENTED with the commit
  list; `docs/dogfooding.md` walkthrough; check axiom 22 for four-node
  phrasing; `graphify update .`.
- **Optional live Haiku smoke — networked, ~$0.01 — ASK THE USER FIRST.**
- Verify the whole-branch definition of done in README (all four items,
  including the manual-path contract).

Kickoff prompt:

```
Read docs/implementation-plans/resume-intake-onboarding/SPLITS.md (Split 5),
then README.md, 05-evals-and-docs.md, and 06-skill-taxonomy.md in that
folder. Verify RI-A/B/C/D commits exist on branch resume-intake-onboarding —
if not, stop and ask. Then read backend/src/agentic_calendar/llm_nodes/
eval.py, tools/capture_eval_recordings.py, tools/run_llm_eval.py, an
existing eval set under backend/evalsets/, and
docs/axioms/22-llm-evaluation-and-observability.md. Implement increment RI-E
only, per CLAUDE.md. The live Haiku smoke is optional and networked — ask me
before running it. Gate: uv run make check green from backend/, then walk
the README definition-of-done checklist and report each item honestly.
```
