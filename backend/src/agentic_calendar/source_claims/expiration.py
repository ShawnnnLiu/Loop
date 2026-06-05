"""Claim expiration policy (axiom 08).

``expires_at`` is computed deterministically from the source type's window
(``priors.expiry_days``) anchored on the source's publication date when known,
else on the collection date. ``is_expired`` delegates to the contract method so
the inclusive boundary (``expires_at <= now.date()``) is defined exactly once.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from agentic_calendar.contracts.source_claim import SourceClaim, SourceType

from .priors import DEFAULT_CONFIDENCE_PRIORS, ConfidencePriors


def compute_expires_at(
    source_type: SourceType,
    *,
    anchor: date,
    priors: ConfidencePriors = DEFAULT_CONFIDENCE_PRIORS,
) -> date:
    """Return the expiry date for ``source_type`` measured from ``anchor``.

    ``anchor`` should be the ``source_published_date`` when available, otherwise
    ``date_collected`` (a source's age is measured from when it was published,
    not from when we happened to fetch it).
    """
    return anchor + timedelta(days=priors.expiry_days[source_type])


def is_expired(claim: SourceClaim, *, now: datetime) -> bool:
    """Inclusive expiry check, delegating to :meth:`SourceClaim.is_expired`."""
    return claim.is_expired(now)
