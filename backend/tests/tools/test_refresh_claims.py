"""Tests for the claim-assembly CLI (grounding-RAG G-G). Fully offline.

The load-bearing properties: assembly is deterministic (same snapshot + query
set + params → identical records), excerpts are bounded verbatim text,
corroboration links exact duplicates ONLY (the restraint is the behavior),
scoring belongs to the sanctioned ingestor (pipeline-supplied score fields are
stripped), ``--dry-run`` writes nothing, and a live re-run is idempotent by
claim identity. The golden case proves the populated store actually reaches
the strategist through the D1 curation filter and survives syllabus
validation — the Phase 5 injection seam, finally exercised with real data.
"""

from __future__ import annotations

import copy
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast

from agentic_calendar.app.cycle import CycleService
from agentic_calendar.app.environment import (
    LlmNodeBundle,
    NodeDependencies,
    build_environment,
)
from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import (
    CorpusDocument,
    content_hash_for,
    derive_doc_id,
)
from agentic_calendar.contracts.corpus_snapshot import ChunkingParams
from agentic_calendar.contracts.source_claim import ConfidenceBucket, SourceType
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.llm_nodes.planner import FixturePlanner
from agentic_calendar.llm_nodes.reflection_summary import (
    DeterministicReflectionSummary,
)
from agentic_calendar.llm_nodes.strategist import FixtureStrategist
from agentic_calendar.llm_nodes.user_facing_explanation import (
    DeterministicUserFacingExplanation,
)
from agentic_calendar.retrieval import SqliteChunkIndex, SqliteCorpusRegistry
from agentic_calendar.source_claims.ingestion import (
    ClaimIngestionStatus,
    InMemorySourceClaimStore,
    SourceClaimIngestor,
)
from agentic_calendar.source_claims.sqlite_store import SqliteSourceClaimStore
from agentic_calendar.supervisor.state import SupervisorState as S
from agentic_calendar.tools.ingest_corpus import CorpusManifest
from agentic_calendar.tools.refresh_claims import (
    AssemblyReport,
    ClaimQuerySet,
    assemble_claims,
    build_excerpt,
    derive_claim_id,
    excerpt_key,
    ingest_assembled,
    load_claim_queries,
    main,
)
from tests._fixture_loader import iter_valid

_REPO_QUERIES = Path(__file__).parents[2] / "corpus" / "claim_queries_v1.json"
_REPO_MANIFEST = Path(__file__).parents[2] / "corpus" / "manifest_v1.json"

#: Matches the golden-suite HAPPY_NOW anchor so the end-to-end propose flow
#: reuses the proven fixture geometry (Mon 2026-05-04, deep-work weekday math).
_NOW = datetime(2026, 5, 4, 12, 0, tzinfo=UTC)
_COLLECTED = date(2026, 5, 4)
#: 40 days before collection-day "now": an unclassified claim (30-day expiry
#: prior) anchored here is contract-valid but already expired at ``_NOW``.
_OLD_COLLECTED = date(2026, 3, 25)

_PARAMS = ChunkingParams(algorithm="structure_v1", target_chars=400, overlap_chars=0)

_SHARED_PARAGRAPH = (
    "System design interviews reward structured preparation and clear "
    "capacity estimation under time pressure."
)
_VARIANT_PARAGRAPH = (
    "System design interviews reward structured preparation and careful "
    "capacity estimation under time pressure."
)

#: url -> (text, date_collected, source_published_date)
_DOCS: dict[str, tuple[str, date, date | None]] = {
    "https://engineering.acme.com/guide": (_SHARED_PARAGRAPH, _COLLECTED, None),
    "https://example.org/mirror": (_SHARED_PARAGRAPH, _COLLECTED, None),
    "https://example.org/variant": (_VARIANT_PARAGRAPH, _COLLECTED, None),
    # Personal-blog host published 2019 + 90-day expiry prior → the kernel
    # expiry predates collection → skipped at assembly (stale-at-source).
    "https://blog.old.example/notes": (
        "System design interview folklore from an old personal blog post.",
        _COLLECTED,
        date(2019, 1, 1),
    ),
    # Unclassified + collected 40 days ago → ingestable but expired at _NOW:
    # the D1 curation filter must drop it before the prompt.
    "https://plain.example.com/old-notes": (
        "System design interviews demand repeated practice with realistic "
        "scenarios and honest feedback loops.",
        _OLD_COLLECTED,
        None,
    ),
    # Shorter than the excerpt floor → skipped (nav-chrome guard).
    "https://example.org/stub": ("System design.", _COLLECTED, None),
}

_MANIFEST = CorpusManifest.model_validate(
    {
        "manifest_version": "corpus-manifest-v1",
        "engineering_blog_hosts": ["engineering.acme.com"],
        "personal_blog_hosts": ["blog.old.example"],
        "sources": [
            {
                "url": "https://engineering.acme.com/guide",
                "expected_type": "company_engineering_blog",
                "track_tags": ["swe"],
                "license_note": "Public blog post; excerpts bounded.",
                "title": "Guide",
            }
        ],
    }
)

_QUERY_SET = ClaimQuerySet.model_validate(
    {
        "query_set_version": "test-claim-queries",
        "k": 10,
        "queries": [
            {"track": "swe", "query_text": "system design interviews preparation"},
            {"track": "swe", "query_text": "system design capacity estimation"},
        ],
    }
)


def _build_corpus(tmp_path: Path) -> tuple[Path, str]:
    """Register the fixture docs, pin a snapshot, build the index."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    corpus_db_path = tmp_path / "corpus.db"
    db = SqliteDatabase(corpus_db_path)
    registry = SqliteCorpusRegistry(db)
    doc_ids = []
    for url, (text, collected, published) in _DOCS.items():
        document = CorpusDocument(
            doc_id=derive_doc_id(url, collected),
            source_url=url,
            source_type=_MANIFEST.classify(url),
            license_note="Public page; test fixture.",
            date_collected=collected,
            source_published_date=published,
            track_tags=[CareerTrack.SWE],
            content_hash=content_hash_for(text),
            title=url.rsplit("/", 1)[-1],
        )
        registry.register(document, text=text)
        doc_ids.append(document.doc_id)
    snapshot = registry.create_snapshot(doc_ids, created_at=_NOW, chunking_params=_PARAMS)
    SqliteChunkIndex(db).build(registry, snapshot)
    return corpus_db_path, snapshot.snapshot_id


def _assemble(tmp_path: Path) -> AssemblyReport:
    corpus_db_path, snapshot_id = _build_corpus(tmp_path)
    db = SqliteDatabase(corpus_db_path)
    registry = SqliteCorpusRegistry(db)
    index = SqliteChunkIndex(db)
    report = assemble_claims(
        registry=registry,
        index=index,
        snapshot_id=snapshot_id,
        query_set=_QUERY_SET,
        manifest=_MANIFEST,
    )
    return report


# --------------------------------------------------------------------------- #
# excerpts
# --------------------------------------------------------------------------- #


def test_build_excerpt_keeps_short_text_verbatim_flattened() -> None:
    assert (
        build_excerpt("One line.\nAnother  line here today.", min_chars=10)
        == "One line. Another line here today."
    )


def test_build_excerpt_trims_at_sentence_boundary() -> None:
    text = "First sentence here. Second sentence follows. Third one overflows."
    excerpt = build_excerpt(text, max_chars=50, min_chars=10)
    assert excerpt == "First sentence here. Second sentence follows."


def test_build_excerpt_cuts_a_long_first_sentence_at_a_word_boundary() -> None:
    text = "word " * 40  # one 200-char "sentence", no terminator
    excerpt = build_excerpt(text, max_chars=52, min_chars=10)
    assert excerpt is not None
    flat = " ".join(text.split())
    assert len(excerpt) <= 52
    assert flat.startswith(excerpt)
    assert flat[len(excerpt)] == " "  # never a mid-word cut


def test_build_excerpt_rejects_fragments_below_the_floor() -> None:
    assert build_excerpt("System design.", min_chars=40) is None


# --------------------------------------------------------------------------- #
# assembly
# --------------------------------------------------------------------------- #


def test_assembly_is_deterministic(tmp_path: Path) -> None:
    first = _assemble(tmp_path / "a")
    second = _assemble(tmp_path / "b")
    assert first.claims == second.claims
    assert (first.skipped_short, first.skipped_stale, first.duplicates_folded) == (
        second.skipped_short,
        second.skipped_stale,
        second.duplicates_folded,
    )


def test_assembly_skips_short_and_stale_and_folds_duplicates(tmp_path: Path) -> None:
    report = _assemble(tmp_path)
    urls = {claim.document_url for claim in report.claims}
    assert urls == {
        "https://engineering.acme.com/guide",
        "https://example.org/mirror",
        "https://example.org/variant",
        "https://plain.example.com/old-notes",
    }
    # The stub and the stale personal-blog doc match both queries but never
    # become claims; the second query re-hits every kept chunk → folded.
    assert report.skipped_short == 2
    assert report.skipped_stale == 2
    assert report.duplicates_folded == 4
    assert len(report.claims) == 4


def test_exact_duplicate_corroboration_links_mutually_and_nothing_fuzzier(
    tmp_path: Path,
) -> None:
    report = _assemble(tmp_path)
    by_url = {claim.document_url: claim for claim in report.claims}
    guide = by_url["https://engineering.acme.com/guide"]
    mirror = by_url["https://example.org/mirror"]
    variant = by_url["https://example.org/variant"]
    assert guide.corroborating_claim_ids == (mirror.claim_id,)
    assert mirror.corroborating_claim_ids == (guide.claim_id,)
    # One word differs → near-duplicate → deliberately NOT linked.
    assert variant.corroborating_claim_ids == ()
    assert report.corroboration_groups == 1


def test_claim_ids_are_stable_and_content_derived(tmp_path: Path) -> None:
    report = _assemble(tmp_path)
    for claim in report.claims:
        assert claim.claim_id == derive_claim_id(claim.document_url, excerpt_key(claim.claim_text))
        assert len(claim.claim_id) == len("claim_") + 16


def test_breadcrumbless_chunks_keep_the_plain_document_url(tmp_path: Path) -> None:
    # Single-paragraph fixture docs chunk without headings → no fragment.
    report = _assemble(tmp_path)
    for claim in report.claims:
        assert claim.source_url == claim.document_url


# --------------------------------------------------------------------------- #
# ingestion
# --------------------------------------------------------------------------- #


def test_ingestor_strips_pipeline_supplied_score_fields(tmp_path: Path) -> None:
    report = _assemble(tmp_path)
    guide = next(c for c in report.claims if c.document_url == "https://engineering.acme.com/guide")
    tampered = {
        **guide.raw_record(),
        "source_type": "official_job_posting",
        "confidence_score": 0.99,
        "confidence_bucket": "high",
        "expires_at": "2030-01-01",
        "corroborating_claim_ids": [],
    }
    store = InMemorySourceClaimStore()
    ingestor = SourceClaimIngestor(
        clock=FrozenClock(_NOW),
        store=store,
        engineering_blog_hosts=frozenset(_MANIFEST.engineering_blog_hosts),
        personal_blog_hosts=frozenset(_MANIFEST.personal_blog_hosts),
    )
    outcome = ingestor.ingest(tampered)
    assert outcome.ok and outcome.claim is not None
    stored = outcome.claim
    # Every derived field was recomputed by the kernel, not taken from input.
    assert stored.source_type is SourceType.COMPANY_ENGINEERING_BLOG
    assert stored.confidence_score == 0.75
    assert stored.confidence_bucket is ConfidenceBucket.MEDIUM
    assert stored.expires_at != date(2030, 1, 1)


def test_ingest_assembled_scores_through_the_sanctioned_ingestor(
    tmp_path: Path,
) -> None:
    report = _assemble(tmp_path)
    store = InMemorySourceClaimStore()
    outcomes = ingest_assembled(
        report.claims, store=store, manifest=_MANIFEST, clock=FrozenClock(_NOW)
    )
    assert all(o.status is ClaimIngestionStatus.INGESTED for _, o in outcomes)
    stored = {c.claim_id: c for c in store.all()}
    assert len(stored) == 4
    # The full mutual corroboration lists survive to storage (audit trail),
    # whatever the scoring credited at each claim's own ingestion moment.
    guide = next(c for c in stored.values() if c.source_url == "https://engineering.acme.com/guide")
    mirror = next(c for c in stored.values() if c.source_url == "https://example.org/mirror")
    assert guide.corroborating_claim_ids == [mirror.claim_id]
    assert mirror.corroborating_claim_ids == [guide.claim_id]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _write_inputs(tmp_path: Path) -> tuple[Path, Path]:
    queries_path = tmp_path / "claim_queries.json"
    queries_path.write_text(_QUERY_SET.model_dump_json(), encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(_MANIFEST.model_dump_json(), encoding="utf-8")
    return queries_path, manifest_path


def _cli_args(tmp_path: Path, corpus_db: Path, snapshot_id: str, *extra: str) -> list[str]:
    queries_path, manifest_path = _write_inputs(tmp_path)
    return [
        "--queries",
        str(queries_path),
        "--manifest",
        str(manifest_path),
        "--corpus-db",
        str(corpus_db),
        "--snapshot",
        snapshot_id,
        *extra,
    ]


def test_cli_dry_run_scores_but_writes_nothing(tmp_path: Path, capsys: Any) -> None:
    corpus_db, snapshot_id = _build_corpus(tmp_path)
    app_db = tmp_path / "app.db"
    exit_code = main(
        _cli_args(tmp_path, corpus_db, snapshot_id, "--dry-run"),
        clock=FrozenClock(_NOW),
    )
    assert exit_code == 0
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert "ingested=4" in out
    assert "heuristic priors" in out
    assert not app_db.exists()


def test_cli_live_run_populates_the_store_idempotently(tmp_path: Path, capsys: Any) -> None:
    corpus_db, snapshot_id = _build_corpus(tmp_path)
    app_db = tmp_path / "app.db"
    args = _cli_args(tmp_path, corpus_db, snapshot_id, "--app-db", str(app_db))

    assert main(args, clock=FrozenClock(_NOW)) == 0
    store = SqliteSourceClaimStore(SqliteDatabase(app_db))
    first_claims = store.all()
    assert len(first_claims) == 4
    assert "ingested=4" in capsys.readouterr().out

    # Idempotent by claim identity: same snapshot + queries → all duplicates.
    assert main(args, clock=FrozenClock(_NOW)) == 0
    assert "duplicate=4" in capsys.readouterr().out
    assert [c.claim_id for c in store.all()] == [c.claim_id for c in first_claims]


def test_cli_requires_app_db_for_live_runs(tmp_path: Path) -> None:
    corpus_db, snapshot_id = _build_corpus(tmp_path)
    assert main(_cli_args(tmp_path, corpus_db, snapshot_id)) == 1


def test_cli_rejects_unknown_snapshot(tmp_path: Path) -> None:
    corpus_db, _ = _build_corpus(tmp_path)
    args = _cli_args(tmp_path, corpus_db, "snap_0000000000000000", "--dry-run")
    assert main(args) == 1


def test_cli_rejects_invalid_query_set(tmp_path: Path) -> None:
    corpus_db, snapshot_id = _build_corpus(tmp_path)
    args = _cli_args(tmp_path, corpus_db, snapshot_id, "--dry-run")
    args[1] = str(tmp_path / "manifest.json")  # a manifest is not a query set
    assert main(args) == 1


def test_repo_claim_query_set_is_valid_and_covers_all_tracks() -> None:
    query_set = load_claim_queries(_REPO_QUERIES)
    assert query_set.query_set_version == "claim-queries-v1"
    assert {q.track for q in query_set.queries} == set(CareerTrack)


# --------------------------------------------------------------------------- #
# golden: populated store → curation → strategist → validator accepts
# --------------------------------------------------------------------------- #


class _RecordingStrategist:
    """Delegating strategist recording the claim ids each call received."""

    def __init__(self, inner: FixtureStrategist) -> None:
        self._inner = inner
        self.seen_claims: list[tuple[str, ...]] = []

    def run(self, **kwargs: Any) -> SyllabusUnits:
        self.seen_claims.append(tuple(c.claim_id for c in kwargs.get("source_claims", ())))
        return self._inner.run(**kwargs)


def test_populated_store_feeds_strategist_through_curation_and_validation(
    tmp_path: Path,
) -> None:
    """The whole G-G loop with real data: refresh_claims populates the app
    database; propose curates the store (the expired real claim is filtered
    pre-prompt — D1 with non-fixture input), the strategist receives the
    surviving claims, cites one, and syllabus validation accepts the run."""
    corpus_db, snapshot_id = _build_corpus(tmp_path)
    app_db = tmp_path / "app.db"
    args = _cli_args(tmp_path, corpus_db, snapshot_id, "--app-db", str(app_db))
    assert main(args, clock=FrozenClock(_NOW)) == 0

    stored = SqliteSourceClaimStore(SqliteDatabase(app_db)).all()
    blog_claim = next(c for c in stored if c.source_type is SourceType.COMPANY_ENGINEERING_BLOG)
    expired_ids = {c.claim_id for c in stored if c.is_expired(_NOW)}
    assert expired_ids, "the 40-day-old unclassified claim must be in the store"

    profile = UserProfile.model_validate(next(iter_valid("user_profile")).payload)
    syllabus_payload = copy.deepcopy(next(iter_valid("syllabus_units")).payload)
    modules = cast("list[dict[str, Any]]", syllabus_payload["modules"])
    for module in modules:
        module["source_claim_ids"] = [blog_claim.claim_id]
    syllabus = SyllabusUnits.model_validate(syllabus_payload)
    plan = TaskPlan.model_validate(next(iter_valid("task_plan")).payload)

    recorder = _RecordingStrategist(FixtureStrategist({profile.target_role: syllabus}))

    def factory(deps: NodeDependencies) -> LlmNodeBundle:
        del deps
        return LlmNodeBundle(
            strategist=recorder,
            planner=FixturePlanner({syllabus.syllabus_version: plan}),
            reflection=DeterministicReflectionSummary(),
            explanation=DeterministicUserFacingExplanation(),
        )

    env = build_environment(
        nodes_factory=factory,
        clock=FrozenClock(_NOW),
        id_generator=DeterministicIdGenerator(),
        db_path=app_db,
    )
    service = CycleService(env)
    service.onboard(
        {
            "user_profile": profile.model_dump(mode="json"),
            "timezone": "UTC",
            "motivation_profile": None,
        }
    )
    proposed = service.propose(profile.user_id)
    assert proposed.state is S.AWAITING_USER_APPROVAL

    (seen,) = recorder.seen_claims
    assert blog_claim.claim_id in seen
    # D1 pre-prompt filter, now with real refresh-produced data: the expired
    # claim stays in the store (audit) but never reaches the prompt.
    assert not set(seen) & expired_ids
