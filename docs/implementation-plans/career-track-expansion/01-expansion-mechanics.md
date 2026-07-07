# 01 · Expansion Mechanics — What "Adding a Career" Actually Requires

This doc is the repeatable checklist. Every career profile in `careers/`
assumes this mechanism; none of them re-explains it. Grounded in the
contracts as they exist today: `contracts/career_track.py`,
`contracts/skill_taxonomy.py`, `skill_taxonomy/normalize.py`,
`docs/specs/skill-taxonomy.schema.md`, and the grounding-RAG plan
(`../loop-grounding-rag/01-corpus-and-contracts.md`).

## The three requirements (recap)

A career exists in the product only when all three hold:

1. **Enum membership.** The career is a member of the closed `CareerTrack`
   enum (`contracts/career_track.py`). Amended only in review; never
   LLM-extended. The enum is the literal join key between the skill
   taxonomy and the corpus — both sides tag with it.
2. **Curated taxonomy entries.** The taxonomy has hand-curated `SkillEntry`
   rows tagged with the new track, landed as a **new taxonomy file
   version**. Enrichment (RI-F) only annotates existing entries with corpus
   evidence; it never creates, renames, or deletes them (axiom 08
   "Controlled vocabularies").
3. **Track-tagged corpus documents.** The corpus contains documents
   track-tagged for the career, ingested from a hand-curated manifest.
   Without them, every entry enriches to zero support — which is a flag for
   human review, not an error, but it means the evidence loop is inert for
   that track.

## Step-by-step checklist per career

Order matters: spec → contract → data → resolution → corpus → enrichment.

### A · Amend `CareerTrack` (spec-first)

1. Update `docs/specs/skill-taxonomy.schema.md` — it is the canonical spec
   for the enum. Cross-check `docs/specs/corpus-document.schema.md` (it
   requires `track_tags` "from the shared closed track enum"; if it lists
   the members, update it too).
2. Add the member to `contracts/career_track.py`. Values are lowercase
   snake_case (`swe`, `mle`, `ai_engineer` set the style).
3. `make schemas` if generated JSON schemas embed the enum values.
4. Update fixtures per the house pattern (an invalid fixture using a
   not-yet-added track value is a useful regression tripwire).

### B · Seed taxonomy entries (new file version)

1. Create `backend/taxonomy/skill_taxonomy_v{N+1}.json`. Versioning is
   **append-only**: never edit an existing version in place. Everything
   that consumed v{N} keeps meaning what it meant.
2. For each skill in the career's seed list (see the career profile doc):
   - **If an entry already exists** (check aliases, not just ids — aliases
     are globally unique across the whole taxonomy), add the new track to
     its `track_tags`. Cross-career skills are one shared entry with many
     tags, e.g. `skill.sql` spans `swe`/`mle`/`ai_engineer` today and every
     data career will join it. The career profiles mark these rows
     `EXISTING`.
   - **If it is new**, add a `SkillEntry`: `skill_id` matching
     `^skill\.[a-z0-9-]+$`, `display_name` ≤ 60 chars, non-empty lowercase
     aliases, the new track tag, one of the five kinds
     (`language | framework | tool | concept | practice`).
3. Keep the per-track entry count at **~100 or fewer**. The résumé-intake
   prompt embeds the resolved track's `display_name`s as the allowed
   weak-spot vocabulary; the RI docs bound that slice at "≤ ~100 short
   strings, cheap on Haiku". A 150-entry track silently breaks that budget.
4. Re-pin consumers: extraction responses and eval recordings stamp
   `taxonomy_version`, so a version bump means the RI-E eval set is
   re-recorded/re-pinned against the new version (same discipline as
   corpus snapshots and prompt versions).
5. The review of this JSON **is** the curation gate. LLM assistance may
   draft rows (as these docs do), but a human approves every entry in the
   commit.

### C · Role → track resolution

Add a marker tuple for the career to `_TRACK_MARKERS` in
`skill_taxonomy/normalize.py`. Precedence is fixed and deliberate —
specific marker sets are checked before general ones ("ml engineer" must
not fall through to `swe`). Two rules when inserting:

- Place the new tuple **before** any track whose markers could partially
  match the new career's titles (e.g. "data engineer" must resolve before
  anything keyed on bare "engineer"-adjacent words; "analytics engineer"
  needs a deliberate home before both data tracks claim it).
- Markers match with non-alphanumeric boundaries against the normalized
  role string; keep them lowercase multi-word phrases as users actually
  type them ("data analyst", "business intelligence", "sre", "site
  reliability").

Unresolvable roles still return `None` → weak-spot choice set becomes the
union of all tracks; that fallback gets more diluted with every added
track, which is another reason markers should be generous per career.

### D · Corpus manifest + ingestion (networked → gated)

1. Add a per-track section to the hand-curated source manifest consumed by
   `tools/ingest_corpus.py`: URL, expected `source_type`, `track_tags`
   (the new enum member), `license_note`. Curation lives in the manifest,
   in review — no crawling; the tool fetches exactly the manifest's URLs.
2. Target **30–60 documents per track** (the calibration the RAG plan used
   for the first three tracks: enough for real retrieval metrics, small
   enough to eyeball). The career profiles each seed 10–15 candidate
   sources; grow toward 30+ with job postings and interview reports.
3. Mind `source_type` mix. The classifier
   (`source_claims/classification.py`) assigns types by domain/URL rules;
   axiom 08 scores confidence and expiry per type. Job postings decay
   fastest (45-day prior) — a track whose corpus is mostly postings goes
   stale in weeks. Anchor each track on stable `role_taxonomy`-class
   documents (official cert syllabi, framework pages, canonical role
   guides) and layer volatile postings on top.
4. Live fetch is an **ask-first** operation, per the RAG plan. Ingestion
   ends in a new immutable corpus snapshot.

### E · Enrichment run (RI-F, offline)

With taxonomy vN+1 and a snapshot containing the new track's documents:

1. Run `tools/enrich_taxonomy.py` against the pinned snapshot (`--dry-run`
   first, house convention). It counts **alias occurrences per track** via
   the FTS5 index and writes `corpus_evidence` (`snapshot_id`,
   `occurrence_count`, `supporting_doc_ids`) into a **new** taxonomy file
   version.
2. Read the report. Zero-support entries are flagged for human review —
   possible meanings: the skill is genuinely niche (fine, keep), the corpus
   is missing an obvious document class (fix the manifest), or the aliases
   don't match how the corpus actually spells the skill (fix aliases in the
   next version). The report is the deliverable; the human edit is the
   action. Evidence never deletes an entry, and high counts never add one.

### F · Evals, UI, docs

- RI-E eval set: add per-track cases, including out-of-vocabulary traps
  ("Flurbo.js expert") and a résumé that should resolve to the new track.
  The fixture twin scans against taxonomy aliases, so it picks up the new
  vocabulary automatically — one vocabulary, zero drift.
- Onboarding copy / target-role examples: surface the new career where
  roles are suggested.
- Cross-reference: the RAG plan already reserves "remaining tracks land in
  G-I after the pipeline is proven" — a career landed via this checklist
  **is** a G-I increment.

## Alias design for FTS5 enrichment (read before drafting entries)

Aliases do double duty: they resolve résumé surfaces deterministically
(RI-C) **and** they are the search terms enrichment counts in the corpus
(RI-F). Design them for both:

- **Store the exact post-normalization form.** The normalizer lowercases,
  collapses whitespace, and strips only narrow sentence punctuation — it
  deliberately does **not** strip `+ # & / -` or a leading dot. So
  `"c++"`, `"c#"`, `".net"`, `"ci/cd"`, `"big-o"` are legal aliases; an
  alias ending in a period is not (the seed property test enforces
  idempotence).
- **Global uniqueness is a hard wall.** One alias resolves to exactly one
  entry, taxonomy-wide. When two careers use the same word for different
  things, the bare word can only live on one entry — give each meaning a
  distinguishing multi-word alias instead (e.g. `"data pipelines"` vs a
  hypothetical `"ci/cd pipelines"`), and let the bare word go to the
  dominant meaning or to neither. Every career profile ends with an
  **alias-collision check** against the v1 alias table for exactly this.
- **Short common-word aliases inflate counts.** `"go"`, `"r"`, `"c"`,
  `"swift"`, `"spark"`, `"rest"`, `"agile"` all collide with ordinary
  English (or other product names) in corpus prose. That is acceptable for
  résumé resolution (surfaces arrive as skill mentions, not prose) but
  makes raw FTS5 occurrence counts optimistic. Treat `occurrence_count` as
  an advisory prior, not a ranking; where a skill has both an ambiguous
  short alias and a distinctive long one, the long one's count is the
  trustworthy signal. Worth carrying into the RI-F report design: per-alias
  counts, not just per-entry totals, cost nothing and disambiguate this.
- **Add the spellings job postings actually use.** Enrichment counts what
  the corpus says, and the corpus is largely postings, syllabi, and guides.
  "power bi" vs "powerbi", "scikit-learn" vs "sklearn", "kubernetes" vs
  "k8s" — missing the corpus's dominant spelling undercounts a skill you
  actually care about. The research-grounded alias lists in `careers/`
  come from posting language for this reason.

## Track granularity policy

A recurring judgment call: new track vs specialization of an existing one.
The rule these docs apply:

> A career gets its **own track** when its prep process differs materially —
> different interview-loop stages, different anchor resources or
> certifications, a mostly-disjoint core skill list. It stays a
> **specialization** when its prep is largely a subset of an existing
> track's.

Consequences as of v1: frontend, backend, and full-stack remain inside
`swe` (the `_TRACK_MARKERS` table already resolves all three there, and
their loops are the same DS&A + system-design shape). Mobile is the
marginal case — see `careers/` for the recommendation. DevOps vs cloud
engineer vs SRE is the other classic merge candidate; the profile doc takes
a position based on how postings actually title the roles.

Getting this wrong in the "too many tracks" direction is the expensive
mistake: every track needs its own ~30–100 curated entries, 30–60 corpus
documents, resolver markers, and eval cases — and thin tracks dilute the
union fallback for unresolved roles. When in doubt, merge and revisit after
enrichment data exists.

## Standing constraints (apply to every step)

- The taxonomy and the corpus never contain user data — no résumé text, no
  calendar anything (axiom 06/08).
- LLMs never write vocabulary entries, assign track tags, or score
  confidence. These docs were research-drafted but land through human
  review; the review is the mechanism.
- Networked steps (corpus fetch) are ask-first, operator-run, dry-run
  capable. Enrichment itself is offline against a pinned snapshot.
- All thresholds implied here (per-track sizes, doc counts) are heuristic
  priors until calibrated — same status as validation/drift thresholds.
