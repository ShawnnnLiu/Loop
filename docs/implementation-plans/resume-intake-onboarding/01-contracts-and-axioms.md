# RI-A · Contracts and Axioms (spec-first)

One commit. No adapter or app code — contracts, specs, axioms, fixtures,
generated schemas, and their tests only. Order inside the increment follows
the house workflow: axiom → spec → Pydantic → fixtures → `make schemas` →
tests.

## 1. Axiom amendments

### `docs/axioms/01-system-boundaries.md`

Amend "Allowed LLM Nodes" (currently `:13-24`, "Only four nodes"):

- Add `ResumeIntakeNode` — proposes structured profile-field candidates
  (experience, skills, strengths, inferred weak spots, target-company
  categories) from a pasted résumé plus draft onboarding answers, for the
  user to review and edit before any write.
- Add to the allowed-responsibilities section: propose candidates for
  user-editable profile fields during onboarding.
- Add to the forbidden list, explicitly:
  - never writes the profile — its output reaches storage only through the
    user-confirmed `POST /api/onboard` payload;
  - never proposes company names or prestige-ranked labels in
    target-company categories;
  - never assigns confidence values — provenance is structural (extracted /
    inferred / suggested by field group) and display-only; no deterministic
    code may route on it;
  - runs only on explicit user action (the Extract button), never
    automatically.
- Update the component/stage tables (`:110-146`) with one row: input =
  `resume_intake_input`, node = `ResumeIntakeNode`, output =
  `resume_extraction`, freeform = no (schema-bound), failure = invalid
  extraction schema, recovery = repair (≤2) then manual entry.
- Update the change log with date + rationale (D-3 revival, user-approved
  2026-07-06).

### `docs/axioms/03-data-contracts.md`

Add two contract lines to the object list:

- `resume_intake_input` — validated bundle handed to the ResumeIntakeNode.
  See `../specs/resume-intake-input.schema.md`.
- `resume_extraction` — schema-bound proposal returned by the
  ResumeIntakeNode. See `../specs/resume-extraction.schema.md`.

### `docs/axioms/09-cost-and-metrics.md`

- Re-add the Haiku tier to Pricing Assumptions: **Haiku-tier model
  (ResumeIntake; `claude-haiku-4-5`): $1.00 per 1M input tokens, $5.00 per 1M
  output tokens** (same figures as the pre-2026-07-04 mid-tier entry in the
  change log).
- Add one row to the Onboarding token-budget table: Résumé extraction ·
  `claude-haiku-4-5` · ~3,500 input · ~800 output · ~$0.008 (heuristic prior;
  user-initiated, ≥0 times per onboarding).
- Change-log entry: 2026-07-06, ResumeIntakeNode added on the Haiku tier;
  tables NOT regenerated (additive row, no existing figure moved).

## 2. Spec changes (`docs/specs/`)

### New: `resume-extraction.schema.md`

Owner: `ResumeIntakeNode`. Consumers: onboarding UI (display + edit), tests.
Fields (all lists default empty — **empty over fabrication**):

| Field | Type | Bounds | Provenance tier |
| --- | --- | --- | --- |
| `experience` | `list[ExperienceItem]` | ≤ 20 items | extracted (groundedness-checked) |
| `skills` | `list[str]` | ≤ 40 items, each 1–60 chars | extracted (groundedness-checked) |
| `known_strengths` | `list[str]` | ≤ 15 items, each 1–60 chars | inferred (résumé-anchored generalization) |
| `inferred_weak_spots` | `list[str]` | ≤ 15 items, each 1–60 chars | inferred (gap vs draft goal/role) |
| `target_company_categories` | `list[str]` | ≤ 8 items, each 1–60 chars | suggested |

`ExperienceItem`: `title` (1–120 chars, required), `organization`
(≤ 120 chars, optional), `summary` (≤ 280 chars, optional).

Spec-level invariants (mirrored by the deterministic post-validator in RI-B —
list them in the spec so prompt rules, validator, and spec cannot drift):

1. Every `ExperienceItem.title` and `.organization`, and every `skills` item,
   appears in the source résumé text (case-insensitive,
   whitespace-normalized substring).
2. No `target_company_categories` item contains an extracted organization
   string or a prestige-ranking term (denylist: `mid-tier`, `low-tier`,
   `bottom`, `mediocre`, `second-rate`, `b-tier`; keep the list in one place
   in code and quote it in the spec).
3. Case-insensitive uniqueness within each list.
4. No confidence numbers anywhere; the field grouping IS the provenance.

### New: `resume-intake-input.schema.md`

Owner: app layer (built from the extract request). Consumer:
`ResumeIntakeNode` (validated at the node boundary like `StrategistInput`).

- `user_id`: str, non-empty.
- `resume_text`: str, **50–40,000 chars** (a 3-char paste is a deterministic
  422, not an LLM call; 40k ≈ generous multi-page ceiling).
- `draft_context`: nested `DraftProfileContext`, all fields optional (the
  wizard may be partially filled): `goal`, `target_role`,
  `experience_level`, `timeline_weeks` (>0), `weekly_hours` (>0, ≤40).

Note in the spec: this is the first LLM input that exists **before any run**;
the service mints a `run_id` with prefix `intake-` for the call log (see
`02-node-and-harness.md`).

### Update: `user-profile.schema.md`

- Add `experience: list[ExperienceItem]` (≤ 20, default empty) — the user's
  confirmed work-experience entries; user-editable profile data, **not**
  consumed by Strategist/Planner prompts.
- Add `skills: list[str]` (≤ 40, default empty) — tools/stack tokens,
  distinct from `known_strengths` (broader capabilities).
- Widen `target_companies` semantics: "company names or company categories;
  extraction only ever proposes categories, users may add names manually."
- Add the **prompt-exposure table** from the README as a normative section:
  which profile fields reach which node's prompt. `experience` joins
  `resume_text` in the Strategist exclusion set (code change lands in RI-B;
  the spec is the source of truth from this commit on).

### Update: `llm-call-log.schema.md`

- Add `resume_intake` to the node-name enum, and document the `intake-`
  run_id prefix for pre-run calls.

### New: `skill-taxonomy.schema.md` (+ `docs/axioms/08` subsection)

Per `06-skill-taxonomy.md`: `CareerTrack` closed enum (shared with the
grounding-RAG corpus — whichever branch lands first creates
`contracts/career_track.py`), `SkillEntry` (slug id, display name, globally
unique lowercase aliases, track tags, kind, nullable `corpus_evidence`),
`SkillTaxonomy` (versioned, unique ids). Plus:

- `ResumeIntakeInput` gains `allowed_weak_spots: list[str]` (filled by the
  service from the taxonomy; the node never imports the kernel).
- Seed vocabulary `backend/taxonomy/skill_taxonomy_v1.json` (~60–100 SWE,
  ~30–40 each MLE/AI-engineer) — **user reviews the seed in this commit**;
  the review is the curation gate.
- Axiom 08 gains the "Controlled vocabularies" subsection (canonical,
  versioned, curated in review; LLMs never write entries; normalization
  deterministic; evidence annotates, never auto-creates; no user data).

## 3. Pydantic contracts (`backend/src/agentic_calendar/contracts/`)

- `resume_extraction.py`: `ExperienceItem`, `ResumeExtraction` — frozen,
  `extra="forbid"`, bounds via `Field`/`StringConstraints`, uniqueness
  validators. One module per spec, matching house style.
- `resume_intake_input.py`: `DraftProfileContext`, `ResumeIntakeInput`.
- `user_profile.py`: add `experience` + `skills` after `known_weaknesses`
  (additive, defaults empty — every existing fixture stays valid); reuse
  `ExperienceItem` by import from `resume_extraction.py`? **No** — contracts
  modules are one-per-spec; put `ExperienceItem` in `user_profile.py` (it is
  profile vocabulary) and have `resume_extraction.py` import it from there.
  Update the `resume_text` docstring to name the two consumers (Strategist
  raw block + ResumeIntakeNode input).

Also `career_track.py` and `skill_taxonomy.py` contract modules (one per
spec, per `06-skill-taxonomy.md`).

No `reason_codes.py` changes — existing generation codes cover every failure.

## 4. Fixtures + generated schemas + tests

- Valid fixtures: a full `ResumeExtraction`, an all-empty one, a
  `ResumeIntakeInput` with and without draft context, an updated
  `UserProfile` fixture carrying `experience`/`skills`.
- Invalid fixtures **with expected structured violations** (house pattern):
  over-long lists, empty `title`, résumé under 50 chars, duplicate skills,
  extra field.
- `make schemas` after the contract models land; commit the generated JSON.
- Tests: contract round-trips, bound violations, fixture suites, and a spec
  test asserting the Strategist exclusion set named in the spec matches the
  adapter constant once RI-B lands (write it `xfail`/skipped here or defer
  the assertion to RI-B — implementer's choice, but do not let the exposure
  table go untested).

Gate: `uv run make check` green from `backend/`.
