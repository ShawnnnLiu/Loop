"""Pathway registry (deterministic seed layer, narrative-pathways NP-B).

The single source of truth for the curated :class:`PathwayTemplate` literals a
user can choose to build toward, plus the closed, track-scoped **theme
vocabulary** those templates draw from. Templates are canned, validated literals
- exactly like the milestone registry (``registry.py``) and the skill taxonomy
(``skill_taxonomy/``): LLM research may draft candidate content, but human review
is the curation gate (axiom 08 controlled-vocabulary wall); an LLM never
produces a template at runtime, and pathway fit over them is computed
deterministically by the ``narrative/`` kernel (axiom 00).

Registry-level invariants that the Pydantic contract cannot express - unique
``pathway_id``s, every ``required_themes_any`` member present in its track's
theme vocabulary, every ``branch_skill_ids`` member resolvable against the
pinned skill taxonomy, and no prestige terms in any text field - are enforced by
``tests/templates/test_pathway_registry.py``, mirroring
``tests/templates/test_registry.py``.

Cross-listing: a pathway has one *home* ``career_track`` (its theme-vocabulary
anchor), but may be surfaced under additional tracks via :data:`_CROSS_LISTED`
(AI-Integration Engineer is a ``swe`` role as much as an ``ai_engineer`` one).
This is a discovery convenience in :func:`pathways_for_track`; theme membership
always anchors to the home track.

This is a leaf kernel: it depends only on ``contracts/`` and ``common/``.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from agentic_calendar.contracts._dedup import casefold_key
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.common_types import EvidenceKind
from agentic_calendar.contracts.pathway_template import EvidenceSlot, PathwayTemplate

#: Shape version of the individual templates (``milestone-template`` discipline).
PATHWAY_SCHEMA_VERSION = "pathway-template-v1"

#: Version of the registry *content* as a whole. ``PathwaySelection`` pins this
#: so a later append-only bump never silently re-maps a live selection
#: (``pathway-selection.schema.md`` version-pinning discipline).
PATHWAY_REGISTRY_VERSION = "pathway-registry-v1"


# ---------------------------------------------------------------------------
# Theme vocabulary — closed, registry-owned, track-scoped (02-…/pathway-template
# spec §"Theme Vocabulary"). Broader than skills, deliberately NOT part of the
# skill taxonomy. The global vocabulary is the union of every theme any home
# pathway references for a track, plus a small pool of non-slot themes for
# tagging breadth. Target is <= ~30 themes per track (the intake-prompt slice,
# re-asserted in NP-C). Compared case-insensitively everywhere through
# ``casefold_key``; stored here in authored display case.
# ---------------------------------------------------------------------------
_THEME_VOCABULARY: Mapping[CareerTrack, tuple[str, ...]] = MappingProxyType(
    {
        CareerTrack.SWE: (
            "backend-systems",
            "distributed-systems",
            "data-layer",
            "production-ops",
            "system-reliability",
            "api-design",
            "developer-experience",
            "frontend-ux",
            "full-stack",
            "product-engineering",
            "technical-writing",
            "open-source",
        ),
        CareerTrack.MLE: (
            "applied-ml",
            "model-development",
            "ml-deployment",
            "mlops",
            "data-engineering",
            "experimentation",
            "research",
            "technical-writing",
        ),
        CareerTrack.AI_ENGINEER: (
            "applied-ml",
            "llm-integration",
            "llm-orchestration",
            "retrieval",
            "evaluation",
            "production-ops",
            "developer-experience",
            "technical-writing",
        ),
    }
)


# ---------------------------------------------------------------------------
# Seed pathways. Content is a curation prior, revisable in review; slot counts
# follow the 4-6 guideline. Every ``branch_skill_ids`` member is a real
# ``skill_id`` in the pinned taxonomy (enforced by the registry test).
# ---------------------------------------------------------------------------

_BACKEND_INFRASTRUCTURE = PathwayTemplate(
    pathway_id="backend-infrastructure-engineer",
    pathway_schema_version=PATHWAY_SCHEMA_VERSION,
    career_track=CareerTrack.SWE,
    display_name="Backend & Infrastructure",
    spine="Builds reliable backend services and the infrastructure that keeps them running.",
    audience_note="Platform and backend teams; infrastructure-heavy product companies.",
    evidence_slots=[
        EvidenceSlot(
            slot_id="service-depth",
            title="Backend service built end to end",
            required_kinds=[EvidenceKind.WORK, EvidenceKind.PROJECT],
            required_themes_any=["backend-systems", "distributed-systems"],
            gap_module_hint="Design and ship one backend service with a clear API boundary",
            branch_skill_ids=["skill.system-design", "skill.api-design", "skill.microservices"],
        ),
        EvidenceSlot(
            slot_id="data-layer",
            title="Data layer you designed",
            required_kinds=[EvidenceKind.WORK, EvidenceKind.PROJECT],
            required_themes_any=["data-layer"],
            gap_module_hint="Model and optimize a persistent data layer",
            branch_skill_ids=["skill.database-design", "skill.postgresql", "skill.caching"],
        ),
        EvidenceSlot(
            slot_id="production-ops",
            title="Ran it in production",
            required_kinds=[EvidenceKind.WORK, EvidenceKind.PROJECT],
            required_themes_any=["production-ops", "system-reliability"],
            gap_module_hint="Take one service to production with monitoring and CI/CD",
            branch_skill_ids=["skill.docker", "skill.kubernetes", "skill.observability", "skill.ci-cd"],
        ),
        EvidenceSlot(
            slot_id="public-artifact",
            title="Public writeup or open-source work",
            required_kinds=[EvidenceKind.PROJECT, EvidenceKind.RESEARCH],
            required_themes_any=["technical-writing", "open-source"],
            gap_module_hint="Publish one project writeup or open-source contribution",
            branch_skill_ids=["skill.git", "skill.code-review", "skill.testing"],
        ),
    ],
)


_FULL_STACK_PRODUCT = PathwayTemplate(
    pathway_id="full-stack-product-engineer",
    pathway_schema_version=PATHWAY_SCHEMA_VERSION,
    career_track=CareerTrack.SWE,
    display_name="Full-Stack Product Engineer",
    spine="Ships complete product features from database to interface.",
    audience_note="Product-focused teams and startups where engineers own features end to end.",
    evidence_slots=[
        EvidenceSlot(
            slot_id="frontend-surface",
            title="Frontend you built",
            required_kinds=[EvidenceKind.WORK, EvidenceKind.PROJECT],
            required_themes_any=["frontend-ux"],
            gap_module_hint="Build one polished frontend surface",
            branch_skill_ids=["skill.react", "skill.typescript", "skill.html-css"],
        ),
        EvidenceSlot(
            slot_id="backend-depth",
            title="Backend behind the product",
            required_kinds=[EvidenceKind.WORK, EvidenceKind.PROJECT],
            required_themes_any=["backend-systems", "api-design"],
            gap_module_hint="Own the backend and API for a product feature",
            branch_skill_ids=["skill.fastapi", "skill.rest-apis", "skill.postgresql"],
        ),
        EvidenceSlot(
            slot_id="shipped-product",
            title="Product shipped to users",
            required_kinds=[EvidenceKind.WORK, EvidenceKind.PROJECT],
            required_themes_any=["product-engineering", "full-stack"],
            gap_module_hint="Ship one full-stack feature to real users",
            branch_skill_ids=["skill.system-design", "skill.testing", "skill.ci-cd"],
        ),
        EvidenceSlot(
            slot_id="user-facing-polish",
            title="User-facing polish or writeup",
            required_kinds=[EvidenceKind.PROJECT, EvidenceKind.RESEARCH],
            required_themes_any=["technical-writing", "developer-experience"],
            gap_module_hint="Document or demo one shipped feature",
            branch_skill_ids=["skill.git", "skill.code-review"],
        ),
    ],
)


_AI_INTEGRATION = PathwayTemplate(
    pathway_id="ai-integration-engineer",
    pathway_schema_version=PATHWAY_SCHEMA_VERSION,
    career_track=CareerTrack.AI_ENGINEER,
    display_name="AI-Integration Engineer",
    spine="Ships LLM-powered features into real products, end to end.",
    audience_note="Product teams adding AI capabilities; applied-AI startups.",
    evidence_slots=[
        EvidenceSlot(
            slot_id="llm-feature-depth",
            title="LLM feature shipped in a real app",
            required_kinds=[EvidenceKind.PROJECT, EvidenceKind.WORK],
            required_themes_any=["applied-ml", "llm-integration"],
            gap_module_hint="Build and deploy one LLM-backed feature end to end",
            branch_skill_ids=["skill.llms", "skill.rag", "skill.prompt-engineering"],
        ),
        EvidenceSlot(
            slot_id="integration-breadth",
            title="Integration and tooling breadth",
            required_kinds=[EvidenceKind.WORK, EvidenceKind.PROJECT],
            required_themes_any=["llm-orchestration", "developer-experience"],
            gap_module_hint="Wire an LLM into real tools and workflows",
            branch_skill_ids=["skill.langchain", "skill.function-calling", "skill.structured-outputs"],
        ),
        EvidenceSlot(
            slot_id="eval-telemetry",
            title="Evaluation and telemetry literacy",
            required_kinds=[EvidenceKind.WORK, EvidenceKind.PROJECT],
            required_themes_any=["evaluation", "production-ops"],
            gap_module_hint="Add evals and telemetry to an AI feature",
            branch_skill_ids=["skill.llm-evaluation", "skill.llm-observability", "skill.guardrails"],
        ),
        EvidenceSlot(
            slot_id="public-artifact",
            title="Public writeup or talk",
            required_kinds=[EvidenceKind.PROJECT, EvidenceKind.RESEARCH],
            required_themes_any=["technical-writing"],
            gap_module_hint="Write up one AI project as a technical narrative",
            branch_skill_ids=["skill.rag", "skill.prompt-engineering"],
        ),
    ],
)


_APPLIED_ML_SPECIALIST = PathwayTemplate(
    pathway_id="applied-ml-specialist",
    pathway_schema_version=PATHWAY_SCHEMA_VERSION,
    career_track=CareerTrack.MLE,
    display_name="Applied ML Specialist",
    spine="Builds and ships machine-learning models that solve real problems.",
    audience_note="ML teams shipping models into products; data-driven companies.",
    evidence_slots=[
        EvidenceSlot(
            slot_id="modeling-depth-core",
            title="Core modeling project",
            required_kinds=[EvidenceKind.PROJECT, EvidenceKind.WORK],
            required_themes_any=["model-development", "applied-ml"],
            gap_module_hint="Build and evaluate one supervised ML model end to end",
            branch_skill_ids=[
                "skill.scikit-learn",
                "skill.xgboost",
                "skill.feature-engineering",
                "skill.model-evaluation",
            ],
        ),
        EvidenceSlot(
            slot_id="modeling-depth-advanced",
            title="Deep-learning or specialized modeling",
            required_kinds=[EvidenceKind.PROJECT, EvidenceKind.WORK, EvidenceKind.RESEARCH],
            required_themes_any=["model-development", "research"],
            gap_module_hint="Train one deep-learning model for a real task",
            branch_skill_ids=["skill.pytorch", "skill.deep-learning", "skill.transformers"],
        ),
        EvidenceSlot(
            slot_id="deployment-evidence",
            title="Model deployed",
            required_kinds=[EvidenceKind.WORK, EvidenceKind.PROJECT],
            required_themes_any=["ml-deployment", "mlops"],
            gap_module_hint="Deploy one model with tracking and serving",
            branch_skill_ids=["skill.model-deployment", "skill.mlflow", "skill.docker"],
        ),
        EvidenceSlot(
            slot_id="data-engineering-breadth",
            title="Data pipeline you built",
            required_kinds=[EvidenceKind.WORK, EvidenceKind.PROJECT],
            required_themes_any=["data-engineering"],
            gap_module_hint="Build one data pipeline feeding a model",
            branch_skill_ids=["skill.spark", "skill.airflow", "skill.data-pipelines"],
        ),
        EvidenceSlot(
            slot_id="writeup",
            title="Technical writeup",
            required_kinds=[EvidenceKind.PROJECT, EvidenceKind.RESEARCH],
            required_themes_any=["technical-writing", "experimentation"],
            gap_module_hint="Write up one modeling project with results",
            branch_skill_ids=["skill.experiment-tracking", "skill.model-evaluation"],
        ),
    ],
)


_LLM_SYSTEMS = PathwayTemplate(
    pathway_id="llm-systems-engineer",
    pathway_schema_version=PATHWAY_SCHEMA_VERSION,
    career_track=CareerTrack.AI_ENGINEER,
    display_name="LLM Systems Engineer",
    spine="Builds production LLM systems: orchestration, retrieval, evaluation, and cost control.",
    audience_note="Teams operating LLM systems at scale; infrastructure-focused AI roles.",
    evidence_slots=[
        EvidenceSlot(
            slot_id="orchestration-eval-depth",
            title="Orchestration and evaluation depth",
            required_kinds=[EvidenceKind.WORK, EvidenceKind.PROJECT],
            required_themes_any=["llm-orchestration", "evaluation"],
            gap_module_hint="Build one orchestrated LLM workflow with evals",
            branch_skill_ids=["skill.ai-agents", "skill.llm-evaluation", "skill.function-calling"],
        ),
        EvidenceSlot(
            slot_id="retrieval-project",
            title="Retrieval system you built",
            required_kinds=[EvidenceKind.PROJECT, EvidenceKind.WORK],
            required_themes_any=["retrieval"],
            gap_module_hint="Build one retrieval-augmented system end to end",
            branch_skill_ids=[
                "skill.rag",
                "skill.embeddings",
                "skill.vector-databases",
                "skill.semantic-search",
            ],
        ),
        EvidenceSlot(
            slot_id="cost-latency-evidence",
            title="Cost and latency optimization",
            required_kinds=[EvidenceKind.WORK, EvidenceKind.PROJECT],
            required_themes_any=["production-ops"],
            gap_module_hint="Optimize one LLM system for cost and latency",
            branch_skill_ids=["skill.inference-optimization", "skill.vllm", "skill.llm-observability"],
        ),
        EvidenceSlot(
            slot_id="public-artifact",
            title="Public writeup or talk",
            required_kinds=[EvidenceKind.PROJECT, EvidenceKind.RESEARCH],
            required_themes_any=["technical-writing"],
            gap_module_hint="Write up one LLM systems project",
            branch_skill_ids=["skill.rag", "skill.llm-evaluation"],
        ),
    ],
)


#: Single source of truth, keyed by ``pathway_id`` in registry (declaration)
#: order. ``pathway_id`` uniqueness is enforced structurally by this mapping and
#: asserted by the registry completeness test.
_PATHWAYS: Mapping[str, PathwayTemplate] = MappingProxyType(
    {
        p.pathway_id: p
        for p in (
            _BACKEND_INFRASTRUCTURE,
            _FULL_STACK_PRODUCT,
            _AI_INTEGRATION,
            _APPLIED_ML_SPECIALIST,
            _LLM_SYSTEMS,
        )
    }
)


#: Extra tracks a pathway is surfaced under beyond its home ``career_track``.
#: AI-Integration Engineer is an ``ai_engineer`` pathway by home (its theme
#: vocabulary anchor) but is equally a ``swe`` role, so it also appears on the
#: ``swe`` card list. Theme membership always anchors to the home track.
_CROSS_LISTED: Mapping[str, tuple[CareerTrack, ...]] = MappingProxyType(
    {
        "ai-integration-engineer": (CareerTrack.SWE,),
    }
)


def get_pathway(pathway_id: str) -> PathwayTemplate | None:
    """Return the registered template for ``pathway_id``, or ``None``.

    ``None`` on an unknown id, mirroring ``select_template_for_profile``'s honest
    fall-through: the service layer maps that to ``UNKNOWN_PATHWAY_ID`` rather
    than the registry guessing.
    """
    return _PATHWAYS.get(pathway_id)


def list_pathways() -> tuple[PathwayTemplate, ...]:
    """Return every registered pathway in declaration order."""
    return tuple(_PATHWAYS.values())


def pathways_for_track(track: CareerTrack) -> tuple[PathwayTemplate, ...]:
    """Return the pathways offered for ``track``, in registry order.

    A pathway is offered for its home ``career_track`` and for any track it is
    cross-listed into (:data:`_CROSS_LISTED`).
    """
    return tuple(
        p
        for p in _PATHWAYS.values()
        if p.career_track is track or track in _CROSS_LISTED.get(p.pathway_id, ())
    )


def theme_vocabulary(track: CareerTrack) -> tuple[str, ...]:
    """Return the closed theme vocabulary for ``track`` (empty if none seeded).

    Themes are stored in authored display case; callers compare through
    ``contracts._dedup.casefold_key``. :func:`is_theme_in_vocabulary` applies
    that comparison.
    """
    return _THEME_VOCABULARY.get(track, ())


def is_theme_in_vocabulary(track: CareerTrack, theme: str) -> bool:
    """Whether ``theme`` is in ``track``'s vocabulary, compared case-insensitively."""
    key = casefold_key(theme)
    return any(casefold_key(t) == key for t in _THEME_VOCABULARY.get(track, ()))
