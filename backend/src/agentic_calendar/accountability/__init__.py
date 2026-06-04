"""Accountability region.

Phase 3 populates the sponsor-reporting slice of the Accountability Layer
(``docs/axioms/21-accountability-layer.md``): the sponsor invite lifecycle, the
deterministic privacy filter, the Sponsor Report Generator, and the Delivery
Service. The broader Accountability Policy Engine and accountability-state
projection are Phase 7; telemetry that feeds them is Phase 4.

Determinism boundary: permission decisions, visibility levels, included fields,
triggers, and the privacy denylist are all owned here. The only LLM-touchable
value is ``suggested_support_action`` wording, which is privacy-scanned before
it can be delivered.

Allowed dependencies (enforced by ``backend/.importlinter``): ``common``,
``contracts``. This region is a leaf — it imports no other region.
"""

from __future__ import annotations

from .delivery import DeliveryOutcome, SponsorReportDeliveryService
from .notification_log_store import (
    InMemoryNotificationLogStore,
    NotificationLogAlreadyExistsError,
    NotificationLogStore,
    NotificationLogStoreError,
)
from .privacy_filter import (
    DEFAULT_DENYLIST_MARKERS,
    DENYLIST_KEYS,
    PrivacyFilter,
    PrivacyVerdict,
)
from .report_generator import GenerationOutcome, SponsorReportGenerator
from .sponsor_store import (
    IllegalSponsorTransitionError,
    InMemorySponsorStore,
    SponsorAlreadyExistsError,
    SponsorNotFoundError,
    SponsorStore,
    SponsorStoreError,
)

__all__ = [
    "DEFAULT_DENYLIST_MARKERS",
    "DENYLIST_KEYS",
    "DeliveryOutcome",
    "GenerationOutcome",
    "IllegalSponsorTransitionError",
    "InMemoryNotificationLogStore",
    "InMemorySponsorStore",
    "NotificationLogAlreadyExistsError",
    "NotificationLogStore",
    "NotificationLogStoreError",
    "PrivacyFilter",
    "PrivacyVerdict",
    "SponsorAlreadyExistsError",
    "SponsorNotFoundError",
    "SponsorReportDeliveryService",
    "SponsorReportGenerator",
    "SponsorStore",
    "SponsorStoreError",
]
