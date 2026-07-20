"""Tests for the six ``knowledge_map_overlay`` record contracts (KT-A)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import BaseModel, ValidationError

from agentic_calendar.contracts.knowledge_map_overlay import (
    CustomGroup,
    CustomNode,
    MasteryGrant,
    MasterySetPoint,
    NodeAddition,
    NodeNote,
)
from tests._fixture_loader import iter_invalid, iter_valid

# Each overlay record type is exported and fixtured under its schema key.
RECORDS: dict[str, type[BaseModel]] = {
    "knowledge_node_addition": NodeAddition,
    "knowledge_custom_group": CustomGroup,
    "knowledge_custom_node": CustomNode,
    "knowledge_node_note": NodeNote,
    "knowledge_mastery_grant": MasteryGrant,
    "knowledge_mastery_setpoint": MasterySetPoint,
}

_VALID = [
    (contract, model, fx)
    for contract, model in RECORDS.items()
    for fx in iter_valid(contract)
]
_INVALID = [
    (contract, model, fx)
    for contract, model in RECORDS.items()
    for fx in iter_invalid(contract)
]

AWARE = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
NAIVE = datetime(2026, 7, 20, 12, 0)


@pytest.mark.parametrize(
    "contract,model,fixture", _VALID, ids=lambda v: getattr(v, "name", str(v))
)
def test_valid_fixture_parses(
    contract: str, model: type[BaseModel], fixture: object
) -> None:
    model.model_validate(fixture.payload)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "contract,model,fixture", _INVALID, ids=lambda v: getattr(v, "name", str(v))
)
def test_invalid_fixture_rejected(
    contract: str, model: type[BaseModel], fixture: object
) -> None:
    payload = fixture.payload  # type: ignore[attr-defined]
    expected = fixture.expected  # type: ignore[attr-defined]
    with pytest.raises(ValidationError) as exc_info:
        model.model_validate(payload)
    msg = str(exc_info.value)
    for substr in expected["error_substrings"]:
        assert substr in msg, f"expected substring {substr!r} not in:\n{msg}"


def test_mastery_grant_rejects_custom_node() -> None:
    """A grant has no meaning on a personal node - the ``kcn-`` id is rejected
    at parse time (this is what makes 'grant-on-custom-node' a shape error)."""
    with pytest.raises(ValidationError):
        MasteryGrant(
            user_id="u1",
            node_id="kcn-mine",  # type: ignore[arg-type]
            credit_minutes=60,
            source="onboarding",  # type: ignore[arg-type]
            created_at=AWARE,
        )


def test_mastery_grant_accepts_generated_node() -> None:
    grant = MasteryGrant(
        user_id="u1",
        node_id="kn-rag",  # type: ignore[arg-type]
        credit_minutes=60,
        source="onboarding",  # type: ignore[arg-type]
        created_at=AWARE,
    )
    assert grant.credit_minutes == 60


def test_set_point_accepts_generated_and_custom_nodes() -> None:
    for node_id in ("kn-rag", "kcn-mine"):
        sp = MasterySetPoint(
            user_id="u1",
            node_id=node_id,  # type: ignore[arg-type]
            target_tier="honed",  # type: ignore[arg-type]
            created_at=AWARE,
        )
        assert sp.node_id == node_id


def test_note_accepts_generated_and_custom_nodes() -> None:
    for node_id in ("kn-rag", "kcn-mine"):
        note = NodeNote(
            user_id="u1",
            node_id=node_id,  # type: ignore[arg-type]
            text="t",
            created_at=AWARE,
            updated_at=AWARE,
        )
        assert note.node_id == node_id


def test_custom_node_accepts_generated_or_custom_group() -> None:
    for group_id in ("kg-foundations", "kcg-mine"):
        node = CustomNode(
            user_id="u1",
            custom_node_id="kcn-mine",  # type: ignore[arg-type]
            name="n",
            group_id=group_id,  # type: ignore[arg-type]
            created_at=AWARE,
        )
        assert node.group_id == group_id


@pytest.mark.parametrize("model", list(RECORDS.values()))
def test_timestamps_must_be_aware(model: type[BaseModel]) -> None:
    payload = {
        NodeAddition: {"user_id": "u1", "skill_id": "skill.rag", "created_at": NAIVE},
        CustomGroup: {
            "user_id": "u1",
            "custom_group_id": "kcg-a",
            "name": "n",
            "created_at": NAIVE,
        },
        CustomNode: {
            "user_id": "u1",
            "custom_node_id": "kcn-a",
            "name": "n",
            "group_id": "kg-a",
            "created_at": NAIVE,
        },
        NodeNote: {
            "user_id": "u1",
            "node_id": "kn-rag",
            "text": "t",
            "created_at": NAIVE,
            "updated_at": AWARE,
        },
        MasteryGrant: {
            "user_id": "u1",
            "node_id": "kn-rag",
            "credit_minutes": 60,
            "source": "onboarding",
            "created_at": NAIVE,
        },
        MasterySetPoint: {
            "user_id": "u1",
            "node_id": "kn-rag",
            "target_tier": "honed",
            "created_at": NAIVE,
        },
    }[model]
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("model", list(RECORDS.values()))
def test_records_forbid_extra_fields(model: type[BaseModel]) -> None:
    assert model.model_config.get("extra") == "forbid"
    assert model.model_config.get("frozen") is True
