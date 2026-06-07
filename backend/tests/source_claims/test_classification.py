"""Tests for deterministic source-type classification (axiom 08)."""

from __future__ import annotations

import pytest

from agentic_calendar.contracts.source_claim import SourceType
from agentic_calendar.source_claims.classification import classify_source


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://boards.greenhouse.io/acme/jobs/1", SourceType.OFFICIAL_JOB_POSTING),
        ("https://acme.lever.co/x", SourceType.OFFICIAL_JOB_POSTING),
        ("https://jobs.ashbyhq.com/acme", SourceType.OFFICIAL_JOB_POSTING),
        ("https://acme.wd1.myworkdayjobs.com/x", SourceType.OFFICIAL_JOB_POSTING),
        ("https://levels.fyi/company/Stripe", SourceType.ROLE_TAXONOMY),
        ("https://www.levels.fyi/x", SourceType.ROLE_TAXONOMY),
        ("levels.fyi/bare/host", SourceType.ROLE_TAXONOMY),
        ("https://interviewing.io/guide", SourceType.INTERVIEW_POSTMORTEM),
        ("https://www.pramp.com/x", SourceType.INTERVIEW_POSTMORTEM),
        ("https://www.glassdoor.com/Interview/x", SourceType.INTERVIEW_REPORT),
        ("https://www.teamblind.com/post", SourceType.INTERVIEW_REPORT),
        ("https://blind.com/post", SourceType.INTERVIEW_REPORT),
        ("https://random.example.org/x", SourceType.UNCLASSIFIED),
        ("not a url", SourceType.UNCLASSIFIED),
        ("", SourceType.UNCLASSIFIED),
    ],
)
def test_classify_source(url: str, expected: SourceType) -> None:
    assert classify_source(url) is expected


def test_injected_company_context() -> None:
    assert (
        classify_source(
            "https://careers.acme.com/x",
            known_company_domains=frozenset({"acme.com"}),
        )
        is SourceType.OFFICIAL_JOB_POSTING
    )
    assert (
        classify_source(
            "https://eng.acme.com/blog",
            engineering_blog_hosts=frozenset({"eng.acme.com"}),
        )
        is SourceType.COMPANY_ENGINEERING_BLOG
    )
