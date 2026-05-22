"""Helpers that build the ``debug`` payload for ``UnscheduledTask`` records.

Centralising payload construction here means each ``reason_code`` always
ships with the same fields, which keeps tests and the (future) approval UI
happy.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.scheduler_output import RepairOption


def no_valid_contiguous_block_debug(
    *,
    required_duration_min: int,
    largest_available_block_min: int,
    required_focus_level: str,
    rejected_windows: list[dict[str, Any]],
    suggested_repair: RepairOption | None = None,
) -> dict[str, Any]:
    """Debug payload for :data:`ReasonCode.NO_VALID_CONTIGUOUS_BLOCK`."""
    payload: dict[str, Any] = {
        "required_duration_min": required_duration_min,
        "largest_available_block_min": largest_available_block_min,
        "required_focus_level": required_focus_level,
        "candidate_windows_checked": len(rejected_windows),
        "rejected_windows": rejected_windows,
    }
    if suggested_repair is not None:
        payload["suggested_repair"] = suggested_repair.value
    return payload


def task_too_long_unsplittable_debug(
    *,
    duration_min: int,
    max_session_length_min: int,
) -> dict[str, Any]:
    return {
        "duration_min": duration_min,
        "max_session_length_min": max_session_length_min,
        "suggested_repair": RepairOption.ASK_USER.value,
    }


def deep_work_required_unavailable_debug(
    *,
    required_duration_min: int,
    deep_work_windows_seen: int,
) -> dict[str, Any]:
    return {
        "required_duration_min": required_duration_min,
        "required_focus_level": "deep",
        "deep_work_windows_seen": deep_work_windows_seen,
        "suggested_repair": RepairOption.ASK_USER.value,
    }


def insufficient_weekly_capacity_debug(
    *,
    total_required_min: int,
    available_capacity_min: int,
) -> dict[str, Any]:
    return {
        "total_required_min": total_required_min,
        "available_capacity_min": available_capacity_min,
        "shortfall_min": total_required_min - available_capacity_min,
        "suggested_repair": RepairOption.EXTEND_TIMELINE.value,
    }


def dependency_blocked_debug(*, blocked_by: list[str]) -> dict[str, Any]:
    return {
        "blocked_by": blocked_by,
        "reason_code": ReasonCode.DEPENDENCY_BLOCKED.value,
    }


def rejected_window(
    *, start: datetime, duration_min: int, rejection_reason: str
) -> dict[str, Any]:
    return {
        "start": start.isoformat(),
        "duration_min": duration_min,
        "rejection_reason": rejection_reason,
    }
