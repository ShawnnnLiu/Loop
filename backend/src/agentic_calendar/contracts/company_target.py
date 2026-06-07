"""``company_target`` contract + classification-context derivation.

A target company the user is preparing for, paired with the domains the operator
trusts for it. This is the explicit *company context* that flows into two places
(axiom 08 / 18):

* deterministic source classification — its domains let ``classify_source``
  recognise that company's careers pages (``official_job_posting``) and
  engineering blog (``company_engineering_blog``) instead of falling through to
  ``unclassified``;
* cache keys — its ``name`` is the ``company_target`` dimension.

Domains are declared explicitly by the caller rather than inferred from the
company name: "LLMs propose, deterministic infrastructure disposes" — no fuzzy
name→domain guessing in the control plane.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field


class CompanyTarget(BaseModel):
    """One target company and the domains trusted as its provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    careers_domains: list[str] = Field(default_factory=list)
    engineering_blog_hosts: list[str] = Field(default_factory=list)


def classification_domains(
    targets: Sequence[CompanyTarget],
) -> tuple[frozenset[str], frozenset[str]]:
    """Return ``(known_company_domains, engineering_blog_hosts)`` for classification.

    Domains are lowercased to match ``classify_source``'s host comparison. The
    two frozensets are exactly what ``SourceClaimIngestor`` /
    ``classify_source`` accept as company context.
    """
    careers = frozenset(
        d.strip().casefold()
        for t in targets
        for d in t.careers_domains
        if d.strip()
    )
    blogs = frozenset(
        h.strip().casefold()
        for t in targets
        for h in t.engineering_blog_hosts
        if h.strip()
    )
    return careers, blogs
