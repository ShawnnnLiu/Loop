# SPLITS: hybrid-retrieval-ship

Sized 2026-09-10 at `7408345`.
Three splits: two coding, one operator.
Each is one fresh Claude Code session ending in exactly one commit on branch `hybrid-retrieval-ship` (split 1 creates it from `main`; splits 2 and 3 continue it).
Budget notes assume the fixed session overhead of `CLAUDE.md`, `AGENTS.md`, this plan folder, and the named files read before the first edit.

Splits are strictly ordered.
Split 1 is deliberately offline so all code lands and is tested before any money is spent.
Split 3 cannot measure anything until split 2 populates the vector cache.

## Split 1: the flag (~150k, comfortable)

Reads: this folder (00, 01, SPLITS); `backend/src/agentic_calendar/tools/refresh_claims.py`; `backend/tests/tools/test_refresh_claims.py`; `backend/src/agentic_calendar/tools/embed_corpus.py`; `backend/tests/tools/test_embed_corpus.py`; `backend/tests/retrieval/test_fusion.py`; `backend/src/agentic_calendar/retrieval/fusion.py`; `backend/src/agentic_calendar/retrieval/eval.py:46-54` (the `ChunkSearcher` protocol).

Writes: `refresh_claims.py` (signature, wiring, two args, error handling, report line, docstring); `embed_corpus.py` (`--claim-queries`); both test modules.

Fallback boundary: the `refresh_claims.py` work alone is a green, honest commit if the session runs long.
`embed_corpus.py --claim-queries` can then move to the front of split 2, which has generous slack.
If you take the fallback, say so explicitly in the commit message and in the ledger.

Kickoff prompt:

> Read docs/implementation-plans/hybrid-retrieval-ship/ (00-overview.md, 01-claim-assembly-flag.md, SPLITS.md), then backend/src/agentic_calendar/tools/refresh_claims.py, backend/tests/tools/test_refresh_claims.py, backend/src/agentic_calendar/tools/embed_corpus.py, backend/tests/tools/test_embed_corpus.py, and backend/tests/retrieval/test_fusion.py.
> Create branch hybrid-retrieval-ship from main.
> Implement split 1 exactly as specified in 01-claim-assembly-flag.md: the required keyword-only `searcher: ChunkSearcher` parameter on `assemble_claims`, `--mode {bm25,hybrid}` and `--embedding-model` on the refresh_claims CLI with typed-error handling and a retriever report line, `--claim-queries` on the embed CLI, and the five new refresh_claims tests plus the two new embed_corpus tests.
> Hard constraints: no network calls, seed fake vectors in tests; do not modify corpus/corpus.db; do not touch contracts/, docs/specs/, schemas/, the retrieval/ package, or the Makefile; `searcher` gets no default value; bm25 stays the default in every path.
> Gates before the single commit: make test-fast, make lint, make typecheck, make boundaries, plus `git status` confirming corpus.db is unmodified.
> Fill ledger rows 1 and 2 in 00-overview.md as part of the same commit.
> Ask before anything networked; commit only when the user confirms.

## Split 2: the embed run (~60k, operator split)

Requires explicit user approval in-session: network access, `VOYAGE_API_KEY`, and real spend of approximately $0.045.

Reads: this folder (00, 02); `backend/src/agentic_calendar/tools/embed_corpus.py` docstring and arg surface.

Writes: `backend/corpus/corpus.db` (approximately 2076 new vectors, roughly 8.5 MB of blob); ledger rows 3-5.

Fallback boundary: none needed. If the live run is interrupted, re-running resumes from the cache.

Kickoff prompt:

> Read docs/implementation-plans/hybrid-retrieval-ship/00-overview.md and 02-embed-run.md, then backend/src/agentic_calendar/tools/embed_corpus.py.
> On branch hybrid-retrieval-ship (split 1 present), run the dry-run command from 02-embed-run.md first and compare its counts against the plan's table (expect ~2076 chunks, 0 eval queries, 38 claim queries, ~746k tokens, ~$0.045).
> Report those numbers to me and wait for explicit approval before the live run.
> After the live run, verify with `run_retrieval_eval --mode hybrid` (no --strict) and a `refresh_claims --mode hybrid --dry-run`, both of which must complete without MissingEmbeddingsError.
> Hard constraints: dry-run first, always; do not raise --max-tokens; do not embed any snapshot other than snap_0217291f46e331b9; do not edit source code; never run refresh_claims without --dry-run.
> Gates before the single commit: make test-fast and make retrieval-eval (BM25 floors must be unchanged).
> Fill ledger rows 3, 4, and 5 in 00-overview.md with the CLI's measured token count and cost, not the chars/4 prior, as part of the same commit.

## Split 3: measure, gate, write it down (~120k)

Reads: this folder (00, 03); `backend/Makefile:1-25` and `:108-145`; `docs/writeups/grounding-an-llm-planner.md` (the ablation section and the post-publication section); one existing file in `backend/evalsets/reports/` for shape; `project-facts-Loop.md:100-115` and `:200-215`.

Writes: `backend/Makefile` (new `retrieval-eval-hybrid` target, `.PHONY`, `help`, comment block); `backend/evalsets/reports/hybrid_claim_delta_<date>.report.json`; the writeup's post-publication bullet; `project-facts-Loop.md`; `docs/implementation-plans/README.md`; ledger rows 6-8.

Fallback boundary: the measurement plus the Makefile gate (steps 1-2) is a green, honest commit on its own.
The claim-delta report and prose updates (steps 3-4) can become a small fourth session if the session runs long.

Kickoff prompt:

> Read docs/implementation-plans/hybrid-retrieval-ship/00-overview.md and 03-gate-and-writeup.md, then backend/Makefile lines 1-25 and 108-145, docs/writeups/grounding-an-llm-planner.md, and one file from backend/evalsets/reports/ for shape.
> On branch hybrid-retrieval-ship (splits 1 and 2 present), implement split 3 exactly as specified: measure hybrid and BM25 on snap_0217291f46e331b9 with the v2 labels at k=5, add the retrieval-eval-hybrid target with floors set to the measured hybrid values verbatim, measure the BM25-vs-hybrid claim-store delta with two dry-run refresh_claims invocations plus a throwaway overlap script, write the committed report artifact, and update the writeup, project-facts, and the plans README.
> Hard constraints: no network calls; floors are measured values to four decimals, never invented and never carried over from the old 55-doc snapshot; do not tune rrf_k or candidate_depth; do not change the BM25 floors or the existing retrieval-eval target; do not add either target to `check`; never run refresh_claims without --dry-run; do not edit the existing measured tables in the writeup, append a dated post-publication bullet instead.
> If hybrid measures at or below BM25 on this snapshot, ship it as a negative result and write it up honestly rather than tuning to rescue the number.
> Gates before the single commit: make retrieval-eval, make retrieval-eval-hybrid, make check.
> Fill ledger rows 6, 7, and 8 in 00-overview.md as part of the same commit.
> Ask before anything networked; commit only when the user confirms.

## After All Three Splits

Populating the live claim store from hybrid (`refresh_claims --mode hybrid --app-db dogfood.db`, no `--dry-run`) is a deliberate operator action, not part of any split.
Take it only after reading split 3's claim-delta report.
Per D4 the ingest is additive: existing BM25-sourced claims stay, content-identical excerpts collapse to the same id, and the store grows.
