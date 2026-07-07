# Grounding an LLM Planner: What Retrieval Actually Bought Us

*Loop's study-plan generator (the Strategist) proposes career-prep syllabi.
This writeup measures what happened when we started feeding it real,
attributable evidence — and what it produced before that: confident plans
citing nothing. The deliverable of this project was never a chat UI over a
vector database; it was this evaluation.*

*All numbers below are traceable to committed artifacts — a pinned corpus
snapshot, checked-in labeled query sets, committed eval recordings and
reports, and gate floors in the repo's Makefile. The [appendix](#appendix-a--every-number-to-its-artifact)
maps each one to its file.*

## The odd starting point: the plumbing existed, the water didn't

Loop already had a full evidence contract before this project: a
`source_claim` schema (provenance, deterministic confidence scoring,
expiry), prompt injection with a citation rule, and a syllabus validator
that rejects references to unknown or expired claims. Every piece was
built and tested — and inert. **Nothing populated the claim store**, so
every production plan ran with `source_claims: []`.

That made the eval design unusually honest: the "ungrounded" baseline is
not a strawman we built to lose. It is byte-for-byte the shipped product
before this project.

The project therefore became: build the corpus and retrieval pipeline that
feeds the existing path, and measure the effect end to end.

## The system, briefly

1. **Corpus**: a hand-curated manifest of public-web sources across six
   career tracks (SWE, MLE, AI engineer, quant dev, data scientist,
   product manager). Every document carries a license note, provenance
   dates, and track tags; the registry is immutable and snapshot-versioned
   so every eval pins the exact bytes it ran against.
2. **Retrieval**: deterministic structure-aware chunking → SQLite FTS5
   BM25. That is the shipped v1 retriever. Dense embeddings (Voyage
   `voyage-3.5`) fused via reciprocal-rank fusion exist as a measured
   ablation, not the foundation.
3. **Claim assembly**: retrieved chunks become bounded **verbatim
   excerpts** with provenance — no LLM anywhere in the evidence path.
   (Distilling claims with a model would add a fifth LLM node class, which
   the architecture axioms forbid without an explicit amendment; parked.)
   Scoring stays in the one sanctioned ingestor: deterministic source-type
   classification, heuristic-prior confidence, computed expiry.
4. **Serving**: a deterministic curation filter (expiry, confidence floor,
   per-company cap) picks which stored claims reach the Strategist prompt;
   the validator rejects any cited claim id it cannot resolve.

## Headline: before / after on generation

Three grounded/ungrounded twin cases (SWE, MLE, AI-engineer personas;
identical inputs except `source_claims`), live capture 2026-07-06,
strategist `claude-opus-4-8`, 12 calls, ~$0.27. Graded deterministically
from the committed recording.

| Metric (Tier-1, deterministic) | Ungrounded (production baseline) | Grounded |
| --- | --- | --- |
| Schema validity (first attempt) | 6/6 | 6/6 |
| Modules citing ≥1 evidence claim (citation coverage) | 0.0000 (nothing to cite) | **0.6444** |
| Supplied claims actually used (claim utilization) | — | 0.8667 |
| Citations at high/medium confidence | — | 1.0000 |
| Fabricated (unknown) citation ids | 0 | **0** |

Grounding cost nothing on validity and produced plans where ~64% of syllabus modules carry checkable citations,
up from a structural zero. The model used 87% of the evidence it was
given — it is not ignoring the claims, and it did not invent a single
citation id in either arm. An advisory LLM-judged "groundedness" rubric
also ran (grounded arm scored 4/5/3 of 5) but is deliberately **not** a
headline: with an empty claim list the rubric is trivially satisfiable, so
the ungrounded twins' perfect scores are uninformative; only the Tier-1
deterministic rates above are gate-worthy, and `make eval-gate` now floors
citation coverage at the measured 0.6444.

## Retrieval quality on a labeled set

Doc-level relevance labels, judged against the fetched content of the
pinned snapshot (evidence recorded per case in the query file's notes).
BM25, k=5.

| Query set | Corpus | recall@5 | MRR | nDCG@5 |
| --- | --- | --- | --- | --- |
| v1 (57 cases, 3 tracks) | 3-track snapshot (35 docs) | 0.9181 | 0.8523 | 0.8380 |
| v1 (same 57 cases) | 6-track snapshot (55 docs) | 0.9006 | 0.8289 | 0.8174 |
| v2 (75 cases, 6 tracks) | 6-track snapshot (55 docs) | **0.8978** | **0.8500** | **0.8327** |

The middle row is a deliberate finding: growing the corpus makes the same
queries slightly *harder* (more ranking competition), and v1 labels were
not retro-extended to newly added documents, so a new document that
genuinely answers an old query scores as a miss. Measured metrics are a
lower bound by construction. The CI gate (`make retrieval-eval`) pins the
v2 floors at the measured values.

## Ablation: what mattered and what didn't

**BM25 → hybrid (BM25 + dense cosine, reciprocal-rank fusion).** Measured
on the 3-track corpus (57 queries): the win is almost entirely *ranking*,
not recall.

| Metric | BM25 | Hybrid RRF | Delta |
| --- | --- | --- | --- |
| recall@5 | 0.9181 | 0.9327 | +0.0146 |
| MRR | 0.8523 | 0.9532 | +0.1009 |
| nDCG@5 | 0.8380 | 0.9216 | +0.0836 |

Re-measured on the expanded 6-track corpus (75 queries):

| Metric | BM25 | Hybrid RRF | Delta |
| --- | --- | --- | --- |
| recall@5 | 0.8978 | 0.9222 | +0.0244 |
| MRR | 0.8500 | 0.9311 | +0.0811 |
| nDCG@5 | 0.8327 | 0.9009 | +0.0682 |

A concrete example of what dense retrieval buys: the labeled query
"engineering culture at quantitative trading firms" names a page that
describes exactly that ("built by coders, led by coders … mathematicians,
computer scientists, statisticians") without containing the word
*culture* — a lexical gap BM25 cannot cross. BM25 misses that page
entirely (the one recall miss among the 18 new cases); hybrid retrieves
it at rank 2.

**BM25 stays the shipped retriever.** Hybrid's MRR gain is real but the
shipped serving path reads the assembled claim store, not live retrieval
ranks; embedding costs (~$0.01 per full corpus refresh) are trivial, but
the operational cost of a second provider in the serving path is not. The
ablation exists so that decision is a measured one.

**Reranker: not built (negative result by decision).** With hybrid already
lifting MRR to ~0.95 on the 3-track corpus, the remaining headroom at this
corpus size (tens of documents, hundreds of chunks) could not justify a
new model dependency plus per-query latency to re-score ten candidates.
Recorded as a conclusion, not a failure: reranking earns its keep on
corpora large enough that the candidate list is noisy — revisit if the
corpus grows an order of magnitude.

**Chunking and k** were fixed (structure-aware chunks targeting 1600
chars; k=5) and not swept: parameters are part of the snapshot identity,
so each sweep point is a full re-chunk + re-label pass. That is honest
scope, not an oversight — the labeled set makes the sweep possible later.

## Freshness: does the system know its evidence is aging?

Expiry stamps, an inclusive expired boundary, and a stale-penalty ramp
existed per-claim; what was missing was the *report*. `tools/corpus_stats.py`
now shows expired/stale-window shares per source type and track, document
age distributions, and snapshot ages; a track is flagged **decaying** when
more than 50% of its claims are expired-or-stale (a heuristic prior, like
every threshold in this system). The refresh loop stays deliberately
manual: an operator reads the stats and re-runs two idempotent, gated
CLIs. No cron.

Two findings the stats view surfaced on day zero:

- **Some evidence is born stale.** Unclassified sources carry a 30-day
  expiry prior, and the stale-penalty window is also 30 days — so every
  claim from an unclassified source enters the stale window at ingestion.
  All 39 unclassified claims in the store are in it right now. That is the
  priors working as designed (weak provenance ages fastest), but it means
  unclassified sources are audit-trail material, never durable evidence.
- **The decay flag fired immediately for one track.** `quant_dev` claims
  lean on an unclassified article index, putting 53% of the track's claims
  in the stale window on the day they were created. The flag's actionable
  reading is "this track needs better-classified sources", not merely
  "re-run the refresh".

## Findings, warts, and open questions

Everything below is disclosed in-repo alongside the code; none of it is
hidden in this writeup.

- **Confidence scores are uncalibrated heuristic priors.** Base scores,
  bonuses, penalties, expiry windows, gate floors, the decay threshold —
  all chosen to be plausible, none fit to data. Calibration is specified
  (manual labeling at ≥200 production claims) and has not run. No
  "calibrated confidence" claim is made anywhere, including here.
- **Only medium-bucket claims currently serve.** The curation floor (0.30)
  was set below the personal-anecdote base score (0.35), but the scorer's
  flat anecdotal penalty lands anecdotes at ≤0.25 and unclassified at
  ~0.10 — so in practice only claims from engineering blogs, role
  taxonomies, and interview guides (30 of 117 stored claims) ever reach a
  prompt. A pre-existing tuning-knob tension, deliberately left unretuned
  during this project rather than quietly adjusted to make the numbers
  look richer.
- **Index-page chrome produces junk claims.** Several sources are blog
  index pages whose retrievable text is navigation and teasers; some
  assembled claims are nav text. Mitigated in the expansion by adding
  specific article URLs (the full-article fetches are the best documents
  in the corpus) and disclosed in the manifest comments; index pages were
  kept because committed retrieval labels reference them and the registry
  is append-only.
- **Fetch quality varies and is recorded, not hidden.** One page fetched
  as 0 bytes (JS-rendered), one returned HTTP 429, several big sites serve
  slightly different bytes per request (caught as immutability conflicts,
  old bytes retained). Query-set cases that lost their evidence were
  dropped with the reason recorded in the file.
- **Corpus text is deliberately not committed.** Every manifest entry's
  license note promises bounded excerpts, so full page text stays out of
  the public repo; `make retrieval-eval` is a local gate (rebuildable from
  the manifest by re-fetching), while recording-based generation gates run
  anywhere.
- **Corroboration is exact-duplicate only.** Near-duplicate excerpts do
  not link (tested as a restraint, not a gap): a fuzzy similarity
  threshold would be an unvalidated prior that the deterministic scorer
  then amplifies. On the real corpus this currently yields zero
  corroboration groups — honest, if unimpressive.
- **The grounded/ungrounded comparison is an intra-report arm split.**
  Twins live in one eval set and one recording; the harness's `--compare`
  mode is for future prompt/model changes and now carries the grounding
  metrics.
- **New tracks are retrieval-covered, not generation-evaled.** The three
  expansion tracks have labeled retrieval queries and populated claims,
  but the grounded-generation eval set's personas still cover the original
  three tracks (a fresh capture was declined as not required by the plan;
  the harness takes new twins whenever one is worth its API cost).

## Where this goes

One paragraph of vision, as budgeted: the long-term shape is a counselor
that can answer "what should I do these next three months, and why?" with
every *why* carrying a citation a human can check. This project built the
part of that vision that has to be true first — evidence with provenance,
deterministic scoring, expiry, and an eval that notices when the model
stops citing.

## Appendix A — every number to its artifact

| Number | Artifact |
| --- | --- |
| Grounded/ungrounded Tier-1 rates (0.6444 / 0.8667 / 1.0 / 0 fabricated; 6/6 validity) | `backend/evalsets/recordings/grounding_2026_07_06.json` + `backend/evalsets/reports/grounding_2026_07_06.report.json`, graded by `run_llm_eval` against `backend/evalsets/eval_set_v3.json` |
| Citation-coverage gate floor 0.6444 | `backend/Makefile` `eval-gate` target (`--min-citation-coverage`) |
| v1 retrieval metrics (0.9181 / 0.8523 / 0.8380) | `backend/evalsets/retrieval_queries_v1.json` vs snapshot `snap_b0ce947cafdafc8b` (G-D commit) |
| v1-on-expanded-corpus (0.9006 / 0.8289 / 0.8174) | same query file vs snapshot `snap_26c44499e582a96a` (G-I commit message) |
| v2 retrieval metrics + floors (0.8978 / 0.8500 / 0.8327) | `backend/evalsets/retrieval_queries_v2.json` vs `snap_26c44499e582a96a`; floors in `backend/Makefile` `retrieval-eval` |
| Hybrid ablation, 3-track | G-E commit message (measured table; one corpus embed = 197,439 tokens, ~$0.0118) |
| Hybrid ablation, 6-track | G-I commit message (incremental embed of 242 new chunks + 18 queries: 82,616 measured tokens, ~$0.0050) |
| Claim-store composition (117 claims; 30 medium; 39 unclassified all stale-window; quant_dev decay flag) | `tools/corpus_stats.py` against the operator databases; assembly counts in the G-I commit message |
| Labeled-set judging evidence | per-case `notes` fields in both query-set files |
| Capture costs (~$0.27 for the G-H run) | `llm_call_log` aggregates, reported in the G-H commit message |
| Confidence/expiry priors | `backend/src/agentic_calendar/source_claims/priors.py` + axiom `docs/axioms/08-rag-source-claims.md` |

## Appendix B — honesty checklist (applied before publishing)

- [x] No "calibrated confidence" claims — every score, floor, and
  threshold is named as a heuristic prior, and the calibration plan is
  referenced instead of implied.
- [x] Tier-2 groundedness is labeled advisory/LLM-judged everywhere it
  appears, with the reason its twin comparison is uninformative.
- [x] The ungrounded baseline is described as what it is: the shipped
  product before this phase, not a constructed strawman.
- [x] Every number in this page traces to a committed recording, report,
  labeled file, gate floor, or commit message (Appendix A).
- [x] Negative results are stated as findings: the reranker was not
  earned at this corpus size; corpus growth lowered same-query metrics;
  some evidence is born stale; zero corroboration groups exist.
