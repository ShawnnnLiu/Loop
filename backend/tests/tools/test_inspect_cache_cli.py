"""Tests for the ``inspect_cache`` operator CLI."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from agentic_calendar.cache.keys import CacheKey, CacheTarget
from agentic_calendar.cache.store import CacheEntry
from agentic_calendar.contracts.source_claim import (
    ConfidenceBucket,
    SourceClaim,
    SourceType,
)
from agentic_calendar.tools.inspect_cache import main

NOW_STR = "2026-06-04T12:00:00+00:00"
NOW = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)


def _claim() -> SourceClaim:
    return SourceClaim(
        claim_id="c1",
        claim_text="A verifiable claim.",
        source_url="https://x.example.com/a",
        source_type=SourceType.INTERVIEW_REPORT,
        date_collected=date(2026, 1, 1),
        confidence_score=0.6,
        confidence_bucket=ConfidenceBucket.MEDIUM,
        expires_at=date(2026, 12, 1),
    )


def _entry(claims: tuple[str, ...]) -> CacheEntry:
    key = CacheKey(
        target=CacheTarget.SYLLABUS_UNITS,
        role_target="backend swe",
        freshness_window="2026-06",
        object_schema_version="syl-v1",
        claim_version_set=claims,
    )
    return CacheEntry(
        key=key,
        value_kind=CacheTarget.SYLLABUS_UNITS,
        value_json={},
        source_claim_ids=claims,
        created_at=NOW,
    )


def _write(tmp_path: Path, claims: list[SourceClaim], entries: list[CacheEntry]) -> Path:
    data = {
        "claims": [c.model_dump(mode="json") for c in claims],
        "entries": [e.model_dump(mode="json") for e in entries],
    }
    path = tmp_path / "cache.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_reports_live_and_stale(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _write(tmp_path, [_claim()], [_entry(("c1",)), _entry(("missing",))])
    rc = main([str(path), "--now", NOW_STR, "--json"])
    assert rc == 0
    rows = json.loads(capsys.readouterr().out)
    assert sorted(r["status"] for r in rows) == ["live", "stale"]


def test_text_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _write(tmp_path, [_claim()], [_entry(("c1",))])
    assert main([str(path), "--now", NOW_STR]) == 0
    assert "live" in capsys.readouterr().out


def test_naive_now_rejected(tmp_path: Path) -> None:
    path = _write(tmp_path, [], [])
    assert main([str(path), "--now", "2026-06-04T12:00:00"]) == 1


def test_missing_file_returns_error(tmp_path: Path) -> None:
    assert main([str(tmp_path / "nope.json"), "--now", NOW_STR]) == 1
