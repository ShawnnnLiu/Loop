"""Accountability region.

Phase 3 populated the sponsor-reporting slice of the Accountability Layer
(``docs/axioms/21-accountability-layer.md``): the sponsor invite lifecycle, the
deterministic privacy filter, the Sponsor Report Generator, and the Delivery
Service. Phase 7 adds the rest of the layer: the accountability-contract
derivation, the append-only check-in store and evaluator, the
accountability-state projection, the deterministic Accountability Policy
Engine, nudge delivery, and the recommitment flow. Telemetry that feeds them
is Phase 4.

Determinism boundary: permission decisions, visibility levels, included
fields, triggers, thresholds, policy ordering, quiet-hours deferral, and the
privacy denylist are all owned here. The only LLM-touchable values are
wording surfaces (``suggested_support_action``, nudge phrasing), which never
become control-plane state.

Allowed dependencies (enforced by ``backend/.importlinter``): ``common``,
``contracts``. This region is a leaf — it imports no other region; the
composition root (operator CLIs) wires it to telemetry, drift, and planning
from outside the region set.
"""

from __future__ import annotations

from .adaptation import ThresholdAdaptation, adapt_contract_thresholds
from .checkin import (
    CheckinAssessment,
    CheckinStatus,
    evaluate_checkin,
    most_recent_due_instant,
)
from .checkin_store import (
    CheckinEventAlreadyExistsError,
    CheckinEventStore,
    CheckinEventStoreError,
    InMemoryCheckinEventStore,
)
from .contract import (
    CHECKIN_GRACE_HOURS,
    LOW_COMPLETION_RATE_FLOOR,
    NUDGE_TONE_TIER_BY_PRESSURE,
    derive_accountability_contract,
    derive_nudge_tone_tier,
)
from .delivery import DeliveryOutcome, SponsorReportDeliveryService
from .notification_log_store import (
    InMemoryNotificationLogStore,
    NotificationLogAlreadyExistsError,
    NotificationLogStore,
    NotificationLogStoreError,
)
from .nudge_store import (
    InMemoryNudgeStore,
    NudgeAlreadyExistsError,
    NudgeStore,
    NudgeStoreError,
)
from .nudges import NudgeDeliveryService, resolve_deliver_at
from .policy_engine import (
    SPONSOR_SUMMARY_MISSED_TASK_FLOOR,
    AccountabilityOutcome,
    AccountabilityPolicyEngine,
    evaluate_accountability,
)
from .privacy_filter import (
    DEFAULT_DENYLIST_MARKERS,
    DENYLIST_KEYS,
    PrivacyFilter,
    PrivacyVerdict,
)
from .projection import (
    DISENGAGED_COMPLETION_FLOOR,
    ProjectionInput,
    behind_schedule_percent,
    project_accountability_state,
)
from .recommitment import (
    RECOMMITMENT_CHOICE_TO_RECOVERY_MODE,
    InMemoryRecommitmentStore,
    RecommitmentAlreadyAnsweredError,
    RecommitmentRequestAlreadyExistsError,
    RecommitmentRequestNotFoundError,
    RecommitmentStore,
    RecommitmentStoreError,
    record_recommitment,
    request_recommitment,
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
    "CHECKIN_GRACE_HOURS",
    "DEFAULT_DENYLIST_MARKERS",
    "DENYLIST_KEYS",
    "DISENGAGED_COMPLETION_FLOOR",
    "LOW_COMPLETION_RATE_FLOOR",
    "NUDGE_TONE_TIER_BY_PRESSURE",
    "RECOMMITMENT_CHOICE_TO_RECOVERY_MODE",
    "SPONSOR_SUMMARY_MISSED_TASK_FLOOR",
    "AccountabilityOutcome",
    "AccountabilityPolicyEngine",
    "CheckinAssessment",
    "CheckinEventAlreadyExistsError",
    "CheckinEventStore",
    "CheckinEventStoreError",
    "CheckinStatus",
    "DeliveryOutcome",
    "GenerationOutcome",
    "IllegalSponsorTransitionError",
    "InMemoryCheckinEventStore",
    "InMemoryNotificationLogStore",
    "InMemoryNudgeStore",
    "InMemoryRecommitmentStore",
    "InMemorySponsorStore",
    "NotificationLogAlreadyExistsError",
    "NotificationLogStore",
    "NotificationLogStoreError",
    "NudgeAlreadyExistsError",
    "NudgeDeliveryService",
    "NudgeStore",
    "NudgeStoreError",
    "PrivacyFilter",
    "PrivacyVerdict",
    "ProjectionInput",
    "RecommitmentAlreadyAnsweredError",
    "RecommitmentRequestAlreadyExistsError",
    "RecommitmentRequestNotFoundError",
    "RecommitmentStore",
    "RecommitmentStoreError",
    "SponsorAlreadyExistsError",
    "SponsorNotFoundError",
    "SponsorReportDeliveryService",
    "SponsorReportGenerator",
    "SponsorStore",
    "SponsorStoreError",
    "ThresholdAdaptation",
    "adapt_contract_thresholds",
    "behind_schedule_percent",
    "derive_accountability_contract",
    "derive_nudge_tone_tier",
    "evaluate_accountability",
    "evaluate_checkin",
    "most_recent_due_instant",
    "project_accountability_state",
    "record_recommitment",
    "request_recommitment",
    "resolve_deliver_at",
]
