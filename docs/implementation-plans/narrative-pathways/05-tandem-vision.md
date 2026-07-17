# 05 · Tandem Vision — Admissions as the End State

Tandem (同舟 — the old admissions product name; design reference in
`docs/design-reference/landing/` and the Admissions Copilot briefs under
`docs/design-reference/uploads/`) is where the story layer stops being a
feature and becomes the product. Everything here is **directional** — no
Tandem increment is scheduled; the point of writing it now is to make sure
Loop's contracts are shaped so none of this requires rework.

## Why admissions is the stronger fit

Career users have résumés; admissions users have *four years* and a blank
slate. The coherent-package problem is more acute (readers explicitly
evaluate narrative), the timeline is longer (evidence can actually be
planned and built, not just repackaged), and the calendar-accountability
engine matters more (a 15-year-old choosing between activities needs
scheduled execution, not advice). The product thesis already names
admissions as an adjacent segment requiring no architectural change; the
milestone registry already carries `college_admissions` and
`graduate_admissions` goal classes. Pathways supply what those skeletons
lack: *which* activities, *why they cohere*, and *what to build next*.

## What generalizes cleanly (by design of the Loop contracts)

| Loop object | Tandem generalization |
| --- | --- |
| `EvidenceItem` kinds | already include `volunteering`, `leadership`, `research`, `award`, `coursework` — the Common-App activity shape. Tandem raises the list cap (10 activities + honors + coursework exceeds 20) — a scoped spec change. |
| Theme vocabulary | new registry pools: `healthcare`, `community-service`, `civic-engagement`, `scientific-research`, `arts-performance`, … Same closed-vocabulary wall. |
| `PathwayTemplate.career_track` | becomes an anchor union: career track **or major-cluster** (`bio-premed`, `sociology-community`, `engineering-builder`, `humanities-writer`, …). The anchor was speced as a join key, not a career, for exactly this. |
| `narrative/` kernel | unchanged — coverage, fit, and progress are anchor-agnostic pure functions. |
| Selection gate, replan semantics, slot-linked modules | unchanged. |
| Sponsor layer (Phase 3 / axiom 21) | the counselor/parent surface: story-progress summaries are sponsor-report content under existing permission levels — pillars-filled counts, never essay text, never raw activity detail beyond what the user's permission tier allows. |

Example Tandem pathways (content sketches, to make the shape concrete):

- **Healthcare-committed scientist** (bio/pre-med): hospital or clinic
  service (sustained, not one-off), science depth (research or advanced
  coursework), a community-health project bridging the two, a public
  artifact (fair, publication, talk).
- **Community-builder** (sociology/public policy): local-org service
  depth, a leadership role with measurable scope, an original project
  (survey, program, zine), civic breadth.
- **Builder-engineer** (CS/engineering): shipped projects ×2 with distinct
  themes, a team artifact (club, competition), a sustained deep skill, a
  public writeup. (Note: this is Loop's card with the kinds widened —
  the two products literally share templates at the boundary, which is the
  bridge story for a Loop user's younger sibling.)

The user's own combination insight is the key content rule: the best Tandem
templates have **bridging slots** that force two of the user's existing
themes into one artifact ("community-health project", "tech-for-shelter
tool"). Bridging is where "exhilarating, coherent" stories come from, and it
is expressible today as a slot with two `required_themes_any` groups —
worth a v2 slot field (`required_themes_all_groups`) if content demands it.

## What is genuinely new in Tandem

1. **The essay editor — the sixth LLM node class.** A deliberate axiom-01
   amendment with its own allowed/forbidden table, RI-A precedent:
   - *Allowed:* propose outlines and drafts **grounded in confirmed
     evidence items** (each draft paragraph carries the evidence ids it
     draws on — the grounding-RAG citation discipline applied to the user's
     own record); propose revisions against user-stated prompts.
   - *Forbidden:* inventing experiences (groundedness check against the
     character sheet is the disposal step — a claim with no backing
     evidence item is flagged, not polished); assessing admissibility;
     ranking schools; any confidence about outcomes.
   - The ethics line from `01-…` hardened: the editor's job is *articulating
     what the user did*. The four-year engine exists so there is something
     true to articulate — that is the product's answer to the essay-mill
     comparison, and the marketing story writes itself from the axioms.
2. **Longer horizons.** Multi-year pathway progress vs. Loop's
   weeks-scale plans: milestone templates (offset-days-before-deadline)
   compose with pathways — slots gain optional target seasons ("research
   by end of junior year"). Scheduler unchanged; this is planning-layer
   composition.
3. **Guardian consent.** Minors: consent records (Phase 6 machinery)
   precede any sponsor visibility; stricter PII stance on evidence items.
4. **Application-cycle mechanics.** School lists, deadlines-as-milestones,
   requirement tracking — the `graduate_admissions`/`college_admissions`
   milestone skeletons, finally exercised. Deterministic throughout.

## Staging gates (explicit, so Tandem doesn't start on vibes)

1. Loop NP-A…NP-F shipped and dogfooded; at least one real user selects a
   pathway and fills a slot from a plan-generated module ("mark evidence"
   fired in anger).
2. Career-track expansion has proven the registry pattern scales (≥ 2 more
   tracks landed with their pathway templates).
3. Anchor-union spec change (career track | major-cluster) lands as its own
   reviewed increment before any admissions content.
4. Essay node class only after the Tandem onboarding + pathway loop works
   without it — prose is the *last* capability, not the first, in a product
   whose thesis is that structure beats prose.

## Cross-references

- `../../axioms/00-product-thesis.md` — admissions as adjacent segment;
  what the MVP excludes (parent surveillance, therapy) binds Tandem too.
- `../../specs/milestone-template.schema.md` — the admissions goal classes.
- `../../axioms/21-accountability-layer.md` + Phase 3 — counselor
  visibility rails.
- `../resume-intake-onboarding/06-skill-taxonomy.md` — the controlled
  -vocabulary discipline every Tandem vocabulary copies.
