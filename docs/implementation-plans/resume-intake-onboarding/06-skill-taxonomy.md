# 06 · Skill Taxonomy — the Controlled Vocabulary and the RAG Seam

Added 2026-07-06 (user follow-up to the locked decisions): extracted skills
must not be invented on the go — they must resolve against a canonical,
field-specific skill vocabulary, and that vocabulary must connect to the
grounding-RAG corpus (`../completed/loop-grounding-rag`). This doc defines the
mechanism. Its work is folded into RI-A/RI-B/RI-C (build-order table at the
bottom) plus one new gated increment, **RI-F**, that runs after the RAG
pipeline exists.

## The principle

The LLM never touches the vocabulary. Three deterministic walls:

1. **Extraction stays surface-level.** The node emits skill strings as they
   appear in the résumé (groundedness-checked substrings — unchanged from
   `02-node-and-harness.md`). It is never asked to emit canonical names, so
   it cannot hallucinate vocabulary membership.
2. **Canonicalization is deterministic.** A pure normalizer maps surface
   strings onto taxonomy entries via an alias table (lowercase, collapse
   whitespace, light punctuation strip → exact alias lookup). A surface that
   matches nothing is returned as **unmatched** — visibly flagged, never
   silently promoted to a canonical skill. No fuzzy/similarity matching in
   v1 (same restraint as the RAG plan's corroboration decision: thresholds
   are guesswork; the restraint is the behavior).
3. **The vocabulary itself is curated data, versioned in review.** LLMs do
   not add, rename, or remove entries; corpus evidence (RI-F) annotates
   entries but never auto-creates them. Same curation philosophy as the RAG
   corpus manifest: "curation lives in the manifest, in review — not in
   crawler heuristics."

`inferred_weak_spots` gets the stronger constraint: it becomes a **closed
choice**. The prompt includes the track-relevant slice of the taxonomy, and
the post-validator rejects any weak spot that is not a member. This is where
the payoff lands downstream: profile weaknesses drive the Strategist's
coverage rule ("a module addressing every weakness"), so canonical
weaknesses mean modules about canonical skills — which can later be joined
deterministically against corpus claims for the same track.

`known_strengths` stays free-inferred prose (it legitimately includes
non-taxonomy strengths like "shipped production systems"); it is labeled
inferred and carries no downstream routing. Recorded as a deliberate
asymmetry, not an oversight.

## Contract and spec (RI-A additions)

**New spec `docs/specs/skill-taxonomy.schema.md`**, contract module
`contracts/skill_taxonomy.py`:

- `CareerTrack` — the **shared closed track enum** (`swe`, `mle`,
  `ai_engineer` to start), in its own module `contracts/career_track.py`.
  This is the literal connection point to the RAG plan: G-A's
  `corpus-document.schema.md` requires `track_tags` from "a closed track
  enum" — both plans use THIS enum, whichever branch lands first creates it
  (cross-notes added to `../completed/loop-grounding-rag/01-corpus-and-contracts.md`).
- `SkillEntry`: `skill_id` (stable slug, e.g. `skill.system-design`),
  `display_name`, `aliases: list[str]` (non-empty, lowercase-normalized,
  globally unique across the taxonomy — one alias resolves to exactly one
  entry, validator-enforced), `track_tags: list[CareerTrack]` (non-empty),
  `kind` (`language | framework | tool | concept | practice`),
  `corpus_evidence: CorpusEvidence | None` (v1 always `None`; filled only by
  RI-F: `snapshot_id`, `occurrence_count`, `supporting_doc_ids`).
- `SkillTaxonomy`: `taxonomy_version` (e.g. `skill-taxonomy-v1`), `entries`
  (unique `skill_id`s). Frozen, `extra="forbid"`, invalid fixtures with
  structured violations, `make schemas`.

**Storage:** checked-in versioned JSON
`backend/taxonomy/skill_taxonomy_v1.json`, append-only versioning like the
eval sets (a vocabulary change = new file version, referenced explicitly).
Seed: hand-curated per track (~60–100 SWE, ~30–40 each MLE/AI-engineer),
drafted by the implementer, **reviewed by the user in the RI-A commit** —
the review IS the curation gate. Every extraction response and eval
recording stamps the `taxonomy_version` it ran against (same pinning
discipline as corpus snapshots and prompt versions).

**Axiom amendment (extends RI-A's axiom work):**
`docs/axioms/08-rag-source-claims.md` gains a "Controlled vocabularies"
subsection — axiom 08 already owns what counts as evidence and who scores
it; the taxonomy is the same idea for vocabulary: canonical, versioned,
curated in review; LLMs never write entries; normalization is
deterministic; corpus evidence annotates but never auto-creates; user data
(résumé text) never enters the taxonomy or its evidence.

## Kernel package (RI-B additions)

New region package `skill_taxonomy/` (mirrors the `source_claims/` kernel
pattern):

- Registered in `.importlinter`; imports `contracts/` and `common/` only.
  Notably NOT imported by `llm_nodes/` — see division of labor below.
- `registry.py`: loads + validates the checked-in JSON, exposes lookups by
  id/alias/track.
- `normalize.py`: pure functions — `normalize_surface(str) -> str` and
  `resolve(surface, taxonomy) -> SkillEntry | None`. Property test: resolve
  is total, deterministic, and alias-collision-free by construction.
- `resolve_track(target_role: str | None) -> CareerTrack | None`: a small
  deterministic alias map from role strings to tracks ("backend engineer" →
  `swe`, "ML engineer" → `mle`, …); unresolvable roles → `None` → the
  weak-spot choice set becomes the union of all tracks. No LLM, no scoring.

## Division of labor (who runs where)

| Step | Owner | Mechanism |
| --- | --- | --- |
| Extract skill surfaces from résumé | `ResumeIntakeNode` (LLM) | verbatim strings, groundedness post-validated |
| Choose weak spots | `ResumeIntakeNode` (LLM) | closed choice from the track slice included in the prompt; membership post-validated |
| Surface → canonical skill | `skill_taxonomy/` kernel (deterministic) | alias lookup at the **service layer** (RI-C), after the node returns |
| Unmatched surfaces | deterministic | returned flagged; user decides keep/drop; never canonical |
| Vocabulary content | humans, in review | versioned JSON; RI-F annotates with corpus evidence |

Two RI-B prompt/validator deltas this implies (amending
`02-node-and-harness.md`):

- The user prompt gains a labeled block: *"Allowed weak-spot vocabulary
  (choose only from this list)"* — the `display_name`s of the resolved
  track's entries (bounded: ≤ ~100 short strings, cheap on Haiku). System
  rule 2 is amended accordingly, and the post-validator adds: every
  `inferred_weak_spots` item must resolve (via the same normalizer) to a
  taxonomy entry in the allowed set. Skills rules are unchanged.
- The fixture twin drops its own embedded vocabulary and scans the résumé
  against the **taxonomy aliases** instead — one vocabulary, zero drift
  between fixture and validator.

The node itself never imports `skill_taxonomy/` (llm_nodes independence is
preserved); the allowed-vocabulary list and the membership check arrive as
plain data — the list is passed into `run()` on the input contract
(`ResumeIntakeInput` gains `allowed_weak_spots: list[str]`, filled by the
service from the registry), and the post-validate closure is built at the
composition root the same way `post_validate` hooks already are.

## Service layer and API (RI-C additions)

`extract_resume` gains two deterministic steps around the node call:

1. Before: resolve track from `draft_context.target_role`, load the pinned
   taxonomy, fill `allowed_weak_spots`.
2. After: run the normalizer over `proposal.skills`. Response adds, next to
   the verbatim proposal:
   - `skills_canonical: [{skill_id, display_name, surface}]`
   - `skills_unmatched: [surface, …]`
   - `taxonomy_version`
   (weak spots are canonical by construction — validated in the repair
   loop, so a persistent violation surfaces as `REPAIR_LIMIT_EXCEEDED`
   rather than leaking through).

`UserProfile.skills` stays `list[str]` (display strings) — no schema churn:
matched skills are stored under their canonical `display_name`; the user may
still hand-type anything (user sovereignty — the vocabulary constrains the
LLM, not the person). Consumers that later need canonical ids re-normalize
at read time with the same pure kernel (cheap, deterministic, versioned).
Record this in the user-profile spec's prompt-exposure/semantics section.

## RI-F · Corpus-evidence enrichment — GATED on grounding-RAG G-A–G-D

**Status: built** (`tools/enrich_taxonomy.py`; the gate was satisfied when
the grounding-RAG branch merged). Counting semantics are pinned in
`docs/specs/skill-taxonomy.schema.md` § "Enrichment semantics".

Runs only after the RAG plan's registry, chunking, and FTS5 index exist
(and lives on whichever branch is current then; it is this project's only
increment with a cross-plan dependency):

- `tools/enrich_taxonomy.py`, operator-run, offline against a **pinned
  corpus snapshot**: for each taxonomy entry, count alias occurrences per
  track via the FTS5 index; write `corpus_evidence` (snapshot id, counts,
  supporting doc ids) into a NEW taxonomy file version. `--dry-run` prints
  the would-be evidence table (house convention).
- Entries with zero corpus support get **flagged in the tool's report for
  human curation review** — evidence never deletes an entry, and high
  counts never add one. The report is the deliverable; the human edit is
  the action.
- Payoff, recorded as explicit future work (NOT in this project's scope):
  with skills and weaknesses canonical and claims track-tagged, a
  deterministic demand-vs-supply join (corpus-prominent skills for the
  target track minus the user's canonical skills) can replace pure-LLM
  weak-spot inference entirely — weak spots become *computed candidates the
  LLM merely phrases*. That is the "Axiom" direction both plans point at;
  one sentence in the writeup, nothing more now.

## Build order (folded increments)

| Work | Lands in |
| --- | --- |
| `CareerTrack` + `SkillEntry`/`SkillTaxonomy` spec, contract, fixtures, schemas; seed `skill_taxonomy_v1.json` (user-reviewed); axiom 08 subsection | RI-A |
| `skill_taxonomy/` kernel (+ `.importlinter`), prompt allowed-list block, weak-spot membership post-validate, fixture twin re-based on taxonomy aliases, `ResumeIntakeInput.allowed_weak_spots` | RI-B |
| Track resolution + normalization in `extract_resume`, response `skills_canonical`/`skills_unmatched`/`taxonomy_version` | RI-C |
| Unrecognized-skill UI treatment | RI-D |
| Vocabulary eval cases (out-of-vocab traps) | RI-E |
| Corpus-evidence enrichment tool | **RI-F** (gated on RAG G-A–G-D; ask before any networked step, though enrichment itself is offline) |

## Tests

- Registry: alias uniqueness enforced; version pinning; invalid taxonomy
  fixtures (duplicate alias across entries, empty tracks).
- Normalizer: property tests (deterministic, casing/punctuation variants of
  every alias resolve; near-misses do NOT resolve — the restraint test).
- Node: weak spot outside the allowed list → repair → exhaustion →
  `REPAIR_LIMIT_EXCEEDED` (never leaks through).
- Service: fake-skill résumé ("Flurbo.js expert") → surface extracted,
  grounded, returned in `skills_unmatched`, absent from
  `skills_canonical`.
- Enrichment (RI-F): pure-function counts over a fixture snapshot;
  `--dry-run` writes nothing; zero-support entries appear in the report.
