"""Tests for ``CompanyTarget`` and the classification-domain derivation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agentic_calendar.contracts.company_target import (
    CompanyTarget,
    classification_domains,
)
from tests._fixture_loader import iter_invalid, iter_valid


def test_classification_domains_flatten_and_casefold() -> None:
    targets = [
        CompanyTarget(
            name="Acme",
            careers_domains=["Acme.com"],
            engineering_blog_hosts=["ENG.acme.com"],
        ),
        CompanyTarget(name="Globex", careers_domains=["globex.io"]),
    ]
    known, blogs = classification_domains(targets)
    assert known == frozenset({"acme.com", "globex.io"})
    assert blogs == frozenset({"eng.acme.com"})


def test_classification_domains_empty() -> None:
    assert classification_domains([]) == (frozenset(), frozenset())
    assert classification_domains([CompanyTarget(name="X")]) == (
        frozenset(),
        frozenset(),
    )


def test_blank_domains_dropped() -> None:
    target = CompanyTarget(
        name="X", careers_domains=["", "  "], engineering_blog_hosts=["  "]
    )
    assert classification_domains([target]) == (frozenset(), frozenset())


CONTRACT = "company_target"


@pytest.mark.parametrize("fixture", list(iter_valid(CONTRACT)), ids=lambda f: f.name)
def test_valid_fixture_parses(fixture: object) -> None:
    obj = CompanyTarget.model_validate(fixture.payload)  # type: ignore[attr-defined]
    assert isinstance(obj, CompanyTarget)


@pytest.mark.parametrize("fixture", list(iter_invalid(CONTRACT)), ids=lambda f: f.name)
def test_invalid_fixture_rejected(fixture: object) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        CompanyTarget.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"
