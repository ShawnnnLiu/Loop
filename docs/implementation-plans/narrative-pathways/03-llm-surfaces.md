# 03 · LLM Surfaces — What Gets Proposed, and by Whom

The headline: **Loop needs no new LLM node class.** The story layer adds two
propose surfaces, both inside already-allowed nodes, both disposed of by the
deterministic core in `02-…`. The sixth node class (essay work) is Tandem's
and gets its own axiom-01 amendment there — see `05-tandem-vision.md`.

## Surface 1 — evidence tagging, inside `ResumeIntakeNode`

The intake node already extracts `experience`; NP-C extends the proposal so
each item also carries:

- `kind` — from the closed `EvidenceItem` kind enum;
- `theme_tags` — from the track's slice of the registry theme vocabulary,
  embedded in the prompt exactly like the weak-spot `display_name` slice is
  today (`resume-intake-input.schema.md` gains an `allowed_themes` list;
  budget re-check: taxonomy slice ≤ ~100 + themes ≤ ~30 must stay cheap on
  Haiku).

Enforcement mirrors the shipped weak-spot mechanism one-for-one:

- Membership checked deterministically in the bounded repair loop; a
  persistent out-of-vocabulary tag → `REPAIR_LIMIT_EXCEEDED`, never a
  silently coined theme.
- `kind` is the node's classification of grounded evidence — the item itself
  stays groundedness-checked against the résumé text (invariant 1 of
  `resume-extraction.schema.md`, unchanged). A wrong `kind` is a user-edit
  away from correct; it routes nothing.
- Empty-over-fabrication: no tags is a valid proposal.
- Everything lands in the same editable review UI; nothing persists except
  through the user's confirm.

The same closed vocabularies drive the manual path: a user who skips
extraction picks `kind` and `theme_tags` from the same dropdowns. **The
vocabulary constrains the LLM, not the person** only for free-text fields
like `skills`; tags are join keys for the deterministic kernel, so they stay
closed for humans too (with "no tag" always allowed).

## Surface 2 — story prose, inside `UserFacingExplanationNode`

Two new prompt targets, both explanation-only, both generated from confirmed
structured state (never from the raw résumé):

1. **Pathway fit note** (per card, on the Your-story step): input is the
   deterministic coverage result (matched items per slot) + the template
   spine; output is 2–3 sentences of "here's why your existing evidence
   carries these pillars." It decorates a ranking that already happened.
2. **Story summary** (Progress panel, user-initiated refresh): input is the
   selection + slot states + recent completions; output is the "where your
   package stands" paragraph.

Bounds carried over verbatim from the node's existing rules: prose is never
parsed, never stored as control-plane state, never re-enters any prompt as
authority. Prestige-term denylist applies to outputs as a deterministic
post-check (same constant as the extraction adapter).

## Why not a new "PathwayAdvisorNode"

The tempting design — an LLM that looks at the whole picture and *recommends
a pathway* — was considered and rejected for Loop:

- Recommendation is a **ranking**, and ranking is disposal, not proposal.
  The kernel's slot coverage already orders the cards from confirmed data;
  an LLM layered on top would either agree (redundant) or disagree
  (unaccountable — exactly the "LLM assigns confidence" failure mode axiom
  08 walls off).
- The genuinely LLM-shaped parts — tagging surfaces and explaining fit — fit
  the two existing surfaces above with no new authority.
- The *choice* belongs to the user. A recommender that pre-picks would
  undercut the product's own class-selection framing.

If Tandem's richer inputs (essays, interests, values prompts) ever justify a
holistic advisory node, that is a deliberate axiom-01 amendment with its own
allowed/forbidden table — the RI-A precedent shows how.

## Prompt exposure (normative delta to `user-profile.schema.md`'s table)

| Profile field | ResumeIntake | Strategist bundle | Planner | Explanation node |
| --- | --- | --- | --- | --- |
| `experience[].kind` / `.theme_tags` | output only | **excluded** (like `experience` itself — the gap list already encodes what matters) | no | via coverage result only |
| `pathway_selection` | no | **as typed constraints only** (`pathway_id` + computed `unfilled_slots` in `StrategyConstraints`; never the template prose) | no | yes (id + slot states) |

The Strategist bundle exclusion set (`{"resume_text", "experience"}`) is
unchanged — pathway shaping arrives through `strategy_constraints`, keeping
the bundle-exclusion test meaningful.

The Strategist prompt gains one addition (NP-D): when `unfilled_slots` is
present, propose up to `max_slot_modules` modules that build toward those
slots, carrying `evidence_slot_id` and citing the slot title in `reason`.
`gap_module_hint` seeds the wording. The deterministic gate rejects unknown
slot ids and over-limit counts (reason codes in `02-…` §6/§8).

## Injection and privacy posture

Unchanged from the shipped intake: résumé text remains the only untrusted
raw block, already labeled data-not-instructions; theme vocabulary and
pathway templates enter prompts as system-side structured lists (curated
literals, not user text). Prompt/response hashing in the LLM call log covers
the new targets with no schema change (`llm-call-log.schema.md` enum gains
the two explanation targets in NP-F). No new PII: tags and selections are
non-sensitive structured fields on the existing profile record.

## Cost (axiom 09 note for NP-A)

- Tagging rides the existing extract call: +~300–600 input tokens (theme
  slice) and +~200 output tokens per press on `claude-haiku-4-5` —
  extraction stays ≈ $0.01, user-initiated.
- Fit notes: one small call per rendered card set (batched: one call
  returning notes for the top N cards, N ≤ 4), Haiku, ≈ $0.005; generated
  once per Your-story visit, cached on the client for the session.
- Story summary: user-initiated only, Haiku, ≈ $0.005.

No background LLM calls anywhere in the feature. Monthly caps unaffected at
MVP scale; NP-A adds the budget lines.

## Eval additions (NP-C / NP-F, house pattern)

- Intake eval set v4: tagged-extraction cases — a résumé with clear
  project/volunteering split; an off-vocabulary theme attempt (must repair
  or fail typed); a sparse résumé (tags stay empty).
- Explanation targets: fixture-driven contract checks only (prose length,
  denylist, no numerals presented as scores) — prompt wording is not a test
  oracle.
