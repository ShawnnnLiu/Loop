"""Tests for ``CompanyTarget`` and the classification-domain derivation."""

from __future__ import annotations

from agentic_calendar.contracts.company_target import (
    CompanyTarget,
    classification_domains,
)


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
