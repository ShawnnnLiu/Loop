# 05 · Production Operations — Populating and Maintaining the Claim Store

Status: **operational runbook**, written 2026-07-14 after the retune /
chrome-gate pass. The pipeline shipped in PR #30; as of this doc's writing
the production claim stores had **never been populated** — every real user
ran the ungrounded baseline. This doc is the checklist that changes that,
and the loop that keeps the evidence alive afterwards.

Standing decisions (owner, 2026-07-14):

- **No automated refresh.** The refresh loop is deliberately manual and
  operator-gated — no cron, no scheduled jobs. `corpus_stats` reports;
  a human acts. (Matches the tool's own v1 posture.)
- **`backend/corpus/corpus.db` is committed** (public-web text only,
  axiom 08; reproducibility of the pinned snapshot won over keeping page
  text out of the repo — see the writeup's post-publication updates). The
  corpus ships inside the deploy image, so production population needs no
  network fetch.

## The two databases

| Database | Contents | Where |
| --- | --- | --- |
| `backend/corpus/corpus.db` | document registry, pinned snapshots, FTS tables, cached embeddings | committed; inside the Fly image at `/app/corpus/corpus.db` |
| app database (claim store + everything else) | `source_claims` among the app's stores | local: `backend/dogfood.db`; Fly: `/data/app.db` (`SHARED_DB_PATH`) |

Population = running `refresh_claims` from the pinned snapshot into the app
database. It is **offline** (reads the local corpus, no network), **idempotent**
(claim ids are content-derived; re-runs report `duplicate=`), and **safe to
re-run** (append-only via the sanctioned ingestor).

## First-time population

Always dry-run first (prints real scores, writes nothing):

```bash
# from backend/
uv run python -m agentic_calendar.tools.refresh_claims \
    --queries corpus/claim_queries_v2.json \
    --manifest corpus/manifest_v1.json \
    --corpus-db corpus/corpus.db \
    --snapshot snap_26c44499e582a96a \
    --dry-run
```

Local (dogfood):

```bash
uv run python -m agentic_calendar.tools.refresh_claims \
    --queries corpus/claim_queries_v2.json \
    --manifest corpus/manifest_v1.json \
    --corpus-db corpus/corpus.db \
    --snapshot snap_26c44499e582a96a \
    --app-db dogfood.db
```

Fly (after a deploy that includes the committed corpus):

```bash
fly ssh console -C "uv run python -m agentic_calendar.tools.refresh_claims \
    --queries corpus/claim_queries_v2.json \
    --manifest corpus/manifest_v1.json \
    --corpus-db corpus/corpus.db \
    --snapshot snap_26c44499e582a96a \
    --app-db /data/app.db"
```

Expected result against `snap_26c44499e582a96a` with `claim-queries-v2`
(2026-07-14 run, chrome gate active): **85 claims ingested** (36 nav-chrome
retrieval hits skipped, 12 stale-at-source, 17 duplicates folded), of which
**37 serve** at the default curation floor (~3.8k prompt tokens): 8
`company_engineering_blog`, 5 `interview_postmortem`, 21 `personal_anecdote`
(labeled low), 3 `role_taxonomy`. `unclassified` claims (31) never serve
uncorroborated — by design.

### Verify

1. `uv run python -m agentic_calendar.tools.corpus_stats --corpus-db
   corpus/corpus.db --app-db <app-db>` — claim counts, freshness split,
   per-track view, decay + doc-floor flags.
2. Propose a plan as a real user: syllabus modules should now carry
   `source_claim_ids`; the validator rejects unknown/expired ids, so a
   grounded plan that validates is the end-to-end proof.

### Rollback

The store is one table. Before any batch run, copy the app database
(`cp dogfood.db dogfood.db.bak-<date>`; on Fly, `fly ssh console -C
"cp /data/app.db /data/app.db.bak-<date>"`). Restoring the copy restores
the store; deleting all claims degrades safely to the ungrounded baseline
(the product as it ran before population).

## The maintenance loop (manual by decision)

Run `corpus_stats` when you think of it — the expiry math says roughly
**monthly** is the natural cadence (the shortest-lived servable types are
`interview_postmortem`/`interview_report` at 120d; `unclassified` at 30d
never serves; `official_job_posting` at 45d becomes relevant once
`known_company_domains` is populated). Act on two flags:

- **`DECAYING`** (>50% of a track's claims stale-or-expired): re-run
  `ingest_corpus` (networked → **ask-first**, per the operating contract)
  to collect fresh documents, pin a new snapshot, then `refresh_claims`
  against it. Claim ids for unchanged text are stable; changed pages yield
  new claims and the expired ones fall out of serving on their own.
- **`UNDER MINIMUM` / below-target doc floors** (minimum 10, target 30
  docs/track): extend the manifest for that track before expecting its
  claims to be worth anything. As of 2026-07-14: `data_scientist` (4),
  `product_manager` (6), `quant_dev` (5) are under minimum.

When extending the manifest, three rules earned by this corpus:

1. **Specific article URLs, not index pages.** Index pages produce
   navigation chrome; the assembly gate now skips the worst of it, but the
   best documents in the corpus are all full-article fetches.
2. **Grow the classifier host lists with the manifest.** A host in none of
   `known_company_domains` / `engineering_blog_hosts` /
   `personal_blog_hosts` classifies `unclassified` → 30-day expiry, born
   stale, never serves. The quant_dev decay flag is exactly this failure.
   (`known_company_domains` is still empty — no URL classifies as
   `official_job_posting` today.)
3. **Anchor each track on `role_taxonomy`-class documents** (cert syllabi,
   canonical role guides) and layer volatile sources on top — the
   expansion-mechanics doc's source-mix rule, visible in the priors table.

## Serving-floor retune — the dataset behind axiom 08's change record

Axiom 08 ("Serving curation floor") records the 0.30 → 0.25 default change
of 2026-07-14 and cites this table. Simulations ran the real 117-claim
store (assembled 2026-07-07) through `curate_claims`, re-scored via
`score_confidence` at the ingestion date; store composition: engineering
blog 17 (0.75), role taxonomy 6 (0.70), postmortem 7 (0.65), anecdote 48
(0.25), unclassified 39 (0.10).

| floor | anecdotal penalty | served | notes |
| --- | --- | --- | --- |
| 0.30 | 0.10 (shipped) | 27 (~2.9k tok) | production-equivalent: zero anecdotes serve — the derivation bug |
| 0.25 | 0.10 | 56 (~5.9k tok) | anecdotes serve at post-penalty score; unclassified stay out |
| 0.20 | 0.10 | 56 (~5.9k tok) | same set; weaker unclassified gate (2 corroborators suffice) |
| any | 0.05 | — | **rejected**: maxed anecdote reaches 0.55 = `medium` boundary, breaking axiom 08's anecdotes-stay-`low` ceiling |

Chosen: floor 0.25, penalties unchanged. On the post-chrome-gate rebuild
the served set is 37 of 85 (~3.8k tokens; the chrome gate removed 10
formerly-serving chrome claims and admitted deeper, cleaner chunks).

To pin a **different** floor in one deployment without touching code:
set `TUNING_PATH` to a `tuning.toml` carrying, e.g.:

```toml
justification = "why this deployment moves the floor"
dataset_reference = "what data motivated it"

[claim_curation]
min_confidence = 0.30
```

Every effective override journals to the threshold change log at boot
(axiom 07); the committed `backend/tuning.toml` stays a fully-commented
template. Fly does not set `TUNING_PATH` today — defaults serve.

## Known limitations (inherited, unchanged by this doc)

- Claims carry no career track; serving is track-blind (`claim_store.all()`
  → curation). Every track added grows every user's prompt. Fixing this is
  a spec-first contract change, deliberately not smuggled into ops work.
- Retrieval happens only at refresh time (30 fixed queries); users' actual
  goals never trigger retrieval. Batch-RAG by design, revisit at scale.
- `make retrieval-eval` is green against the committed corpus anywhere,
  but is still not CI-wired — a follow-up decision.
- All thresholds named here are uncalibrated heuristic priors (axiom 07/08
  disclosure); the calibration pass triggers at ≥200 production claims.
