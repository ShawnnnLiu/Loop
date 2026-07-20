"""Deterministic slot-coverage assignment (narrative-pathways NP-B)."""

from __future__ import annotations

from agentic_calendar.contracts.common_types import EvidenceKind
from agentic_calendar.narrative import SlotState, slot_coverage

from ._helpers import item, make_profile, make_template, selection


def _state(coverage: tuple, slot_id: str) -> SlotState:
    return next(c.state for c in coverage if c.slot_id == slot_id)


def _indices(coverage: tuple, slot_id: str) -> tuple[int, ...]:
    return next(c.matched_item_indices for c in coverage if c.slot_id == slot_id)


def test_empty_experience_is_all_empty() -> None:
    coverage = slot_coverage(make_profile([]), make_template())
    assert [c.slot_id for c in coverage] == ["s1", "s2", "s3"]
    assert all(c.state is SlotState.EMPTY for c in coverage)
    assert all(c.matched_item_indices == () for c in coverage)


def test_item_lands_in_first_matching_slot_by_registry_order() -> None:
    # A project tagged 'alpha' matches both s1 and s2; s1 is earlier, so it wins,
    # and one item fills only that one slot.
    coverage = slot_coverage(
        make_profile([item("Thing", EvidenceKind.PROJECT, ["alpha"])]),
        make_template(),
    )
    assert _state(coverage, "s1") is SlotState.FILLED
    assert _indices(coverage, "s1") == (0,)
    assert _state(coverage, "s2") is SlotState.EMPTY
    assert _indices(coverage, "s2") == ()


def test_matched_indices_preserve_item_order() -> None:
    coverage = slot_coverage(
        make_profile(
            [
                item("First", EvidenceKind.WORK, ["alpha"]),
                item("Second", EvidenceKind.PROJECT, ["alpha"]),
            ]
        ),
        make_template(),
    )
    assert _indices(coverage, "s1") == (0, 1)
    assert _state(coverage, "s1") is SlotState.FILLED


def test_min_items_partial_then_filled() -> None:
    template = make_template()  # s3 needs two work+gamma items
    one = slot_coverage(make_profile([item("A", EvidenceKind.WORK, ["gamma"])]), template)
    assert _state(one, "s3") is SlotState.PARTIAL

    two = slot_coverage(
        make_profile(
            [
                item("A", EvidenceKind.WORK, ["gamma"]),
                item("B", EvidenceKind.WORK, ["gamma"]),
            ]
        ),
        template,
    )
    assert _state(two, "s3") is SlotState.FILLED
    assert _indices(two, "s3") == (0, 1)


def test_kind_mismatch_does_not_match() -> None:
    # 'volunteering' is in no slot's required_kinds even though the theme matches.
    coverage = slot_coverage(
        make_profile([item("V", EvidenceKind.VOLUNTEERING, ["alpha"])]),
        make_template(),
    )
    assert all(c.state is SlotState.EMPTY for c in coverage)


def test_theme_join_is_case_insensitive() -> None:
    # Item tag authored in a different case than the slot's required theme.
    coverage = slot_coverage(
        make_profile([item("Thing", EvidenceKind.PROJECT, ["ALPHA"])]),
        make_template(),
    )
    assert _state(coverage, "s1") is SlotState.FILLED


def test_override_wins_over_greedy_default() -> None:
    profile = make_profile(
        [item("Thing", EvidenceKind.PROJECT, ["alpha"], organization="Org")],
        selection([{"item_title": "Thing", "item_organization": "Org", "slot_id": "s2"}]),
    )
    coverage = slot_coverage(profile, make_template())
    # Default would be s1; the override forces s2.
    assert _state(coverage, "s1") is SlotState.EMPTY
    assert _state(coverage, "s2") is SlotState.FILLED
    assert _indices(coverage, "s2") == (0,)


def test_override_matches_item_identity_case_insensitively() -> None:
    profile = make_profile(
        [item("Thing", EvidenceKind.PROJECT, ["alpha"], organization="Org")],
        selection([{"item_title": "thing", "item_organization": "ORG", "slot_id": "s2"}]),
    )
    coverage = slot_coverage(profile, make_template())
    assert _state(coverage, "s2") is SlotState.FILLED


def test_override_forces_slot_even_without_theme_or_kind_match() -> None:
    # A work item tagged only 'zeta' matches no slot by default, but the user's
    # explicit override still assigns it - the override is the correction.
    profile = make_profile(
        [item("Odd", EvidenceKind.WORK, ["zeta"], organization="Org")],
        selection([{"item_title": "Odd", "item_organization": "Org", "slot_id": "s2"}]),
    )
    coverage = slot_coverage(profile, make_template())
    assert _state(coverage, "s2") is SlotState.FILLED
    assert _indices(coverage, "s2") == (0,)


def test_override_ignored_when_selection_targets_a_different_pathway() -> None:
    # Selection is for 'other-pathway'; computing coverage for the test template
    # (e.g. ranking cards) must not pick up its overrides.
    profile = make_profile(
        [item("Thing", EvidenceKind.PROJECT, ["alpha"], organization="Org")],
        selection(
            [{"item_title": "Thing", "item_organization": "Org", "slot_id": "s2"}],
            pathway_id="other-pathway",
        ),
    )
    coverage = slot_coverage(profile, make_template())
    assert _state(coverage, "s1") is SlotState.FILLED  # greedy default, override skipped
    assert _state(coverage, "s2") is SlotState.EMPTY


def test_override_to_unknown_slot_is_ignored_and_kernel_stays_total() -> None:
    # An override naming a slot the template lacks (a service-layer invalid input)
    # must not crash the kernel; the item falls back to greedy assignment.
    profile = make_profile(
        [item("Thing", EvidenceKind.PROJECT, ["alpha"], organization="Org")],
        selection([{"item_title": "Thing", "item_organization": "Org", "slot_id": "nope"}]),
    )
    coverage = slot_coverage(profile, make_template())
    assert _state(coverage, "s1") is SlotState.FILLED


def test_slot_coverage_is_deterministic() -> None:
    profile = make_profile([item("Thing", EvidenceKind.PROJECT, ["alpha"])])
    template = make_template()
    assert slot_coverage(profile, template) == slot_coverage(profile, template)
