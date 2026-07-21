"""Environment wiring: every store, service, and LLM node the cycle needs.

``build_environment`` is the single place backend selection happens: pass a
``db_path`` and every persisted store is the Phase 9a SQLite twin sharing one
database file; omit it and everything is in-memory (the test default). The
cycle service is written against the protocols, so it cannot tell the
difference — which is exactly the restart-survival guarantee the dogfood
backbone needs.

LLM nodes arrive through a factory rather than as instances because the real
adapters (Phase 8) need the environment's own call-log store, clock, and id
generator; the factory inverts that dependency without letting ``app/``
construct SDK transports itself (only ``llm_nodes``/``tools`` may touch the
SDK).
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from agentic_calendar.accountability.checkin_store import (
    CheckinEventStore,
    InMemoryCheckinEventStore,
)
from agentic_calendar.accountability.notification_log_store import (
    InMemoryNotificationLogStore,
    NotificationLogStore,
)
from agentic_calendar.accountability.nudge_store import InMemoryNudgeStore, NudgeStore
from agentic_calendar.accountability.nudges import NudgeDeliveryService
from agentic_calendar.accountability.recommitment import (
    InMemoryRecommitmentStore,
    RecommitmentStore,
)
from agentic_calendar.accountability.sponsor_store import (
    InMemorySponsorStore,
    SponsorStore,
)
from agentic_calendar.accountability.sqlite_checkin_store import SqliteCheckinEventStore
from agentic_calendar.accountability.sqlite_notification_log_store import (
    SqliteNotificationLogStore,
)
from agentic_calendar.accountability.sqlite_nudge_store import SqliteNudgeStore
from agentic_calendar.accountability.sqlite_recommitment_store import (
    SqliteRecommitmentStore,
)
from agentic_calendar.accountability.sqlite_sponsor_store import SqliteSponsorStore
from agentic_calendar.approval.sqlite_store import SqliteApprovalEventStore
from agentic_calendar.approval.store import ApprovalEventStore, InMemoryApprovalEventStore
from agentic_calendar.calendar_writer.adapter import ExternalCalendarAdapter
from agentic_calendar.calendar_writer.in_memory_adapter import InMemoryCalendarAdapter
from agentic_calendar.calendar_writer.lock import CalendarWriteLockManager
from agentic_calendar.calendar_writer.manager import CalendarWriteManager
from agentic_calendar.calendar_writer.sqlite_store import SqliteCalendarEventMappingStore
from agentic_calendar.calendar_writer.store import (
    CalendarEventMappingStore,
    InMemoryCalendarEventMappingStore,
)
from agentic_calendar.common.clock import Clock, SystemClock
from agentic_calendar.common.ids import IdGenerator, UuidIdGenerator
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.consent.audit_store import (
    DataAccessAuditStore,
    InMemoryDataAccessAuditStore,
)
from agentic_calendar.consent.gate import ConsentGate
from agentic_calendar.consent.sqlite_audit_store import SqliteDataAccessAuditStore
from agentic_calendar.consent.sqlite_store import SqliteConsentStore
from agentic_calendar.consent.store import ConsentStore, InMemoryConsentStore
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.drift_event import DriftEvent
from agentic_calendar.contracts.resume_extraction import ResumeExtraction
from agentic_calendar.contracts.resume_intake_input import ResumeIntakeInput
from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.contracts.strategy_constraints import StrategyConstraints
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import Task, TaskPlan
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import ValidationResult
from agentic_calendar.disposition.disposition_store import (
    InMemoryTaskDispositionStore,
    TaskDispositionStore,
)
from agentic_calendar.disposition.sqlite_disposition_store import (
    SqliteTaskDispositionStore,
)
from agentic_calendar.drift.classifier import DriftClassifier
from agentic_calendar.identity.sqlite_store import SqliteGoogleCredentialStore
from agentic_calendar.identity.store import (
    GoogleCredentialStore,
    InMemoryGoogleCredentialStore,
)
from agentic_calendar.llm_nodes.call_log import InMemoryLlmCallLogStore, LlmCallLogStore
from agentic_calendar.llm_nodes.prose_attachment import (
    InMemoryProseAttachmentStore,
    ProseAttachmentStore,
)
from agentic_calendar.llm_nodes.reflection_summary import ReflectionSummary
from agentic_calendar.llm_nodes.sqlite_call_log import SqliteLlmCallLogStore
from agentic_calendar.llm_nodes.sqlite_prose_store import SqliteProseAttachmentStore
from agentic_calendar.llm_nodes.user_facing_explanation import (
    FitNoteRequest,
    PathwayFitNotes,
    StorySummary,
    StorySummaryRequest,
    UserExplanation,
)
from agentic_calendar.overlay import (
    InMemoryKnowledgeOverlayStore,
    KnowledgeOverlayStore,
    SqliteKnowledgeOverlayStore,
)
from agentic_calendar.planning.sqlite_store import SqlitePlanVersionStore
from agentic_calendar.planning.store import InMemoryPlanVersionStore, PlanVersionStore
from agentic_calendar.source_claims.ingestion import (
    InMemorySourceClaimStore,
    SourceClaimStore,
)
from agentic_calendar.source_claims.sqlite_store import SqliteSourceClaimStore
from agentic_calendar.telemetry.event_store import (
    InMemoryTelemetryEventStore,
    TelemetryEventStore,
)
from agentic_calendar.telemetry.ingestion import TelemetryIngestor
from agentic_calendar.telemetry.sqlite_event_store import SqliteTelemetryEventStore

from .placement_preference import (
    InMemoryPlacementPreferenceStore,
    PlacementPreferenceStore,
    SqlitePlacementPreferenceStore,
)
from .state import AppStateStore, InMemoryAppStateStore, SqliteAppStateStore
from .threshold_log import (
    InMemoryThresholdChangeLogStore,
    SqliteThresholdChangeLogStore,
    ThresholdChangeLogStore,
)
from .tuning import EffectiveTuning, apply_tuning, load_tuning_file


@runtime_checkable
class StrategistNode(Protocol):
    """Structural surface shared by ``FixtureStrategist`` and ``AnthropicStrategist``."""

    def run(
        self,
        *,
        run_id: str,
        user_profile: UserProfile,
        source_claims: Sequence[SourceClaim] = (),
        strategy_constraints: StrategyConstraints | None = None,
    ) -> SyllabusUnits: ...


@runtime_checkable
class PlannerNode(Protocol):
    """Structural surface shared by ``FixturePlanner`` and ``AnthropicPlanner``.

    ``user_profile`` carries the scheduling limits the deterministic user-fit
    checks enforce; ``repair`` is the failed ``ValidationResult`` from the
    previous pass of the bounded repair loop (axiom 04) so retries are not
    re-invoked blind. ``behavioral_hints`` are the user's recent persisted
    reflection sentences (D2) — advisory prose the replan path threads in for
    sizing/emphasis; never parsed, never control-plane.
    ``prior_plan_tasks`` + ``replan_mode`` (D4 stage 1) are the replan path's
    anchor: the active plan's surviving tasks plus the recovery mode, so the
    prompt can instruct preserve-unless-affected instead of regenerating
    blind. All are optional: deterministic plan sources ignore them.
    """

    def run(
        self,
        *,
        run_id: str,
        syllabus: SyllabusUnits,
        user_profile: UserProfile | None = None,
        repair: ValidationResult | None = None,
        excluded_tasks: Collection[str] = (),
        behavioral_hints: Sequence[str] = (),
        prior_plan_tasks: Sequence[Task] = (),
        replan_mode: RecoveryAction | None = None,
    ) -> TaskPlan: ...


@runtime_checkable
class ReflectionNode(Protocol):
    """Structural surface shared by the deterministic and Anthropic reflection nodes.

    ``prior_reflections`` are the user's last few persisted reflection
    sentences (D2) — advisory continuity context so successive notes read as
    one coaching conversation; never parsed, never control-plane."""

    def run(
        self,
        *,
        run_id: str,
        drift_events: Sequence[DriftEvent],
        completion_rate: float | None = None,
        prior_reflections: Sequence[str] = (),
    ) -> ReflectionSummary: ...


@runtime_checkable
class ExplanationNode(Protocol):
    """Structural surface shared by the deterministic and Anthropic explanation nodes.

    Beyond the validation explanation, this node carries the two story-layer
    prose targets (NP-F): batched pathway fit notes and the story summary. They
    stay *inside* this already-allowed node (03-llm-surfaces: no new LLM node
    class) — both twins implement all three methods, and the ``LlmNodeBundle``
    keeps five slots. Story prose is display-only: it decorates the
    ``narrative/`` kernel's deterministic coverage and never re-ranks it."""

    def run(
        self, *, run_id: str, validation_result: ValidationResult
    ) -> UserExplanation: ...

    def run_fit_notes(
        self, *, run_id: str, requests: tuple[FitNoteRequest, ...]
    ) -> PathwayFitNotes: ...

    def run_story_summary(
        self, *, run_id: str, request: StorySummaryRequest
    ) -> StorySummary: ...


@runtime_checkable
class ResumeIntakeNode(Protocol):
    """Structural surface shared by ``FixtureResumeIntake`` and ``AnthropicResumeIntake``.

    Persistence-free onboarding extraction (the fifth allowed node, axiom 01):
    the service mints an ``intake-``-prefixed ``run_id`` (no run exists yet)
    and fills ``intake.allowed_weak_spots`` from the skill-taxonomy kernel —
    the node itself receives the vocabulary as plain data and never imports
    the kernel (``.importlinter`` contract 18)."""

    def run(
        self, *, run_id: str, intake: ResumeIntakeInput
    ) -> ResumeExtraction: ...


@dataclass(frozen=True, slots=True)
class LlmNodeBundle:
    """The five allowed LLM nodes (axiom 01) — fixture or real, never mixed in here."""

    strategist: StrategistNode
    planner: PlannerNode
    reflection: ReflectionNode
    explanation: ExplanationNode
    resume_intake: ResumeIntakeNode


@dataclass(frozen=True, slots=True)
class NodeDependencies:
    """What a node factory may use to construct the bundle."""

    call_log_store: LlmCallLogStore
    clock: Clock
    id_generator: IdGenerator


NodesFactory = Callable[[NodeDependencies], LlmNodeBundle]


@dataclass(frozen=True, slots=True)
class AppEnvironment:
    """Everything the cycle service operates on, fully wired."""

    clock: Clock
    id_generator: IdGenerator
    db: SqliteDatabase | None
    state: AppStateStore
    plan_store: PlanVersionStore
    approval_store: ApprovalEventStore
    mapping_store: CalendarEventMappingStore
    telemetry_store: TelemetryEventStore
    disposition_store: TaskDispositionStore
    knowledge_overlay_store: KnowledgeOverlayStore
    placement_preference_store: PlacementPreferenceStore
    consent_store: ConsentStore
    audit_store: DataAccessAuditStore
    checkin_store: CheckinEventStore
    nudge_store: NudgeStore
    notification_log_store: NotificationLogStore
    recommitment_store: RecommitmentStore
    sponsor_store: SponsorStore
    call_log_store: LlmCallLogStore
    prose_store: ProseAttachmentStore
    claim_store: SourceClaimStore
    credential_store: GoogleCredentialStore
    threshold_log_store: ThresholdChangeLogStore
    tuning: EffectiveTuning
    calendar_adapter: ExternalCalendarAdapter
    lock_manager: CalendarWriteLockManager
    write_manager: CalendarWriteManager
    telemetry_ingestor: TelemetryIngestor
    drift_classifier: DriftClassifier
    consent_gate: ConsentGate
    nudge_service: NudgeDeliveryService
    nodes: LlmNodeBundle


def build_environment(
    *,
    nodes_factory: NodesFactory,
    db_path: str | Path | None = None,
    clock: Clock | None = None,
    id_generator: IdGenerator | None = None,
    calendar_adapter: ExternalCalendarAdapter | None = None,
    tuning_path: str | Path | None = None,
) -> AppEnvironment:
    """Wire one complete environment.

    ``db_path`` selects persistence: ``None`` keeps every store in-memory
    (the test default); a path opens one shared SQLite database and every
    persisted store becomes its Phase 9a twin. The default calendar adapter
    is the in-memory one — the real Google adapter (Phase 9c) is injected
    here by the operator CLI, never constructed implicitly.

    ``tuning_path`` is the only supported way to change a tuning value:
    overrides are validated against the registry and journaled to the
    threshold change log before anything serves them (axiom 07 "no silent
    threshold changes"); omitted, every config keeps its default and the
    journal is untouched.
    """
    clock = clock if clock is not None else SystemClock()
    ids = id_generator if id_generator is not None else UuidIdGenerator()

    db: SqliteDatabase | None = None
    if db_path is None:
        state: AppStateStore = InMemoryAppStateStore()
        plan_store: PlanVersionStore = InMemoryPlanVersionStore()
        approval_store: ApprovalEventStore = InMemoryApprovalEventStore()
        mapping_store: CalendarEventMappingStore = InMemoryCalendarEventMappingStore()
        telemetry_store: TelemetryEventStore = InMemoryTelemetryEventStore()
        disposition_store: TaskDispositionStore = InMemoryTaskDispositionStore()
        knowledge_overlay_store: KnowledgeOverlayStore = (
            InMemoryKnowledgeOverlayStore()
        )
        placement_preference_store: PlacementPreferenceStore = (
            InMemoryPlacementPreferenceStore()
        )
        consent_store: ConsentStore = InMemoryConsentStore(clock)
        audit_store: DataAccessAuditStore = InMemoryDataAccessAuditStore()
        checkin_store: CheckinEventStore = InMemoryCheckinEventStore()
        nudge_store: NudgeStore = InMemoryNudgeStore()
        notification_log_store: NotificationLogStore = InMemoryNotificationLogStore()
        recommitment_store: RecommitmentStore = InMemoryRecommitmentStore()
        sponsor_store: SponsorStore = InMemorySponsorStore(clock)
        call_log_store: LlmCallLogStore = InMemoryLlmCallLogStore()
        prose_store: ProseAttachmentStore = InMemoryProseAttachmentStore()
        claim_store: SourceClaimStore = InMemorySourceClaimStore()
        credential_store: GoogleCredentialStore = InMemoryGoogleCredentialStore()
        threshold_log_store: ThresholdChangeLogStore = (
            InMemoryThresholdChangeLogStore()
        )
    else:
        db = SqliteDatabase(db_path)
        state = SqliteAppStateStore(db)
        plan_store = SqlitePlanVersionStore(db)
        approval_store = SqliteApprovalEventStore(db)
        mapping_store = SqliteCalendarEventMappingStore(db)
        telemetry_store = SqliteTelemetryEventStore(db)
        disposition_store = SqliteTaskDispositionStore(db)
        knowledge_overlay_store = SqliteKnowledgeOverlayStore(db)
        placement_preference_store = SqlitePlacementPreferenceStore(db)
        consent_store = SqliteConsentStore(db, clock)
        audit_store = SqliteDataAccessAuditStore(db)
        checkin_store = SqliteCheckinEventStore(db)
        nudge_store = SqliteNudgeStore(db)
        notification_log_store = SqliteNotificationLogStore(db)
        recommitment_store = SqliteRecommitmentStore(db)
        sponsor_store = SqliteSponsorStore(db, clock)
        call_log_store = SqliteLlmCallLogStore(db)
        prose_store = SqliteProseAttachmentStore(db)
        claim_store = SqliteSourceClaimStore(db)
        credential_store = SqliteGoogleCredentialStore(db)
        threshold_log_store = SqliteThresholdChangeLogStore(db)

    tuning = apply_tuning(
        parsed=load_tuning_file(tuning_path) if tuning_path is not None else None,
        store=threshold_log_store,
        clock=clock,
        id_generator=ids,
    )

    adapter = (
        calendar_adapter
        if calendar_adapter is not None
        else InMemoryCalendarAdapter(id_generator=ids)
    )
    lock_manager = CalendarWriteLockManager(clock=clock)
    write_manager = CalendarWriteManager(
        adapter=adapter,
        mapping_store=mapping_store,
        approval_store=approval_store,
        lock_manager=lock_manager,
        id_generator=ids,
        clock=clock,
    )
    nodes = nodes_factory(
        NodeDependencies(call_log_store=call_log_store, clock=clock, id_generator=ids)
    )
    return AppEnvironment(
        clock=clock,
        id_generator=ids,
        db=db,
        state=state,
        plan_store=plan_store,
        approval_store=approval_store,
        mapping_store=mapping_store,
        telemetry_store=telemetry_store,
        disposition_store=disposition_store,
        knowledge_overlay_store=knowledge_overlay_store,
        placement_preference_store=placement_preference_store,
        consent_store=consent_store,
        audit_store=audit_store,
        checkin_store=checkin_store,
        nudge_store=nudge_store,
        notification_log_store=notification_log_store,
        recommitment_store=recommitment_store,
        sponsor_store=sponsor_store,
        call_log_store=call_log_store,
        prose_store=prose_store,
        claim_store=claim_store,
        credential_store=credential_store,
        threshold_log_store=threshold_log_store,
        tuning=tuning,
        calendar_adapter=adapter,
        lock_manager=lock_manager,
        write_manager=write_manager,
        telemetry_ingestor=TelemetryIngestor(clock=clock, store=telemetry_store),
        drift_classifier=DriftClassifier(
            clock=clock, id_generator=ids, thresholds=tuning.drift_thresholds
        ),
        consent_gate=ConsentGate(
            consent_store, audit_store, clock=clock, id_generator=ids
        ),
        nudge_service=NudgeDeliveryService(
            clock=clock, id_generator=ids, store=nudge_store
        ),
        nodes=nodes,
    )
