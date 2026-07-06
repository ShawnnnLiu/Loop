# 04 · Freshness, Remaining Tracks, Writeup (G-I, G-J)

## G-I · Freshness + corpus expansion

**Freshness metric (the draft's "is the corpus decaying, and does the
system know?"):** almost all machinery exists — expiry stamps, the
inclusive `is_expired` boundary, the stale-penalty ramp (axiom 08 priors).
What's missing is the *report*:

- A corpus/claims stats view: share of claims expired or inside the 30-day
  stale-penalty window, per source type and track; corpus doc age
  distribution per track; oldest-snapshot age. Home: extend
  `tools/show_metrics.py` (or a sibling `tools/corpus_stats.py` if that
  file is plan-cycle-specific — decide in-repo, don't force it).
- Threshold ("a track is decaying when >X% of its claims are stale") is a
  heuristic prior — record it as such, same honesty rule as every other
  threshold in the repo.
- The refresh loop is manual and already exists after G-B/G-G:
  re-run `ingest_corpus` (hash-idempotent) + `refresh_claims` when stats
  say so. **No cron, no automation in v1** — an operator reading a stats
  view and running two gated CLIs is exactly the right amount of system.

**Remaining tracks:** expand the manifest from 3 to the target 5–10
(quant dev, data scientist, PM, plus 2–3 more per the draft), each landing
with: manifest entries, labeled queries added to the query set (append-only
version bump), retrieval metrics re-run, and G-H grounded cases for at
least the tracks the eval set's personas actually use. Depth stays ahead of
coverage — a new track without labeled queries doesn't count as shipped.

## G-J · Writeup + eval appendix (the recruiter-facing artifact)

- **The writeup:** "Grounding an LLM planner: what retrieval actually
  bought us" — centered on the before/after table (ungrounded production
  baseline vs. grounded, Tier-1 rates + advisory Tier-2 groundedness),
  with the ablation table (BM25 vs. hybrid; reranker on/off if G-F ran;
  chunk size; k) and the latency/quality tradeoff. One paragraph of product
  vision (the counselor, "where this goes next") — one, per the scope guard.
  Negative results go in, labeled as findings, not buried: "reranking
  didn't earn its latency at this corpus size" is a conclusion, not a
  failure.
- Home: `docs/` in-repo (linkable from the how-its-built page of the
  recruiter-readiness pass, which has a slot for engineering writeups) or
  the external blog — user's call at the time; the repo copy is the
  durable one.
- **Eval appendix:** the labeled query set (it's already committed —
  link it), per-ablation metric tables, the floors chosen and why they're
  heuristic priors, and per-run costs from the call log
  (`call_aggregates`, same reporting convention as the UX pass captures).
- **Honesty checklist before publishing** (axiom 08's public-facing rule
  applied to the writeup):
  - no "calibrated confidence" claims — priors are named as priors;
  - Tier-2 groundedness labeled advisory/LLM-judged everywhere it appears;
  - the ungrounded baseline described as what it is (the shipped product
    before this phase, not a strawman);
  - every number traceable to a committed recording, report, or test run.

## Cost accounting (axiom 09 touch)

- If G-E shipped: replace the dormant "~$0.02/1M, not yet exercised"
  embedding line with the real provider's price + measured per-refresh
  cost; onboarding table's "RAG retrieval (8 queries)" line gets real
  numbers. Table regeneration rules in axiom 09 apply (change log entry).
- If G-E didn't ship: annotate the embedding line "still not exercised —
  BM25-only grounding shipped" so the axiom stays honest.
- Ingestion/refresh costs are near-zero (fetches + SQLite); the real spend
  is G-H captures — each was user-approved with a cap at run time; the
  writeup reports the total.

## Definition of done (from the draft, restated as the exit gate)

One page a recruiter can read showing (a) retrieval metrics on a labeled
set, (b) a measured change in unsupported-claim/citation-coverage rates in
generated plans, (c) an honest ablation of which components mattered.
All three exist as committed, reproducible artifacts (pinned snapshot +
committed recordings + reports) — anything less stays on the branch.
