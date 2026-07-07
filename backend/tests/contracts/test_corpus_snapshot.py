"""Tests for the ``CorpusSnapshot`` contract and its identity derivation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.corpus_snapshot import (
    ChunkingParams,
    CorpusSnapshot,
    chunking_fingerprint,
    derive_snapshot_id,
)
from tests._fixture_loader import iter_invalid, iter_valid

CONTRACT = "corpus_snapshot"

_H1 = "1cc4db79381ad4643b9ab7959b974f4157fbe51a5b9cea05e4e65ffc7669dea7"
_H2 = "1514ecd5c78e9ec5f4dc84a3c01208b002cf834db202b1c8dda3e03d7fff5f4e"

_PARAMS = ChunkingParams(algorithm="structure_v1", target_chars=1600, overlap_chars=200)


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    snapshot = CorpusSnapshot.model_validate(payload)
    assert snapshot.snapshot_id == payload["snapshot_id"]


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        CorpusSnapshot.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"


def test_derive_snapshot_id_is_order_independent() -> None:
    assert derive_snapshot_id([_H1, _H2], _PARAMS) == derive_snapshot_id(
        [_H2, _H1], _PARAMS
    )


def test_derive_snapshot_id_deduplicates_members() -> None:
    # Two documents with identical content pin the same evidence bytes, so
    # the identity collapses them (the derivation hashes the *set*).
    assert derive_snapshot_id([_H1, _H1], _PARAMS) == derive_snapshot_id([_H1], _PARAMS)


def test_derive_snapshot_id_is_well_formed() -> None:
    snapshot_id = derive_snapshot_id([_H1], _PARAMS)
    assert snapshot_id.startswith("snap_")
    assert len(snapshot_id) == len("snap_") + 16
    assert derive_snapshot_id([_H1], _PARAMS) != derive_snapshot_id([_H2], _PARAMS)


def test_derive_snapshot_id_depends_on_chunking_params() -> None:
    # Re-chunking is a new snapshot: same members, different params → new id.
    other = ChunkingParams(algorithm="structure_v1", target_chars=800, overlap_chars=100)
    assert derive_snapshot_id([_H1], _PARAMS) != derive_snapshot_id([_H1], other)


def test_chunking_fingerprint_is_canonical() -> None:
    assert chunking_fingerprint(_PARAMS) == "structure_v1:1600:200"
