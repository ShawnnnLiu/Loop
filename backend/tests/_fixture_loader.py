"""Helpers for loading paired ``<name>.json`` / ``<name>.expected.json`` fixtures.

Used by ``tests/contracts/`` so each contract has the same loader. Kept under
``tests/`` (not under ``src/``) because it is test infrastructure only.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

FIXTURES_ROOT = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class ValidFixture:
    name: str
    payload: dict[str, object]


@dataclass(frozen=True)
class InvalidFixture:
    name: str
    payload: dict[str, object]
    expected: dict[str, object]


def _load_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise TypeError(f"fixture {path} must contain a JSON object")
    return data


def iter_valid(contract: str) -> Iterator[ValidFixture]:
    folder = FIXTURES_ROOT / "valid" / contract
    if not folder.exists():
        return
    for path in sorted(folder.glob("*.json")):
        yield ValidFixture(name=path.stem, payload=_load_json(path))


def iter_invalid(contract: str) -> Iterator[InvalidFixture]:
    folder = FIXTURES_ROOT / "invalid" / contract
    if not folder.exists():
        return
    for path in sorted(folder.glob("*.json")):
        if path.name.endswith(".expected.json"):
            continue
        expected_path = path.with_suffix(".expected.json")
        if not expected_path.exists():
            raise FileNotFoundError(
                f"invalid fixture {path} is missing its paired {expected_path.name}"
            )
        yield InvalidFixture(
            name=path.stem,
            payload=_load_json(path),
            expected=_load_json(expected_path),
        )
