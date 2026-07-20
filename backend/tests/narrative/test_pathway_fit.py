"""Deterministic pathway fit - slot counts, never scores (NP-B)."""

from __future__ import annotations

from agentic_calendar.contracts.common_types import EvidenceKind
from agentic_calendar.narrative import pathway_fit
from agentic_calendar.templates import get_pathway

from ._helpers import item, make_profile, make_template


def test_fit_counts_filled_slots_out_of_total() -> None:
    profile = make_profile(
        [
            item("A", EvidenceKind.PROJECT, ["alpha"]),  # fills s1
            item("B", EvidenceKind.WORK, ["gamma"]),  # s3 needs 2 -> partial, not filled
        ]
    )
    fit = pathway_fit(profile, make_template())
    assert fit.pathway_id == "test-pathway"
    assert fit.filled_slots == 1
    assert fit.total_slots == 3


def test_empty_profile_fits_nothing() -> None:
    fit = pathway_fit(make_profile([]), make_template())
    assert fit.filled_slots == 0
    assert fit.total_slots == 3


def test_fit_orders_pathways_by_filled_count() -> None:
    # A profile with one applied-ml LLM project fits AI-Integration above a
    # backend pathway it shares nothing with - purely by filled-slot count.
    ai = get_pathway("ai-integration-engineer")
    backend = get_pathway("backend-infrastructure-engineer")
    assert ai is not None and backend is not None
    profile = make_profile([item("Chatbot", EvidenceKind.PROJECT, ["applied-ml"])])

    ranked = sorted(
        (pathway_fit(profile, ai), pathway_fit(profile, backend)),
        key=lambda f: f.filled_slots,
        reverse=True,
    )
    assert ranked[0].pathway_id == "ai-integration-engineer"
    assert ranked[0].filled_slots == 1
    assert ranked[1].filled_slots == 0


def test_fit_carries_no_score_fields() -> None:
    fit = pathway_fit(make_profile([]), make_template())
    assert set(fit.model_dump().keys()) == {"pathway_id", "filled_slots", "total_slots"}
