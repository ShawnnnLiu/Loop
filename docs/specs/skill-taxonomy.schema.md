# Skill Taxonomy Schema

## Owner

Human curators, in review. The taxonomy is checked-in versioned JSON under
`backend/taxonomy/` — curated data, never runtime or LLM output (axiom 08
"Controlled Vocabularies").

## Consumers

The deterministic `skill_taxonomy/` kernel (registry + normalizer), the
service layer that fills `ResumeIntakeInput.allowed_weak_spots` and
canonicalizes extracted skills, tests, and (gated increment RI-F) the
corpus-evidence enrichment tool.

## Purpose

Extracted skills are vocabulary, not free invention. The ResumeIntakeNode
emits surface strings only; a deterministic normalizer maps them onto this
canonical, versioned, human-curated taxonomy. Unmatched surfaces are
returned visibly flagged and never become canonical skills.
`inferred_weak_spots` is a closed choice from the track-relevant taxonomy
slice, membership-enforced in the repair loop.

The taxonomy shares the `CareerTrack` enum with the grounding-RAG corpus
(`../implementation-plans/loop-grounding-rag/`): corpus documents are
track-tagged with the same closed enum, so corpus-derived evidence can
later annotate taxonomy entries deterministically.

## JSON Example

```json
{
  "taxonomy_version": "skill-taxonomy-v1",
  "entries": [
    {
      "skill_id": "skill.system-design",
      "display_name": "System design",
      "aliases": ["system design", "systems design", "distributed system design"],
      "track_tags": ["swe", "mle", "ai_engineer"],
      "kind": "concept",
      "corpus_evidence": null
    },
    {
      "skill_id": "skill.python",
      "display_name": "Python",
      "aliases": ["python", "python3"],
      "track_tags": ["swe", "mle", "ai_engineer"],
      "kind": "language",
      "corpus_evidence": null
    }
  ]
}
```

## Field Definitions

### `CareerTrack` (shared closed enum, `contracts/career_track.py`)

| Value | Meaning |
| --- | --- |
| `swe` | Software engineering |
| `mle` | Machine-learning engineering |
| `ai_engineer` | AI engineering (LLM/agent application work) |

Both this taxonomy and the grounding-RAG corpus (`track_tags` in
`corpus-document.schema.md`, once that plan lands) use **this** enum;
whichever branch lands first creates the module.

### `SkillEntry`

| Field | Type | Rules |
| --- | --- | --- |
| `skill_id` | string | required; stable slug, pattern `skill.[a-z0-9-]+` |
| `display_name` | string | required, 1–60 chars; canonical display form |
| `aliases` | `list[str]` | required, non-empty; each already lowercase-normalized (lowercase, single-spaced, trimmed); unique within the entry AND globally unique across the taxonomy |
| `track_tags` | `list[CareerTrack]` | required, non-empty, unique |
| `kind` | enum | `language`, `framework`, `tool`, `concept`, `practice` |
| `corpus_evidence` | `CorpusEvidence` or null | **v1: always `null`**; filled only by the gated RI-F enrichment tool |

### `CorpusEvidence`

| Field | Type | Rules |
| --- | --- | --- |
| `snapshot_id` | string | required, non-empty; the pinned corpus snapshot the counts came from |
| `occurrence_count` | int | required, `>= 0` |
| `supporting_doc_ids` | `list[str]` | default empty; unique |

### `SkillTaxonomy`

| Field | Type | Rules |
| --- | --- | --- |
| `taxonomy_version` | string | required; pattern `skill-taxonomy-v<N>` |
| `entries` | `list[SkillEntry]` | required, non-empty; `skill_id`s unique; alias uniqueness holds globally |

## Normalization Semantics

One alias resolves to exactly one entry — global alias uniqueness is
validator-enforced, so the kernel's `resolve(surface, taxonomy)` is total,
deterministic, and collision-free by construction. Normalization is
lowercase, whitespace-collapse, and a light punctuation strip; **no
fuzzy/similarity matching in v1** (thresholds are guesswork until
calibrated — the restraint is the behavior). A surface that matches
nothing is returned **unmatched**, visibly flagged, never silently
promoted.

## Storage and Versioning

Checked-in versioned JSON: `backend/taxonomy/skill_taxonomy_v1.json`.
Versioning is append-only like the eval sets — a vocabulary change is a
new file version, referenced explicitly. Every extraction response and
eval recording stamps the `taxonomy_version` it ran against (the same
pinning discipline as corpus snapshots and prompt versions).

Curation rules (axiom 08):

- Humans add/rename/remove entries, in review. LLMs never write entries.
- Corpus evidence annotates entries (RI-F, from a pinned snapshot); it
  never auto-creates, auto-deletes, or auto-ranks them.
- User data (résumé text, profile fields) never enters the taxonomy or
  its evidence.

## Invalid Examples

```json
{
  "taxonomy_version": "skill-taxonomy-v1",
  "entries": [
    { "skill_id": "skill.python", "display_name": "Python", "aliases": ["python"], "track_tags": ["swe"], "kind": "language", "corpus_evidence": null },
    { "skill_id": "skill.python-lang", "display_name": "Python (language)", "aliases": ["python"], "track_tags": ["swe"], "kind": "language", "corpus_evidence": null }
  ]
}
```

Reason: alias `python` appears on two entries — aliases must be globally
unique so resolution is unambiguous.

```json
{ "skill_id": "skill.python", "display_name": "Python", "aliases": ["python"], "track_tags": [], "kind": "language", "corpus_evidence": null }
```

Reason: empty `track_tags`.

```json
{ "skill_id": "skill.python", "display_name": "Python", "aliases": ["Python"], "track_tags": ["swe"], "kind": "language", "corpus_evidence": null }
```

Reason: alias not lowercase-normalized.

## Related Docs

- `../axioms/08-rag-source-claims.md` ("Controlled Vocabularies")
- `resume-extraction.schema.md`
- `resume-intake-input.schema.md`
- `../implementation-plans/resume-intake-onboarding/06-skill-taxonomy.md`
