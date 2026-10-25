# Split 3: Measure, Gate, Write It Down

Offline and deterministic.
One commit.

This is the split that turns "we built hybrid" into "we measured hybrid on the corpus we actually serve and gated it."

## Step 1: Measure The Hybrid Baseline

```bash
cd backend
uv run python -m agentic_calendar.tools.run_retrieval_eval \
	--queries evalsets/retrieval_queries_v2.json \
	--db corpus/corpus.db \
	--snapshot snap_0217291f46e331b9 \
	--k 5 --mode hybrid
```

Record the aggregate recall@5, MRR, and nDCG@5 to four decimal places.
These become ledger row 6 and the hybrid floors.

Re-confirm the BM25 baseline in the same session so the comparison is same-snapshot, same-labels, same-code:

```bash
uv run python -m agentic_calendar.tools.run_retrieval_eval \
	--queries evalsets/retrieval_queries_v2.json \
	--db corpus/corpus.db \
	--snapshot snap_0217291f46e331b9 \
	--k 5 --mode bm25
```

Expect 0.7644 / 0.7144 / 0.6910.
That is ledger row 7.

**Do not assume the delta.**
The published +0.0811 MRR came from the 55-document snapshot.
The pinned snapshot is 3.4x larger with stale v2 labels, and the writeup already documents that corpus growth both increases ranking competition and creates label-staleness artifacts.
Hybrid could gain more here (more competition means ranking matters more) or less (stale labels cannot credit newly-surfaced documents either way).
Report what the run says.

If hybrid comes out at or below BM25 on this snapshot, that is a publishable negative result and the plan still ships: the gate records it, the writeup records it, and the flag stays opt-in and defaulted off.
Do not tune `rrf_k` or `candidate_depth` to rescue the number.
D8 locks those, and tuning against a 75-case label set with known staleness would be fitting noise.

## Step 2: Add The Hybrid Gate

In `backend/Makefile`, directly below the existing `retrieval-eval` target (verified at lines 129-136 on 2026-09-10), add:

```make
retrieval-eval-hybrid:
	uv run python -m agentic_calendar.tools.run_retrieval_eval --strict \
		--queries evalsets/retrieval_queries_v2.json \
		--db corpus/corpus.db \
		--snapshot snap_0217291f46e331b9 \
		--k 5 --mode hybrid \
		--min-recall <measured> --min-mrr <measured> --min-ndcg <measured>
```

Floors are the measured values from step 1, verbatim, to four decimals.
That is house convention: floors equal measured, seeded as heuristic priors, always passing until labels, corpus, chunking, or ranking change.

Add `retrieval-eval-hybrid` to the `.PHONY` line at `Makefile:1` and to the `help` target's echo block near `Makefile:18`.

Add a comment block above the new target recording: that the hybrid retriever is opt-in and BM25 remains the default and the primary gate; that these floors were measured on `snap_0217291f46e331b9` with v2 labels on the measurement date; the measured BM25-vs-hybrid delta; and that the gate depends on the vector cache committed in split 2, so a `MissingEmbeddingsError` here means the cache and the snapshot pin have diverged.

Do not modify the existing `retrieval-eval` target or its floors (D5).
Do not add either target to `check`.

## Step 3: Measure The Claim-Store Delta

This is the number that justifies the whole plan, because claim assembly is where retrieval quality becomes product value.

Run both retrievers in dry-run against the pinned snapshot and the v4 claim queries:

```bash
uv run python -m agentic_calendar.tools.refresh_claims \
	--queries corpus/claim_queries_v4.json \
	--manifest corpus/manifest_v1.json \
	--corpus-db corpus/corpus.db \
	--snapshot snap_0217291f46e331b9 \
	--dry-run

uv run python -m agentic_calendar.tools.refresh_claims \
	--queries corpus/claim_queries_v4.json \
	--manifest corpus/manifest_v1.json \
	--corpus-db corpus/corpus.db \
	--snapshot snap_0217291f46e331b9 \
	--mode hybrid --dry-run
```

Both write nothing.
Record for each arm: total assembled claims, claims accepted by the ingestor, the skip counters (short, chrome, stale), duplicates folded, corroboration groups, and the confidence-bucket distribution the outcome printer already reports.

Then compute the set overlap of `claim_id` values between the two arms.
Because ids are content-derived, overlap means both retrievers surfaced the same excerpt, and the symmetric difference is exactly what changing the retriever would add to and remove from the evidence pool.
A short throwaway script is fine; do not add a tool for this.

Write the comparison into `backend/evalsets/reports/hybrid_claim_delta_<date>.report.json`, matching the existing naming convention in that folder (`baseline_2026_07_05.report.json`, `grounding_2026_07_06.report.json`, and two others).
Read one of them first and match its internal conventions.
Include the retriever, embedding model, `rrf_k`, `candidate_depth`, snapshot id, claim query set version, and both arms' counts.
This is where retriever provenance lives, since D3 forbids putting it on the contract.

That is ledger row 8.

## Step 4: Update The Prose

**`docs/writeups/grounding-an-llm-planner.md`.**
Add a new dated bullet to the "Post-publication updates" section at the end.
Do not rewrite the existing ablation section; its numbers were correct for the corpus they were measured on, and the writeup's credibility rests on not retroactively editing measurements.

The new bullet states: hybrid re-measured on the 188-document pinned snapshot with the actual numbers; the claim-store delta; that hybrid shipped as an opt-in `--mode hybrid` on claim assembly with its own gate while BM25 remains the default and the primary gate; and the honest caveat that the v2 labels predate the corpus expansion so both arms are lower bounds.

Correct the standing claim in the ablation section that reads "BM25 stays the shipped retriever" by appending a short forward-reference to the post-publication bullet rather than deleting the original sentence.

**`project-facts-Loop.md`.**
Update the hybrid entries around lines 104 and 208 to reflect shipped-behind-a-flag status with the new measured numbers.
Keep the existing `[MEASURED]` and `[DOCUMENTED]` tagging convention.
Note that this file is currently untracked; leave that decision to the user rather than committing it silently.

**`docs/implementation-plans/README.md`.**
Move the `hybrid-retrieval-ship/` row's status to implemented, or to the honest partial state if any split is outstanding.

## Hard Constraints

- No network calls.
- Floors are measured values, verbatim. Never invent, round favorably, or reuse the old snapshot's numbers.
- Do not tune `rrf_k` or `candidate_depth`.
- Do not change BM25 floors or the `retrieval-eval` target.
- Do not run `refresh_claims` live (without `--dry-run`). Populating the real claim store from hybrid is an operator decision after this evidence exists.
- Do not edit the existing measured tables in the writeup.
- A negative or neutral result ships as-is and gets written up as such.

## Gates Before The Commit

```bash
make retrieval-eval
make retrieval-eval-hybrid
make check
```

`make retrieval-eval` must pass unchanged.
`make retrieval-eval-hybrid` must pass at its freshly-seeded floors, which it will by construction; the real check is that it runs at all, meaning the vector cache covers the snapshot.

Fill ledger rows 6, 7, and 8 in `00-overview.md` in the same commit.
