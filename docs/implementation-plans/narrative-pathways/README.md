# Narrative Pathways — Character Sheet → Chosen Story → Evidence-Slotted Plan

Written 2026-07-15. Status: **implemented in Loop (NP-A … NP-F).** The
career-pathway story layer is built on branch `narrative-pathways`: curated
`PathwayTemplate` registry, the deterministic `narrative/` fit/gap kernel,
evidence tagging inside `ResumeIntakeNode`, pathway selection + syllabus
invalidation, the story frontend, and the two `UserFacingExplanationNode` prose
targets. The knowledge-map (KT-A … KT-D, `06-…`) and mastery-memory
(MM-A … MM-C, `08-…`) series remain planning docs. This document's original
proposals below are preserved as the design record; the per-increment landings
are the table that follows.

## Increment landings (Loop, NP-A … NP-F)

One commit per lettered increment, spec/axiom-first, `uv run make check` green
per commit (frontend four gates for NP-E/NP-F).

| Increment | Commit(s) | What landed |
|---|---|---|
| NP-A | `f9e2d82` (+ `5bd0e6d` follow-up) | Axioms, two new specs (`pathway-template`, `pathway-selection`), Pydantic contracts + amendments, valid/invalid fixtures, five reason codes, `EvidenceKind` enum; shared dedup helper + slot-override referential integrity. |
| NP-B | `3f23c6e` | `narrative/` kernel (`slot_coverage`/`pathway_fit`/`story_progress`), curated pathway registry in `templates/`, five seed pathways for swe/mle/ai_engineer, track-scoped theme vocabulary. |
| NP-C | `0b71bee` | `ResumeIntakeNode` proposes evidence `kind` + closed-vocabulary `theme_tags`; `allowed_themes` bundle + repair-loop membership; eval set v8, prompt-version bump. |
| NP-D | `a5554a8`, `98d774b`, `f43fdf4`, `ca36203` | Validation-layer slot gate (3 reason codes); `GET /api/pathways` + `StrategyConstraints` unfilled-slot plumbing + Strategist prompt v6; onboard selection validation + pathway-change invalidation; `POST /api/evidence`. |
| NP-E | `2416ef8` | Story frontend: wizard "Your story" step, evidence tag editors, Progress story panel + mark-evidence, Tuning change-pathway; three supporting endpoints (draft preview, evidence-vocabulary, select_pathway). |
| NP-F | *(this increment)* | The two `UserFacingExplanationNode` prose targets — batched pathway **fit notes** and the user-initiated **story summary** (Haiku tier, deterministic post-checks: prestige denylist + psych-label denylist + no-numerals-as-scores) with a deterministic twin; `POST /api/pathways/fit-notes` + `POST /api/story-summary`; call-log/axiom-09 observability; this README + `docs/dogfooding.md` story loop. |

The design proposals below predate implementation. Where a schema or reason code
was refined during the spec-first workflow, the landed spec in `docs/specs/` and
the axioms are authoritative.

Provenance: product design session 2026-07-15, grounded in the shipped résumé
intake (`../resume-intake-onboarding/`), the career-track expansion research
(`../career-track-expansion/`), the milestone-template registry
(`../../specs/milestone-template.schema.md`), and the current onboarding
wizard (`frontend/src/lib/intake.ts` — `Goal → Time & constraints → Résumé &
profile → Connect`).

## The idea, one paragraph

Strong candidates — for jobs and for college — don't present a pile of
disconnected activities; they present a **package**: a coherent story where
projects, work, volunteering, and skills reinforce one claim about who they
are. Today the product plans *study time* toward a goal. This feature makes it
plan *a story*: onboarding dissects the user's current "character" (their
confirmed evidence inventory), shows them curated **pathways** — narrative
packages they could build toward ("Applied ML Specialist", "AI-Integration
Engineer"; later "healthcare-committed scientist", "community-builder
sociologist") — and lets them **choose one, like picking a class in a game**.
The chosen pathway defines **evidence slots** (the pillars a coherent version
of that story needs: depth projects, breadth, leadership, public artifacts).
Unfilled slots become the gaps the Strategist plans against; filled slots
become visible story progress. Career prep in Loop first; college admissions
in Tandem as the end state, where the same spine grounds essay work.

## How it obeys the thesis

**LLMs propose. Deterministic infrastructure disposes** — applied to
narrative:

- **Pathways are a curated registry, not LLM inventions.** `PathwayTemplate`s
  are deterministic literals, exactly like `MilestoneTemplate`s
  (`templates/registry.py`) and the skill taxonomy
  (`backend/taxonomy/skill_taxonomy_v1.json`). LLM research may draft them;
  review is the gate (axiom 08 controlled-vocabularies wall).
- **The character sheet is evidence, not personality.** It is the confirmed
  profile (`experience`, `skills`, strengths) plus proposed-then-confirmed
  theme tags. No psychological labels, no LLM-inferred identity — the axiom-00
  principle "motivation is product state" extends to "narrative is product
  state."
- **Fit and gaps are computed deterministically.** Pathway fit = which
  evidence slots the confirmed inventory fills, a pure function mirroring
  prerequisite computation. LLMs never assign fit scores (same rule as source
  confidence). The UI shows honest slot counts ("3 of 6 pillars"), not
  invented percentages.
- **Selection is an explicit user gate.** No pathway is active until the user
  picks it; skipping keeps today's behavior exactly. Changing pathway creates
  a new profile version and invalidates the syllabus like a target-role change
  (`user-profile.schema.md` update-policy table gains a row).
- **The chosen pathway is typed control-plane state.** It reaches the
  Strategist as structured constraint extensions, never as prose. Modules can
  declare which slot they build toward; the validator checks the linkage with
  typed reason codes.

## Doc map

| Doc | What it holds |
|---|---|
| `01-product-design.md` | The product end-to-end: character sheet, pathway cards, the choose-your-story step, slot progression, gamification stance, ethics (packaging truth ≠ fabricating it), what this is NOT. **Read first.** |
| `02-contracts-and-registry.md` | The deterministic core: `EvidenceItem` amendment, `PathwayTemplate` registry + evidence slots + theme vocabulary, `PathwaySelection`, the `narrative/` fit/gap kernel, strategist-constraint and syllabus-module extensions, axiom deltas, new reason codes. |
| `03-llm-surfaces.md` | What LLMs propose and where: ResumeIntakeNode tag extension, UserFacingExplanationNode story summaries, why **no new node class** is needed in Loop, prompt-exposure table, groundedness posture, cost. |
| `04-loop-increments.md` | NP-A…NP-F Loop implementation increments (one commit each), seed pathway content for the three live tracks, definition of done. |
| `05-tandem-vision.md` | The admissions end state: activity-shaped evidence, major-anchored pathways, the essay-editor seam (the future sixth node class), counselor visibility via the existing sponsor layer, staging gates. |
| `06-knowledge-tree.md` | The **knowledge map** (added 2026-07-16 as a DAG; reworked 2026-07-19 to expandable groups, filename kept): per-**account** map of group nodes that click-expand into skill nodes, four deterministic mastery tiers, the **add-only onboarding rule**, user customization (vocabulary-picked node additions that feed planning; user-created named groups/nodes + descriptions + private notes as a **personal layer that never counts toward pathway progress or enters prompts**; per-node mastery set-points incl. downward), KT-A…KT-D increments. Never a second prerequisite engine. Design canvas (`docs/design-reference/Loop - Pathway Map.html`) needs a re-pass for the group interaction. |
| `07-tree-generation.md` | How knowledge maps come to exist (added 2026-07-17 for the DAG; reworked 2026-07-19 for groups): deterministic generation from a curated, versioned **skill grouping** (group assignment + minutes prior + blurb per `skill_id`) and per-slot seed skills; build-time `make maps` / `maps-check` tool with committed, byte-identical output; g-series open decisions. No edges, no cycles — generation is membership lookup. |
| `08-mastery-memory.md` | Completions that shape the next plan (added 2026-07-19): optional `solve_confidence` triage at check-off, the three-source **mastery basis fold** (confidence-weighted telemetry + add-only onboarding grants + user set-points, the only path down), skill-keyed and permanent across plan versions, and a typed `StrategyConstraints` mastery slice so regeneration stops re-assigning honed skills and allocates bounded review instead. Amends `06-…`'s non-interference rule with one advisory-context exception; MM-A…MM-C increments; m-series open decisions. |

## How these docs plug into existing plans

- **`resume-intake-onboarding/`** (shipped): the character sheet's raw
  material. NP-C extends `ResumeExtraction` additively (evidence `kind` +
  `theme_tags` proposals, both closed-vocabulary, enforced in the existing
  repair loop). RI-F enrichment discipline (pinned snapshots, human review)
  is the model for pathway-registry curation.
- **`career-track-expansion/`**: the nine researched career profiles are the
  content quarry for career pathway templates. A pathway is finer-grained
  than a `CareerTrack` — several pathways can live inside `swe` (the profiles
  already note frontend/backend/full-stack stay inside `swe`; pathways are
  where that intra-track shaping finally gets a home).
- **`milestone-template.schema.md` / `templates/registry.py`**: the
  registry-of-deterministic-literals pattern `PathwayTemplate` copies. The
  `college_admissions` and `graduate_admissions` goal classes already exist
  there — Tandem's skeleton was always planned; pathways give it its spine.
- **`loop-grounding-rag/`**: future, gated — pathway templates can gain
  corpus evidence the way taxonomy entries do in RI-F ("postings for X
  commonly ask for Y+Z together"), keeping registry curation honest. Not in
  Loop scope.

## Staging

1. **Loop (this plan, NP-A…NP-F):** career pathways only, three live tracks
   (`swe`, `mle`, `ai_engineer`), one new wizard step, story panel in
   Progress. No essay features, no new LLM node class.
1b. **Knowledge map (KT-A…KT-D, `06-…`):** the per-account grouped map +
   mastery tiers + customization + map UI; interleaves with or follows the
   NP series (KT-A/B need NP-B, KT-C needs NP-D, KT-D needs NP-E).
1c. **Mastery memory (MM-A…MM-C, `08-…`):** confidence triage capture +
   mastery-aware generation; follows the KT series (MM-A needs KT-A, MM-B
   needs KT-B, MM-C needs KT-C; KT-D independent).
2. **Track expansion interlock:** each career landed via
   `career-track-expansion/` should land its 2–4 pathway templates in the
   same review, once the registry exists.
3. **Tandem:** activities vocabulary, major-anchored pathways, essay editor
   (new node class, new axiom-01 amendment), counselor reporting. Gated on
   Loop pathway proof (see `05-tandem-vision.md` for the explicit gates).

## Open decisions (flagged for the user)

1. **Single pathway in Loop** (proposed): one primary pathway per profile;
   secondary/combo pathways deferred. Combos are real ("bio background +
   CS projects") but multiply UI and validation surface — Tandem revisits.
2. **`experience` field name stays** (proposed): `EvidenceItem` lands as an
   additive amendment of `ExperienceItem` (`kind` default `work`,
   `theme_tags` default empty) rather than a rename/migration. Revisit the
   name only if a real migration is ever needed.
3. **Slot counts, not scores** (proposed): fit display is "n of m pillars,"
   never a percentage or letter grade — honest under the heuristic-priors
   axiom, still game-like.
4. **Registry curation ownership**: same human-review gate as the taxonomy;
   whether pathway content review needs a second pair of eyes beyond the
   normal commit review is the user's call.
5. **Knowledge-map decisions d1–d6** (tier names — now four, `locked`
   resolved by removal; honed threshold basis; map size + group
   granularity; group expansion interaction; whether a map can exist
   without a pathway selection): see the open decisions section of
   `06-knowledge-tree.md`.
6. **Map-generation decisions g2–g4** (hand overrides still none in v1,
   blurb home, group granularity; g1 transitive reduction resolved by
   removal — no edges exist): see `07-tree-generation.md`.
7. **Mastery-memory decisions m1–m6** (confidence weights, triage surface,
   mastered = honed vs proven, advisory vs hard exclusion, interval review
   parked, onboarding grant sizing): see `08-mastery-memory.md`.

## Kickoff prompt (copy-paste into a fresh session, when implementation is approved)

```
Read docs/implementation-plans/narrative-pathways/README.md, then the eight
numbered docs in that folder, then docs/specs/milestone-template.schema.md,
docs/specs/user-profile.schema.md, docs/specs/resume-extraction.schema.md,
docs/specs/strategy-constraints.schema.md,
backend/src/agentic_calendar/templates/registry.py, and
backend/src/agentic_calendar/skill_taxonomy/. Implement increments NP-A
through NP-F in order, one commit per increment, following the repo's
CLAUDE.md operating contract (spec/axiom-first, gates green per commit —
`uv run make check` from backend/, frontend gates for NP-E — ask before
networked commands or new dependencies). Start by restating the increments
and the open decisions the docs flag, then begin NP-A.
```
