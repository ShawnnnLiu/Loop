"""Deterministic source-type classification (axiom 08).

``source_type`` is decided by domain / URL rules, never by LLM judgment. Only
the enumerable hosts from the axiom 08 table are recognised; everything else
falls through to ``UNCLASSIFIED`` (honest — "company careers domain" / "company
engineering blog" / "personal blog" are not decidable from a URL alone). A
caller that *does* know the context may inject ``known_company_domains``,
``engineering_blog_hosts``, and ``personal_blog_hosts`` without changing this
signature later. Without those injections the corresponding axiom-08 source
types (``official_job_posting`` via company domain, ``company_engineering_blog``,
``personal_anecdote``) are unreachable by design — they are declared by the
operator, never guessed from a bare URL.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlsplit

from agentic_calendar.contracts.source_claim import SourceType

#: Applicant-tracking-system and careers hosts → official job postings.
_ATS_HOSTS: frozenset[str] = frozenset(
    {
        "greenhouse.io",
        "boards.greenhouse.io",
        "lever.co",
        "jobs.lever.co",
        "ashbyhq.com",
        "jobs.ashbyhq.com",
        "workday.com",
        "myworkdayjobs.com",
    }
)

_ROLE_TAXONOMY_HOSTS: frozenset[str] = frozenset({"levels.fyi"})

_INTERVIEW_POSTMORTEM_HOSTS: frozenset[str] = frozenset(
    {"interviewing.io", "pramp.com"}
)

_INTERVIEW_REPORT_HOSTS: frozenset[str] = frozenset(
    {"glassdoor.com", "blind.com", "teamblind.com"}
)


def _host(url: str) -> str | None:
    """Return the lowercased host of ``url`` with a leading ``www.`` stripped.

    Accepts bare hosts (``"levels.fyi/..."``) as well as full URLs. Returns
    ``None`` for anything without a recoverable host.
    """
    try:
        parts = urlsplit(url if "//" in url else f"//{url}")
    except ValueError:
        return None
    host = parts.hostname
    if not host:
        return None
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _matches(host: str, domains: Iterable[str]) -> bool:
    """True when ``host`` equals or is a subdomain of any domain in ``domains``."""
    return any(host == d or host.endswith(f".{d}") for d in domains)


def classify_source(
    url: str,
    *,
    known_company_domains: frozenset[str] = frozenset(),
    engineering_blog_hosts: frozenset[str] = frozenset(),
    personal_blog_hosts: frozenset[str] = frozenset(),
) -> SourceType:
    """Classify a source URL into a :class:`SourceType`, deterministically.

    Unknown or unparseable URLs return ``UNCLASSIFIED`` rather than raising.
    Operator-declared host sets are checked after the enumerable high-trust
    hosts; ``personal_blog_hosts`` is the only path to ``PERSONAL_ANECDOTE``
    (a personal blog is not inferable from a bare URL, so it is never guessed).
    """
    host = _host(url)
    if host is None:
        return SourceType.UNCLASSIFIED

    if _matches(host, _ATS_HOSTS):
        return SourceType.OFFICIAL_JOB_POSTING
    if _matches(host, _ROLE_TAXONOMY_HOSTS):
        return SourceType.ROLE_TAXONOMY
    if _matches(host, _INTERVIEW_POSTMORTEM_HOSTS):
        return SourceType.INTERVIEW_POSTMORTEM
    if _matches(host, _INTERVIEW_REPORT_HOSTS):
        return SourceType.INTERVIEW_REPORT
    if engineering_blog_hosts and _matches(host, engineering_blog_hosts):
        return SourceType.COMPANY_ENGINEERING_BLOG
    if known_company_domains and _matches(host, known_company_domains):
        return SourceType.OFFICIAL_JOB_POSTING
    if personal_blog_hosts and _matches(host, personal_blog_hosts):
        return SourceType.PERSONAL_ANECDOTE
    return SourceType.UNCLASSIFIED
