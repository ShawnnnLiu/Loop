"""Tests for the corpus-evidence enrichment CLI (résumé-intake RI-F). Offline.

The load-bearing properties: counting is a pure function of (snapshot,
taxonomy) — phrase semantics, track-scoped, distinct-chunk union with a
per-alias breakdown; the output is a NEW contract-valid taxonomy version with
every non-evidence field verbatim (append-only, never overwritten); zero
support is flagged for human review, never deleted; ``--dry-run`` writes
nothing.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import (
    CorpusDocument,
    content_hash_for,
    derive_doc_id,
)
from agentic_calendar.contracts.corpus_snapshot import ChunkingParams
from agentic_calendar.contracts.skill_taxonomy import SkillTaxonomy
from agentic_calendar.contracts.source_claim import SourceType
from agentic_calendar.retrieval import SqliteChunkIndex, SqliteCorpusRegistry
from agentic_calendar.skill_taxonomy.registry import load_taxonomy
from agentic_calendar.tools.enrich_taxonomy import (
    build_enriched_taxonomy,
    gather_evidence,
    main,
    next_taxonomy_version,
)

_COLLECTED = date(2026, 7, 19)
_CREATED_AT = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
_PARAMS = ChunkingParams(algorithm="structure_v1", target_chars=400, overlap_chars=0)

#: url -> (text, track_tags). Geometry the assertions depend on: each text is
#: one chunk; "power bi" appears twice in ONE chunk (distinct-chunk union must
#: count 1); "kubernetes" appears in an SWE doc and an MLE doc (the track
#: filter must exclude the MLE one); "system … preparation" words co-occur
#: without adjacency (phrase semantics must not match).
_DOCS: dict[str, tuple[str, tuple[CareerTrack, ...]]] = {
    "https://example.com/swe-guide": (
        "System design interviews reward structured preparation.\n"
        "Learn kubernetes basics early in your preparation.",
        (CareerTrack.SWE,),
    ),
    "https://example.com/analyst-guide": (
        "Dashboards in power bi are the analyst staple.\n"
        "A power bi certification helps a first screen.",
        (CareerTrack.DATA_ANALYST,),
    ),
    "https://example.com/mle-guide": (
        "Feature engineering pipelines need kubernetes for scale.",
        (CareerTrack.MLE,),
    ),
}

_TAXONOMY = {
    "taxonomy_version": "skill-taxonomy-v1",
    "entries": [
        {
            "skill_id": "skill.system-design",
            "display_name": "System design",
            "aliases": ["system design", "systems design"],
            "track_tags": ["swe"],
            "kind": "concept",
            "corpus_evidence": None,
        },
        {
            "skill_id": "skill.power-bi",
            "display_name": "Power BI",
            "aliases": ["power bi", "powerbi"],
            "track_tags": ["data_analyst"],
            "kind": "tool",
            "corpus_evidence": None,
        },
        {
            "skill_id": "skill.kubernetes",
            "display_name": "Kubernetes",
            "aliases": ["kubernetes", "k8s"],
            "track_tags": ["swe"],
            "kind": "tool",
            "corpus_evidence": None,
        },
        {
            "skill_id": "skill.flurbo-js",
            "display_name": "Flurbo.js",
            "aliases": ["flurbo.js"],
            "track_tags": ["swe"],
            "kind": "framework",
            "corpus_evidence": None,
        },
    ],
}


def _build_corpus(tmp_path: Path) -> tuple[Path, str]:
    """Register the fixture docs, pin a snapshot, build the index."""
    corpus_db_path = tmp_path / "corpus.db"
    db = SqliteDatabase(corpus_db_path)
    registry = SqliteCorpusRegistry(db)
    doc_ids = []
    for url, (text, tracks) in _DOCS.items():
        document = CorpusDocument(
            doc_id=derive_doc_id(url, _COLLECTED),
            source_url=url,
            source_type=SourceType.UNCLASSIFIED,
            license_note="Public page; test fixture.",
            date_collected=_COLLECTED,
            track_tags=list(tracks),
            content_hash=content_hash_for(text),
            title=url.rsplit("/", 1)[-1],
        )
        registry.register(document, text=text)
        doc_ids.append(document.doc_id)
    snapshot = registry.create_snapshot(
        doc_ids, created_at=_CREATED_AT, chunking_params=_PARAMS
    )
    SqliteChunkIndex(db).build(registry, snapshot)
    return corpus_db_path, snapshot.snapshot_id


def _write_taxonomy(tmp_path: Path) -> Path:
    path = tmp_path / "skill_taxonomy_v1.json"
    path.write_text(json.dumps(_TAXONOMY, indent=2) + "\n", encoding="utf-8")
    return path


def _evidence_by_id(tmp_path: Path) -> dict[str, object]:
    corpus_db_path, snapshot_id = _build_corpus(tmp_path)
    index = SqliteChunkIndex(SqliteDatabase(corpus_db_path))
    taxonomy = SkillTaxonomy.model_validate(_TAXONOMY)
    evidence = gather_evidence(index=index, snapshot_id=snapshot_id, taxonomy=taxonomy)
    return {e.skill_id: e for e in evidence}


# --------------------------------------------------------------------------- #
# counting
# --------------------------------------------------------------------------- #


def test_counts_are_phrase_scoped_track_scoped_distinct_chunk_unions(
    tmp_path: Path,
) -> None:
    by_id = _evidence_by_id(tmp_path)
    swe_doc = derive_doc_id("https://example.com/swe-guide", _COLLECTED)
    analyst_doc = derive_doc_id("https://example.com/analyst-guide", _COLLECTED)

    system_design = by_id["skill.system-design"]
    assert system_design.occurrence_count == 1
    assert system_design.supporting_doc_ids == (swe_doc,)
    # Per-alias breakdown, in alias order: the matching spelling counts, the
    # variant honestly reports zero.
    assert [(a.alias, a.chunk_count) for a in system_design.per_alias] == [
        ("system design", 1),
        ("systems design", 0),
    ]

    # "power bi" occurs twice in one chunk: distinct-chunk union counts 1.
    power_bi = by_id["skill.power-bi"]
    assert power_bi.occurrence_count == 1
    assert power_bi.supporting_doc_ids == (analyst_doc,)
    assert [(a.alias, a.chunk_count) for a in power_bi.per_alias] == [
        ("power bi", 1),
        ("powerbi", 0),
    ]

    # "kubernetes" also appears in the MLE doc — the SWE-scoped entry must
    # not see it (track-scoped support, not corpus-wide frequency).
    kubernetes = by_id["skill.kubernetes"]
    assert kubernetes.occurrence_count == 1
    assert kubernetes.supporting_doc_ids == (swe_doc,)

    flurbo = by_id["skill.flurbo-js"]
    assert flurbo.occurrence_count == 0
    assert flurbo.supporting_doc_ids == ()


def test_gather_evidence_is_deterministic(tmp_path: Path) -> None:
    corpus_db_path, snapshot_id = _build_corpus(tmp_path)
    index = SqliteChunkIndex(SqliteDatabase(corpus_db_path))
    taxonomy = SkillTaxonomy.model_validate(_TAXONOMY)
    first = gather_evidence(index=index, snapshot_id=snapshot_id, taxonomy=taxonomy)
    second = gather_evidence(index=index, snapshot_id=snapshot_id, taxonomy=taxonomy)
    assert first == second
    assert [e.skill_id for e in first] == [e["skill_id"] for e in _TAXONOMY["entries"]]


# --------------------------------------------------------------------------- #
# the new taxonomy version
# --------------------------------------------------------------------------- #


def test_next_taxonomy_version_bumps_and_rejects_malformed() -> None:
    assert next_taxonomy_version("skill-taxonomy-v4") == "skill-taxonomy-v5"
    with pytest.raises(ValueError, match="malformed"):
        next_taxonomy_version("taxonomy-4")


def test_enriched_taxonomy_fills_evidence_and_nothing_else(tmp_path: Path) -> None:
    corpus_db_path, snapshot_id = _build_corpus(tmp_path)
    index = SqliteChunkIndex(SqliteDatabase(corpus_db_path))
    taxonomy = SkillTaxonomy.model_validate(_TAXONOMY)
    evidence = gather_evidence(index=index, snapshot_id=snapshot_id, taxonomy=taxonomy)

    enriched = build_enriched_taxonomy(taxonomy, evidence, snapshot_id=snapshot_id)

    assert enriched.taxonomy_version == "skill-taxonomy-v2"
    assert len(enriched.entries) == len(taxonomy.entries)
    for before, after in zip(taxonomy.entries, enriched.entries, strict=True):
        # Everything except the evidence is verbatim — enrichment annotates,
        # it never curates (no adds, drops, renames, or re-tags).
        assert after.model_dump(exclude={"corpus_evidence"}) == before.model_dump(
            exclude={"corpus_evidence"}
        )
        assert after.corpus_evidence is not None
        assert after.corpus_evidence.snapshot_id == snapshot_id
    zero = next(e for e in enriched.entries if e.skill_id == "skill.flurbo-js")
    assert zero.corpus_evidence is not None
    assert zero.corpus_evidence.occurrence_count == 0
    assert zero.corpus_evidence.supporting_doc_ids == []


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def test_dry_run_reports_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus_db_path, snapshot_id = _build_corpus(tmp_path)
    taxonomy_path = _write_taxonomy(tmp_path)

    exit_code = main(
        [
            "--taxonomy",
            str(taxonomy_path),
            "--corpus-db",
            str(corpus_db_path),
            "--snapshot",
            snapshot_id,
            "--dry-run",
        ]
    )

    assert exit_code == 0
    assert not (tmp_path / "skill_taxonomy_v2.json").exists()
    out = capsys.readouterr().out
    # Per-alias breakdown and the zero-support flag are the report's point.
    assert "power bi=1" in out
    assert "zero-support entries (1) — flagged for human curation review:" in out
    assert "skill.flurbo-js (Flurbo.js)" in out
    assert "dry-run: nothing written" in out


def test_live_run_writes_next_version_and_refuses_overwrite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus_db_path, snapshot_id = _build_corpus(tmp_path)
    taxonomy_path = _write_taxonomy(tmp_path)
    argv = [
        "--taxonomy",
        str(taxonomy_path),
        "--corpus-db",
        str(corpus_db_path),
        "--snapshot",
        snapshot_id,
    ]

    assert main(argv) == 0
    out_path = tmp_path / "skill_taxonomy_v2.json"
    # The written file is contract-valid via the same loader production uses.
    written = load_taxonomy(out_path)
    assert written.taxonomy_version == "skill-taxonomy-v2"
    assert all(e.corpus_evidence is not None for e in written.entries)
    assert f"wrote {out_path}" in capsys.readouterr().out

    # Append-only: a re-run must refuse to overwrite the existing version.
    assert main(argv) == 1
    assert "append-only" in capsys.readouterr().err


def test_live_run_honors_explicit_out_path(tmp_path: Path) -> None:
    corpus_db_path, snapshot_id = _build_corpus(tmp_path)
    taxonomy_path = _write_taxonomy(tmp_path)
    out_path = tmp_path / "custom_out.json"

    exit_code = main(
        [
            "--taxonomy",
            str(taxonomy_path),
            "--corpus-db",
            str(corpus_db_path),
            "--snapshot",
            snapshot_id,
            "--out",
            str(out_path),
        ]
    )

    assert exit_code == 0
    assert load_taxonomy(out_path).taxonomy_version == "skill-taxonomy-v2"


def test_unknown_snapshot_and_bad_inputs_are_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus_db_path, _ = _build_corpus(tmp_path)
    taxonomy_path = _write_taxonomy(tmp_path)

    assert (
        main(
            [
                "--taxonomy",
                str(taxonomy_path),
                "--corpus-db",
                str(corpus_db_path),
                "--snapshot",
                "snap_0000000000000000",
                "--dry-run",
            ]
        )
        == 1
    )
    assert "is not in" in capsys.readouterr().err

    assert (
        main(
            [
                "--taxonomy",
                str(taxonomy_path),
                "--corpus-db",
                str(tmp_path / "missing.db"),
                "--snapshot",
                "snap_0000000000000000",
                "--dry-run",
            ]
        )
        == 1
    )
    assert "corpus database not found" in capsys.readouterr().err

    assert (
        main(
            [
                "--taxonomy",
                str(tmp_path / "missing.json"),
                "--corpus-db",
                str(corpus_db_path),
                "--snapshot",
                "snap_0000000000000000",
                "--dry-run",
            ]
        )
        == 1
    )
    assert "cannot read taxonomy file" in capsys.readouterr().err
