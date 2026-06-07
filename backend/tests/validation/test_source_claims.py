"""Tests for syllabus source-claim validation (axiom 08)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime

from agentic_calendar.contracts.common_types import Priority
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.source_claim import (
    ConfidenceBucket,
    SourceClaim,
    SourceType,
)
from agentic_calendar.contracts.syllabus_units import SyllabusModule, SyllabusUnits
from agentic_calendar.contracts.validation_result import ArtifactType, NextAction
from agentic_calendar.contracts.violation_types import ViolationType
from agentic_calendar.validation import validate_syllabus_units
from agentic_calendar.validation.source_claims import check_source_claims

NOW = datetime(2026, 6, 4, 12, 0, tzinfo=UTC)


def _claim(claim_id: str, expires_at: date) -> SourceClaim:
    return SourceClaim(
        claim_id=claim_id,
        claim_text="A verifiable claim.",
        source_url="https://x.example.com/a",
        source_type=SourceType.INTERVIEW_REPORT,
        date_collected=date(2026, 1, 1),
        confidence_score=0.6,
        confidence_bucket=ConfidenceBucket.MEDIUM,
        expires_at=expires_at,
    )


def _module(**overrides: object) -> SyllabusModule:
    base: dict[str, object] = {
        "module_id": "m1",
        "title": "Module",
        "priority": Priority.MEDIUM,
        "target_outcomes": ["outcome"],
        "estimated_total_min": 60,
        "difficulty": 3,
    }
    base.update(overrides)
    return SyllabusModule(**base)  # type: ignore[arg-type]


def _syllabus(modules: list[SyllabusModule]) -> SyllabusUnits:
    return SyllabusUnits(syllabus_version="syl_1", goal_summary="g", modules=modules)


def _check(
    syllabus: SyllabusUnits,
    registry: Mapping[str, SourceClaim],
    *,
    require_company: bool = True,
) -> list[ViolationType]:
    violations = check_source_claims(
        syllabus,
        claim_registry=registry,
        now=NOW,
        must_reference_claims_for_company_specific_modules=require_company,
    )
    return [v.type for v in violations]


def test_orphan_claim_reference() -> None:
    syl = _syllabus([_module(source_claim_ids=["missing"])])
    assert _check(syl, {}) == [ViolationType.ORPHAN_SOURCE_CLAIM]


def test_expired_claim_reference() -> None:
    registry = {"c1": _claim("c1", date(2026, 1, 1))}  # long expired by NOW
    syl = _syllabus([_module(source_claim_ids=["c1"])])
    assert _check(syl, registry) == [ViolationType.EXPIRED_SOURCE_CLAIM]


def test_live_claim_reference_ok() -> None:
    registry = {"c1": _claim("c1", date(2026, 12, 1))}  # future
    syl = _syllabus([_module(source_claim_ids=["c1"])])
    assert _check(syl, registry) == []


def test_expiry_boundary_is_inclusive() -> None:
    registry = {"c1": _claim("c1", NOW.date())}  # expires exactly today → expired
    syl = _syllabus([_module(source_claim_ids=["c1"])])
    assert _check(syl, registry) == [ViolationType.EXPIRED_SOURCE_CLAIM]


def test_company_specific_module_missing_claim() -> None:
    syl = _syllabus([_module(company_specific=True, source_claim_ids=[])])
    assert _check(syl, {}) == [ViolationType.COMPANY_MODULE_MISSING_CLAIM]


def test_company_specific_rule_off() -> None:
    syl = _syllabus([_module(company_specific=True, source_claim_ids=[])])
    assert _check(syl, {}, require_company=False) == []


def test_non_company_module_without_claims_is_fine() -> None:
    syl = _syllabus([_module(company_specific=False, source_claim_ids=[])])
    assert _check(syl, {}) == []


def test_validate_clean_syllabus_is_noop() -> None:
    registry = {"c1": _claim("c1", date(2026, 12, 1))}
    syl = _syllabus([_module(source_claim_ids=["c1"])])
    result = validate_syllabus_units(
        syl, claim_registry=registry, now=NOW, run_id="run_1"
    )
    assert result.valid
    assert result.reason_code is None
    assert result.next_action is NextAction.NOOP
    assert result.artifact_type is ArtifactType.SYLLABUS_UNITS


def test_validate_orphan_routes_to_strategist_repair() -> None:
    syl = _syllabus([_module(source_claim_ids=["missing"])])
    result = validate_syllabus_units(syl, claim_registry={}, now=NOW, run_id="run_1")
    assert not result.valid
    assert result.repairable
    assert result.reason_code is ReasonCode.SOURCE_CLAIM_VALIDATION_FAILED
    assert result.next_action is NextAction.STRATEGIST_REPAIR_RETRY


def test_validate_repair_cap_exhausted_routes_to_user() -> None:
    syl = _syllabus([_module(source_claim_ids=["missing"])])
    result = validate_syllabus_units(
        syl, claim_registry={}, now=NOW, run_id="run_1", repair_attempt=2
    )
    assert result.next_action is NextAction.ERROR_REQUIRES_USER


def test_validate_malformed_dict_returns_typed_result_not_raise() -> None:
    """A raw dict that fails the Pydantic contract must surface as a typed
    SCHEMA_INVALID result, never a leaked ValidationError (axiom 04 / 16)."""
    result = validate_syllabus_units(
        {"syllabus_version": "syl_1"},  # missing goal_summary + modules
        claim_registry={},
        now=NOW,
        run_id="run_1",
    )
    assert not result.valid
    assert result.reason_code is ReasonCode.SCHEMA_INVALID
    assert result.violations
    assert result.next_action is NextAction.STRATEGIST_REPAIR_RETRY
