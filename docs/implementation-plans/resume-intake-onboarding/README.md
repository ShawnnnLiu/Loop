# Résumé Intake Onboarding — Extract → Review → Confirm

Status: **planned, not started.** Branch: `resume-intake-onboarding` from
`main` after the `calendar-authoritative-moves` PR merges (see Sequencing).

Provenance: design session 2026-07-06, grounded in a code exploration of the
onboarding surfaces and the LLM-node harness. All file references verified on
branch `calendar-authoritative-moves` at that date. This revives the deferred
**D-3 Résumé Parser Node** (`phase-loop-mvp-backend.md` §Deferred) with the
design-reference mockup `docs/design-reference/design-loop/onboarding.jsx`
(step 5) as the visual target.

## The feature, one paragraph

On a consolidated onboarding step, the user pastes their résumé and presses an
explicit **Extract** button. A new lightweight LLM node (`ResumeIntakeNode`,
`claude-haiku-4-5`) reads the résumé plus the draft answers from earlier wizard
steps and returns one schema-bound proposal: experience entries, skills,
strengths, inferred weak spots, and target-company **categories** (never
company names). The frontend renders the proposal as fully editable fields
(add / delete / change). Nothing persists until the user finishes the wizard
through the existing `POST /api/onboard` — the human review gate plus
deterministic schema validation are the disposal side of "LLMs propose,
deterministic infrastructure disposes."

## Locked decisions (user, 2026-07-06)

1. **New `experience` + `skills` profile fields** — but schemas stay clean and
   **detached from prompts that don't need them** (prompt-exposure table
   below; `experience` is excluded from the Strategist bundle the way
   `resume_text` already is).
2. **Consolidate**: the current Skills step (step 2) merges into the résumé
   step; the wizard goes 5 steps → 4.
3. **Explicit Extract button** — no auto-extract on paste.
4. **Haiku for now** (`claude-haiku-4-5`, $1.00/$5.00 per MTok — the tier
   axiom 09 already priced before the 2026-07-04 Sonnet upgrade).
5. **Target companies: suggested categories only.** The node never extracts or
   proposes company names into targets, and never uses prestige-ranking
   language ("mid-tier", "low-tier", …). It DOES extract work experience and
   lets it inform `skills` and `known_strengths`.
6. **Paste only.** PDF/DOCX upload and LinkedIn URL stay deferred (per the
   original D-3 note, file storage is separate work).
7. **All rule changes in scope**: axiom 01 gains a fifth allowed node class;
   axioms 03/09 and the specs/fixtures/schemas follow the spec-first workflow.
8. *(follow-up, same day)* **Skills are vocabulary, not free invention.**
   Extracted skills must resolve against a canonical, field-specific skill
   taxonomy connected to the grounding-RAG corpus (shared career-track enum;
   corpus-evidence enrichment once that pipeline exists). Full mechanism in
   `06-skill-taxonomy.md`.

## Design constraints (non-negotiable)

- **Fifth node class is an axiom amendment, not a workaround.** Axiom
  `01-system-boundaries.md:13-24` says only four nodes may call an LLM; RI-A
  amends it deliberately, with the node's allowed/forbidden responsibilities
  written down before any code.
- **Provenance is structural, not scored.** The mockup's three confidence
  tiers map to field groups: `experience`/`skills` = *extracted*
  (deterministically groundedness-checked against the résumé text),
  `known_strengths`/`inferred_weak_spots` = *inferred*,
  `target_company_categories` = *suggested*. No per-item confidence values —
  LLMs do not assign confidence (axiom 00/08); the UI labels sections, and
  nothing routes on provenance.
- **Prompt exposure is explicit.** New profile fields reach only the prompts
  that need them. Canonical table (also lands in
  `docs/specs/user-profile.schema.md`):

  | Profile field | ResumeIntake | Strategist bundle | Planner |
  | --- | --- | --- | --- |
  | `experience` (new) | output only | **excluded** (noise; raw résumé block already covers background) | no |
  | `skills` (new) | output only | included | no |
  | `known_strengths` / `known_weaknesses` | output only | included (coverage rule) | weaknesses only (unchanged) |
  | `target_companies` | output only (categories) | included (unchanged) | no |
  | `resume_text` | input (labeled raw block) | excluded from bundle, appended as labeled raw block (unchanged) | no |

- **Skills resolve against a controlled vocabulary; the LLM never touches
  the vocabulary.** The node extracts surface strings only
  (groundedness-checked); a deterministic normalizer in a new
  `skill_taxonomy/` kernel maps them onto a versioned, human-curated
  taxonomy (`backend/taxonomy/skill_taxonomy_v1.json`); unmatched surfaces
  are returned visibly flagged and never become canonical skills.
  `inferred_weak_spots` is a **closed choice** from the track-relevant
  taxonomy slice, membership-enforced in the repair loop. The taxonomy
  shares the `CareerTrack` enum with the grounding-RAG corpus and gains
  corpus-derived evidence in gated increment RI-F. See
  `06-skill-taxonomy.md`.
- **The extract path is persistence-free.** `POST /api/onboard/extract`
  validates input, runs the node, returns the proposal. No store writes; the
  only write path remains `POST /api/onboard` on wizard finish. Skip and
  manual entry must keep working — extraction is an enhancement, never a
  blocker.
- **Typed failure surface.** Reuses the existing generation reason codes
  (`LLM_MALFORMED_OUTPUT`, `LLM_SCHEMA_REJECTED`, `LLM_REFUSAL`,
  `LLM_TRUNCATED`, `LLM_RETRY_LIMIT_EXCEEDED`, `REPAIR_LIMIT_EXCEEDED`,
  `LLM_AUTH_FAILED`, `LLM_RATE_LIMITED`); no new codes. HTTP 200 + typed
  `reason_code` for workflow failures, 422 for invalid payloads, per the
  `routes_cycle.py` mapping rules.
- **Privacy unchanged.** Résumé text is PII: prompt/response are hashed in the
  LLM call log, never stored raw (existing `_GenerationEngine` behavior);
  résumé text lives only on the user's own profile.
- **Injection posture.** Pasted résumés are untrusted text: labeled
  data-not-instructions block (existing Strategist pattern), schema-bound
  JSON output, deterministic post-validation, and a same-user review gate.

## Files / increments (one commit per lettered increment)

| File | Increment |
| --- | --- |
| `01-contracts-and-axioms.md` | RI-A axiom amendments (01/03/09) + specs + Pydantic contracts + fixtures + `make schemas` |
| `02-node-and-harness.md` | RI-B fixture twin + Anthropic adapter (Haiku config, prompts, groundedness post-validate) + call-log enum |
| `03-app-and-api.md` | RI-C `POST /api/onboard/extract` + environment/bundle wiring + keyless dev |
| `04-frontend.md` | RI-D consolidated wizard step, Extract button, editable sections, api client + vitest |
| `05-evals-and-docs.md` | RI-E eval-set cases + capture-CLI registration + docs/dogfooding notes |
| `06-skill-taxonomy.md` | Controlled skill vocabulary + RAG seam; work folded into RI-A/B/C/D/E per its build-order table, plus gated **RI-F** corpus-evidence enrichment (after grounding-RAG G-A–G-D) |

## Sequencing

- Branch from `main` after the `calendar-authoritative-moves` PR merges.
  Overlap with the other planned tracks is light: `loop-grounding-rag` and
  `scheduler-placement-quality` touch different regions; shared files are
  `app/cycle.py`, `routes_cycle.py`, `environment.py` (additive here) —
  rebase-friendly.
- Usual conventions: one commit per increment, spec/axiom-first for every
  contract change (`docs/axioms/` + `docs/specs/` before Pydantic before
  fixtures before `make schemas`), gates green per commit (`uv run make
  check` from `backend/`, `npm run typecheck && lint && test && build` from
  `frontend/` for RI-D), `graphify update .` after code changes.
- Each increment is small enough for one session; RI-A→RI-E can also run as a
  single clean-context handoff using the kickoff prompt below.

## Ask-user gates (standing, per the operating contract)

- No new dependencies, no schema-generation surprises expected. Everything is
  local deterministic work **except** an optional end-of-project live smoke of
  the real Haiku adapter (networked, costs ~$0.01) — ask before running it.
- The axiom-01 amendment wording ships in the RI-A commit; the user has
  pre-approved the change in principle (decision 7) and reviews the wording at
  commit time.

## Cost note (axiom 09)

One extract call ≈ 3–4k input tokens (system + exemplar + 2-page résumé +
draft context) and ≤ 1k output on `claude-haiku-4-5` ≈ **$0.005–0.01 per
press**, user-initiated only. RI-A adds the Haiku pricing row and an
onboarding-budget line; monthly caps are unaffected at MVP scale.

## Definition of done (whole project)

1. In the keyless dev server (`python -m agentic_calendar.app.web`), the
   consolidated step renders, Extract fills the five sections from the
   fixture node, every field is editable, and finishing the wizard persists
   exactly what the user confirmed — verified in a real browser, not just
   curl.
2. Groundedness holds by construction: on the eval set (incl. an
   injection-attempt résumé and a sparse résumé), every extracted experience
   organization/title and every skill appears in the source text; zero
   company names and zero prestige-tier words in
   `target_company_categories`; failures surface typed reason codes.
   Vocabulary holds by construction too: a résumé with a made-up skill
   yields it in `skills_unmatched`, never canonical; no weak spot outside
   the taxonomy survives the repair loop.
3. `uv run make check` green (all suites incl. new contract/fixture/boundary
   tests); frontend gates green; `.importlinter` untouched and passing (the
   node lives in `llm_nodes/`).
4. Axioms 01/03/09 and the specs read as if the node had always been planned
   — no drift between the prompt rules, the post-validator, and the spec.

If extraction works but a hand-typed profile can no longer be entered when
the LLM is down, it isn't done — the manual path is the contract.

## Kickoff prompt (copy-paste into a fresh session)

```
Read docs/implementation-plans/resume-intake-onboarding/README.md, then the
six numbered docs in that folder, then docs/axioms/01-system-boundaries.md,
docs/specs/user-profile.schema.md, and
backend/src/agentic_calendar/llm_nodes/ (base.py, strategist.py,
anthropic_adapter.py, call_log.py). Implement increments RI-A through RI-E in
order, one commit per increment, following the repo's CLAUDE.md operating
contract (spec/axiom-first, gates green per commit, ask before networked
commands). Start by restating the increments and any open decisions the docs
flag, then begin RI-A.
```
