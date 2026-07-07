"""Vector cache + cosine tests (G-E). Hand-computed arithmetic, no network."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.retrieval import SqliteVectorStore, cosine_similarity
from agentic_calendar.retrieval.vectors import pack_vector, unpack_vector


@pytest.fixture
def store(tmp_path: Path) -> SqliteVectorStore:
    return SqliteVectorStore(SqliteDatabase(tmp_path / "vectors.db"))


def test_pack_unpack_roundtrip_is_exact_for_float32() -> None:
    vector = [0.5, -1.25, 3.0, 0.0]  # exactly representable in float32
    assert unpack_vector(pack_vector(vector), dimension=4) == vector


def test_unpack_dimension_mismatch_raises() -> None:
    blob = pack_vector([1.0, 2.0])
    with pytest.raises(ValueError):
        unpack_vector(blob, dimension=3)


def test_cosine_hand_computed() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([1.0, 1.0], [1.0, 1.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)
    # (3,4)·(4,3) / (5·5) = 24/25
    assert cosine_similarity([3.0, 4.0], [4.0, 3.0]) == pytest.approx(24 / 25)


def test_cosine_zero_norm_is_honest_zero() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_cosine_dimension_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        cosine_similarity([1.0], [1.0, 2.0])


def test_put_get_roundtrip(store: SqliteVectorStore) -> None:
    written = store.put_many(
        [("hash-a", [1.0, 2.0]), ("hash-b", [3.0, 4.0])],
        model_name="voyage-3.5",
        input_type="document",
    )
    assert written == 2
    assert store.get("hash-a", model_name="voyage-3.5", input_type="document") == [1.0, 2.0]
    assert store.get("hash-missing", model_name="voyage-3.5", input_type="document") is None


def test_first_write_pins_rewrites_are_ignored(store: SqliteVectorStore) -> None:
    store.put_many([("hash-a", [1.0])], model_name="m", input_type="document")
    rewritten = store.put_many([("hash-a", [9.0])], model_name="m", input_type="document")
    assert rewritten == 0
    assert store.get("hash-a", model_name="m", input_type="document") == [1.0]


def test_identity_includes_model_and_input_type(store: SqliteVectorStore) -> None:
    store.put_many([("hash-a", [1.0])], model_name="m1", input_type="document")
    store.put_many([("hash-a", [2.0])], model_name="m2", input_type="document")
    store.put_many([("hash-a", [3.0])], model_name="m1", input_type="query")
    assert store.get("hash-a", model_name="m1", input_type="document") == [1.0]
    assert store.get("hash-a", model_name="m2", input_type="document") == [2.0]
    assert store.get("hash-a", model_name="m1", input_type="query") == [3.0]
    assert store.count(model_name="m1") == 2


def test_get_many_and_missing(store: SqliteVectorStore) -> None:
    store.put_many([("h1", [1.0]), ("h2", [2.0])], model_name="m", input_type="document")
    cached = store.get_many(["h1", "h2", "h3", "h1"], model_name="m", input_type="document")
    assert cached == {"h1": [1.0], "h2": [2.0]}
    assert store.missing(
        ["h3", "h1", "h4", "h3"], model_name="m", input_type="document"
    ) == ["h3", "h4"]
