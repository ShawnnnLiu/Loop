"""Grade the labeled retrieval query set against a pinned corpus snapshot.

Usage::

    uv run python -m agentic_calendar.tools.run_retrieval_eval \\
        --queries evalsets/retrieval_queries_v2.json \\
        --db corpus/corpus.db --snapshot snap_xxxxxxxxxxxxxxxx [--k 5] \\
        [--mode bm25|hybrid] \\
        [--strict --min-recall 0.8 --min-mrr 0.7 --min-ndcg 0.75]

Fully offline and deterministic (amended axiom 22: grading checked-in data
may gate merges): the corpus database, the snapshot pin, and the labels are
all versioned inputs; the FTS index is derived data and is (re)built
idempotently before grading. ``--strict`` requires all three floors and
exits non-zero on any breach — the ``make retrieval-eval`` gate. Floors are
heuristic priors seeded from the first measured run.

``--mode hybrid`` grades the G-E hybrid retriever (BM25 + dense cosine under
reciprocal rank fusion) using **cached vectors only** — still offline; a
missing vector is a typed error pointing at the (ask-first, networked) embed
CLI, never a silent fall-back to BM25. The BM25 mode stays the CI gate;
hybrid runs exist to measure the ablation, two runs over the same labels.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.retrieval import (
    HybridSearcher,
    SqliteChunkIndex,
    SqliteCorpusRegistry,
    SqliteVectorStore,
)
from agentic_calendar.retrieval.eval import (
    ChunkSearcher,
    RetrievalFloors,
    RetrievalReport,
    evaluate_query_set,
    floor_breaches,
    load_query_set,
)


def _print_report(report: RetrievalReport) -> None:
    for case in report.per_case:
        hit = (
            f"first hit @{case.first_relevant_rank}"
            if case.first_relevant_rank is not None
            else "no relevant doc retrieved"
        )
        print(
            f"[{case.query_id}] recall@{report.k}={case.recall_at_k:.4f} "
            f"rr={case.reciprocal_rank:.4f} ndcg@{report.k}={case.ndcg_at_k:.4f} "
            f"({hit}; {case.relevant_count} relevant)"
        )
    print(
        f"aggregate ({report.cases} cases, k={report.k}, "
        f"snapshot {report.snapshot_id}, {report.query_set_version}): "
        f"recall@{report.k}={report.mean_recall_at_k:.4f} "
        f"mrr={report.mean_reciprocal_rank:.4f} "
        f"ndcg@{report.k}={report.mean_ndcg_at_k:.4f}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Grade the labeled retrieval query set against a pinned snapshot "
            "(offline, deterministic; may gate merges per amended axiom 22)."
        )
    )
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument(
        "--snapshot", required=True, help="Pinned snapshot id (snap_ + 16 hex)."
    )
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument(
        "--mode",
        choices=("bm25", "hybrid"),
        default="bm25",
        help="Retriever to grade: bm25 (the CI gate) or hybrid (G-E ablation).",
    )
    parser.add_argument(
        "--embedding-model",
        default="voyage-3.5",
        help="Vector-cache model name for --mode hybrid.",
    )
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--min-recall", type=float, default=None)
    parser.add_argument("--min-mrr", type=float, default=None)
    parser.add_argument("--min-ndcg", type=float, default=None)
    args = parser.parse_args(argv)

    floors: RetrievalFloors | None = None
    floor_values = (args.min_recall, args.min_mrr, args.min_ndcg)
    if args.strict or any(v is not None for v in floor_values):
        if any(v is None for v in floor_values):
            print(
                "error: --min-recall, --min-mrr, and --min-ndcg must all be "
                "given together (required with --strict)",
                file=sys.stderr,
            )
            return 1
        floors = RetrievalFloors(
            min_mean_recall_at_k=args.min_recall,
            min_mean_reciprocal_rank=args.min_mrr,
            min_mean_ndcg_at_k=args.min_ndcg,
        )

    if not args.db.exists():
        print(f"error: corpus database not found: {args.db}", file=sys.stderr)
        return 1

    try:
        query_set = load_query_set(args.queries)
        db = SqliteDatabase(args.db)
        registry = SqliteCorpusRegistry(db)
        snapshot = registry.get_snapshot(args.snapshot)
        if snapshot is None:
            print(
                f"error: snapshot {args.snapshot!r} is not in {args.db}",
                file=sys.stderr,
            )
            return 1
        index = SqliteChunkIndex(db)
        # Derived data: (re)building is offline, idempotent, deterministic.
        index.build(registry, snapshot)
        hybrid: HybridSearcher | None = None
        if args.mode == "hybrid":
            hybrid = HybridSearcher(
                index, SqliteVectorStore(db), model_name=args.embedding_model
            )
        searcher: ChunkSearcher = hybrid if hybrid is not None else index
        report = evaluate_query_set(
            query_set, searcher=searcher, registry=registry, snapshot=snapshot, k=args.k
        )
    except AgenticCalendarError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if hybrid is not None:
        print(
            f"retriever: hybrid (model {args.embedding_model}, "
            f"rrf_k={hybrid.params.rrf_k}, "
            f"candidate_depth={hybrid.params.candidate_depth})"
        )
    else:
        print("retriever: bm25")
    _print_report(report)

    if floors is not None:
        breaches = floor_breaches(report, floors)
        for breach in breaches:
            print(f"FLOOR BREACH: {breach}", file=sys.stderr)
        if breaches and args.strict:
            return 1
        if not breaches:
            print("floors: all metrics at or above their floors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
