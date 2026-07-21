"""Narrative-pathway slot-linkage checks for a syllabus (NP-D).

Validates that a ``SyllabusUnits`` proposal links its modules to evidence slots
honestly:

* a module carrying ``evidence_slot_id`` is only allowed when a pathway is
  selected (``PATHWAY_NOT_SELECTED``);
* every ``evidence_slot_id`` names a real slot of the *selected* pathway
  (``UNKNOWN_EVIDENCE_SLOT``);
* no more modules link to slots than ``strategy_constraints.max_slot_modules``
  allows (``SLOT_MODULE_LIMIT_EXCEEDED``).

These three checks need external state the contract cannot see - the selected
:class:`PathwayTemplate` (its slot ids) and the ``max_slot_modules`` bound - so
they live in the validation layer rather than on the ``SyllabusModule`` model.
The one slot rule checkable without external state (a slot-linked module must
carry a non-empty ``reason``) is enforced at parse time on ``SyllabusModule``.

Pure function returning a list of ``Violation`` records; never mutates inputs
(axiom 04). Imports ``contracts/`` only.
"""

from __future__ import annotations

from collections.abc import Collection

from agentic_calendar.contracts.pathway_template import PathwayTemplate
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.validation_result import Violation
from agentic_calendar.contracts.violation_types import ViolationType

from .base import make_violation


def check_pathway_slots(
    syllabus: SyllabusUnits,
    *,
    selected_pathway: PathwayTemplate | None,
    max_slot_modules: int,
) -> list[Violation]:
    """Return slot-linkage violations for ``syllabus``.

    ``selected_pathway`` is the template the profile's ``pathway_selection``
    resolves to against the pinned registry version, or ``None`` when no
    pathway is selected (or the selection could not be resolved). The composition
    root supplies both this and ``max_slot_modules`` from the same
    ``StrategyConstraints`` it hands the Strategist, so the gate disposes exactly
    what the prompt was told to respect.
    """
    slot_ids = (
        frozenset(slot.slot_id for slot in selected_pathway.evidence_slots)
        if selected_pathway is not None
        else frozenset()
    )
    violations: list[Violation] = []
    linked_count = 0
    for module in syllabus.modules:
        slot_id = module.evidence_slot_id
        if slot_id is None:
            continue
        linked_count += 1
        if selected_pathway is None:
            violations.append(
                make_violation(
                    ViolationType.PATHWAY_NOT_SELECTED,
                    module_id=module.module_id,
                    evidence_slot_id=slot_id,
                )
            )
        elif slot_id not in slot_ids:
            violations.append(
                make_violation(
                    ViolationType.UNKNOWN_EVIDENCE_SLOT,
                    module_id=module.module_id,
                    evidence_slot_id=slot_id,
                    pathway_id=selected_pathway.pathway_id,
                )
            )

    if linked_count > max_slot_modules:
        violations.append(
            make_violation(
                ViolationType.SLOT_MODULE_LIMIT_EXCEEDED,
                slot_linked_module_count=linked_count,
                max_slot_modules=max_slot_modules,
            )
        )

    return violations


def check_knowledge_node_tags(
    syllabus: SyllabusUnits,
    *,
    knowledge_node_ids: Collection[str],
) -> list[Violation]:
    """Return ``UNKNOWN_KNOWLEDGE_NODE`` violations for out-of-vocabulary tags.

    A module tags the skills it trains via ``knowledge_node_ids``
    (``syllabus-units.schema.md``). Every tag must name a node in the account's
    knowledge-map vocabulary - exactly the ``StrategyConstraints.knowledge_nodes``
    the composition root handed the Strategist (KT-C), so the gate disposes what
    the prompt was told to respect. With no pathway selected the vocabulary is
    empty and any tag is rejected; untagged modules are always valid (a general
    module trains no specific node).
    """
    allowed = frozenset(knowledge_node_ids)
    violations: list[Violation] = []
    for module in syllabus.modules:
        for node_id in module.knowledge_node_ids:
            if node_id not in allowed:
                violations.append(
                    make_violation(
                        ViolationType.UNKNOWN_KNOWLEDGE_NODE,
                        module_id=module.module_id,
                        knowledge_node_id=node_id,
                    )
                )
    return violations


def check_mastery_review(
    syllabus: SyllabusUnits,
    *,
    mastered_node_ids: Collection[str],
    review_node_ids: Collection[str],
    max_review_modules: int,
    max_review_minutes: int,
) -> list[Violation]:
    """Return mastery-review-bound violations for ``syllabus`` (MM-C).

    The deterministic output gate for the ``StrategyConstraints`` mastery slice
    (``08-mastery-memory.md``). A module whose ``knowledge_node_ids`` are
    *non-empty and all* mastered or review-flagged is a **review module**: old
    skills the user has, revisited briefly, not re-studied at full length. Two
    bounds hold:

    * each review module's ``estimated_total_min`` must be
      ``<= max_review_minutes`` → else ``MASTERY_REVIEW_BOUND_EXCEEDED``;
    * the count of review modules must be ``<= max_review_modules`` → else
      ``REVIEW_MODULE_LIMIT_EXCEEDED``.

    A **mixed** module (any tag outside the mastered/review sets) is legitimate
    and unbounded - new work naturally touches old skills. An **untagged** module
    is never a review module (the mastery instruction is advisory; only
    all-mastered modules are review-bounded). With both sets empty (no mastery
    data) nothing is a review module, so this is inert - today's behavior.

    ``mastered_node_ids`` / ``review_node_ids`` / the bounds come from the same
    ``StrategyConstraints`` the composition root handed the Strategist, so the
    gate disposes exactly what the prompt was told to respect.
    """
    review_targets = frozenset(mastered_node_ids) | frozenset(review_node_ids)
    violations: list[Violation] = []
    review_module_count = 0
    for module in syllabus.modules:
        tags = module.knowledge_node_ids
        if not tags or not all(node_id in review_targets for node_id in tags):
            continue
        review_module_count += 1
        if module.estimated_total_min > max_review_minutes:
            violations.append(
                make_violation(
                    ViolationType.MASTERY_REVIEW_BOUND_EXCEEDED,
                    module_id=module.module_id,
                    estimated_total_min=module.estimated_total_min,
                    max_review_minutes=max_review_minutes,
                )
            )

    if review_module_count > max_review_modules:
        violations.append(
            make_violation(
                ViolationType.REVIEW_MODULE_LIMIT_EXCEEDED,
                review_module_count=review_module_count,
                max_review_modules=max_review_modules,
            )
        )

    return violations
