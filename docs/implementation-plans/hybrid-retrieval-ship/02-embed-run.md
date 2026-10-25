# Split 2: The Embed Run

Networked and paid.
This split requires explicit user approval in-session before any command runs, per the ask-first protocol for networked commands.
One commit, and the commit contains a binary database change.

## What This Split Does

Populate the vector cache in `backend/corpus/corpus.db` so that hybrid retrieval over the pinned snapshot `snap_0217291f46e331b9` actually runs.

Until this happens, `--mode hybrid` raises `MissingEmbeddingsError` by design.
That is correct behavior, not a bug, and split 1's tests prove it.

## Measured Scope, 2026-09-10

Verified directly against the committed database at `7408345`.

| Input | Total | Cached | To embed | Estimated tokens |
| --- | --- | --- | --- | --- |
| Chunks in `snap_0217291f46e331b9` | 2798 (2763 unique texts) | 704 | 2076 | ~746,341 |
| Eval queries (`evalsets/retrieval_queries_v2.json`) | 75 | 75 | 0 | 0 |
| Claim queries (`corpus/claim_queries_v4.json`) | 38 | 0 | 38 | ~455 |

Estimated cost at the pinned voyage-3.5 price of $0.06 per 1M tokens: **approximately $0.045**.

The estimate sits under the CLI's default `--max-tokens 1000000` cap, so no cap raise is needed.
Do not raise the cap.
If the dry-run reports an estimate above the cap, stop and report it rather than raising it, because that would mean the snapshot or the chunking drifted from this plan's measurement.

The 704 already-cached vectors are incidental overlap with the older `snap_26c44499e582a96a` corpus, where text survived the snapshot re-pin unchanged.
Cache identity is content-hash keyed, so they are reused correctly and for free.

## Procedure

**Step 1. Dry run first. Always.**

```bash
cd backend
uv run python -m agentic_calendar.tools.embed_corpus \
	--db corpus/corpus.db \
	--snapshot snap_0217291f46e331b9 \
	--queries evalsets/retrieval_queries_v2.json \
	--claim-queries corpus/claim_queries_v4.json \
	--dry-run
```

This makes no network call.
Compare its reported counts against the table above.
Expect roughly 2076 chunks to embed, 0 eval queries, 38 claim queries, and an estimate near 746k tokens.

If the numbers differ materially, stop and report before spending.
A large divergence means the snapshot pin, the chunking params, or the claim query set changed since 2026-09-10, and the plan's floors and cost expectations need re-deriving first.

**Step 2. Get explicit user approval for the live run.**
State the measured estimate and cost from step 1.
Confirm `VOYAGE_API_KEY` is present in the environment.
Do not proceed without an affirmative answer.

**Step 3. Live run.**

Same command without `--dry-run`.

The transport batches at 128 texts per request with deterministic exponential backoff across four retries, which rides out a per-minute rate-limit window.
If the account is rate-limited hard, add `--batch-size 32` and re-run.
Re-running is cheap and safe: cache identity means already-embedded texts are skipped, so an interrupted run resumes where it left off and re-running a completed run embeds nothing.

Record the CLI's reported measured tokens, estimated cost, and latency.
Those are ledger rows 4 and 5, and they are the honest numbers.
The chars/4 figure in this document is a prior, not a measurement.

**Step 4. Verify coverage before committing.**

```bash
cd backend
uv run python -m agentic_calendar.tools.run_retrieval_eval \
	--queries evalsets/retrieval_queries_v2.json \
	--db corpus/corpus.db \
	--snapshot snap_0217291f46e331b9 \
	--k 5 --mode hybrid
```

This must complete without raising `MissingEmbeddingsError`.
Do not add `--strict` here; there are no hybrid floors yet, and setting them is split 3's job.
Note the printed aggregate line but do not wire it anywhere in this split.

Also confirm the claim-query side is covered by a hybrid dry-run of claim assembly:

```bash
uv run python -m agentic_calendar.tools.refresh_claims \
	--queries corpus/claim_queries_v4.json \
	--manifest corpus/manifest_v1.json \
	--corpus-db corpus/corpus.db \
	--snapshot snap_0217291f46e331b9 \
	--mode hybrid --dry-run
```

It must print `retriever: hybrid` and complete without a typed error.
`--dry-run` scores against a throwaway in-memory store and writes nothing.

## The Commit

`corpus/corpus.db` is a committed binary and it will grow.
2076 new vectors at 1024 float32 dimensions is approximately 8.5 MB of blob, plus index overhead.

Check the delta before committing:

```bash
git status --short
ls -la corpus/corpus.db
```

Only `corpus/corpus.db` and `docs/implementation-plans/hybrid-retrieval-ship/00-overview.md` (the ledger rows) should be modified.
If the FTS index tables also changed because a `build` call rewrote them, that is expected and harmless; the index is derived data rebuilt idempotently.

Commit message should state the snapshot id, vector count, measured tokens, and measured cost.

## Hard Constraints

- Dry-run before live run, every time, no exceptions.
- Explicit user approval before the live run.
- Do not raise `--max-tokens` above the default.
- Do not embed a snapshot other than `snap_0217291f46e331b9`.
- Do not touch source code in this split. If split 1's CLI work is missing or broken, stop and fix it in split 1, not here.
- Do not run `refresh_claims` without `--dry-run` in this split. Populating the live claim store is a separate operator decision after split 3's measurements.

## Gates Before The Commit

```bash
make test-fast
make retrieval-eval
```

`make retrieval-eval` must still pass at its existing BM25 floors.
Embedding adds rows to a separate table and must not perturb BM25 ranking at all.
If those floors move, something rebuilt the FTS index differently and that must be understood before committing.

Fill ledger rows 3, 4, and 5 in `00-overview.md` in the same commit.
