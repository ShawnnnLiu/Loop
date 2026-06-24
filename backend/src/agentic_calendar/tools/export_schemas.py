"""Export every Pydantic contract to JSON Schema.

Output goes to ``<repo>/schemas/<contract>.schema.json`` by default. The
generated files are committed so that the (future) frontend has a single
source of truth and so schema drift is reviewable in PRs.

Usage::

    uv run python -m agentic_calendar.tools.export_schemas --out ../schemas
    uv run agentic-calendar-export-schemas --out ../schemas

The CLI is deterministic: the same models produce byte-identical JSON.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agentic_calendar.cache.keys import CacheKey
from agentic_calendar.cache.store import CacheEntry
from agentic_calendar.contracts.accountability_contract import AccountabilityContract
from agentic_calendar.contracts.accountability_intervention import InterventionDecision
from agentic_calendar.contracts.accountability_state import AccountabilityState
from agentic_calendar.contracts.approval_event import ApprovalEvent
from agentic_calendar.contracts.calendar_event_mapping import CalendarEventMapping
from agentic_calendar.contracts.calendar_reconciliation import (
    CalendarReconciliationResult,
)
from agentic_calendar.contracts.checkin_event import CheckinEvent
from agentic_calendar.contracts.company_target import CompanyTarget
from agentic_calendar.contracts.consent_record import ConsentRecord
from agentic_calendar.contracts.data_access_audit import DataAccessAuditEntry
from agentic_calendar.contracts.draft_schedule import DraftSchedule
from agentic_calendar.contracts.drift_event import DriftEvent
from agentic_calendar.contracts.milestone_template import MilestoneTemplate
from agentic_calendar.contracts.motivation_profile import MotivationProfile
from agentic_calendar.contracts.notification_log import NotificationLog
from agentic_calendar.contracts.nudge import NudgeRecord
from agentic_calendar.contracts.plan_diff import PlanDiff
from agentic_calendar.contracts.pooled_duration_model import PooledDurationModel
from agentic_calendar.contracts.power_user import (
    PerUserRefinement,
    PowerUserEligibility,
)
from agentic_calendar.contracts.recommitment import (
    RecommitmentEvent,
    RecommitmentRequest,
)
from agentic_calendar.contracts.scheduler_output import SchedulerOutput
from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.contracts.sponsor import Sponsor
from agentic_calendar.contracts.sponsor_report import (
    SponsorReport,
    SponsorReportApproval,
    SponsorReportInput,
)
from agentic_calendar.contracts.strategist_input import StrategistInput
from agentic_calendar.contracts.strategy_constraints import StrategyConstraints
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.contracts.task_plan import TaskPlan
from agentic_calendar.contracts.telemetry import TelemetryEvent
from agentic_calendar.contracts.threshold_change_log import ThresholdChange
from agentic_calendar.contracts.user_duration_multipliers import UserDurationMultipliers
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.contracts.validation_result import ValidationResult
from agentic_calendar.llm_nodes.call_log import LlmCallLog

CONTRACTS: dict[str, type[BaseModel]] = {
    "user_profile": UserProfile,
    "motivation_profile": MotivationProfile,
    "syllabus_units": SyllabusUnits,
    "source_claim": SourceClaim,
    "strategy_constraints": StrategyConstraints,
    "strategist_input": StrategistInput,
    "company_target": CompanyTarget,
    "cache_key": CacheKey,
    "cache_entry": CacheEntry,
    "milestone_template": MilestoneTemplate,
    "task_plan": TaskPlan,
    "validation_result": ValidationResult,
    "scheduler_output": SchedulerOutput,
    "draft_schedule": DraftSchedule,
    "approval_event": ApprovalEvent,
    "calendar_event_mapping": CalendarEventMapping,
    "calendar_reconciliation": CalendarReconciliationResult,
    "plan_diff": PlanDiff,
    "sponsor": Sponsor,
    "sponsor_report": SponsorReport,
    "sponsor_report_input": SponsorReportInput,
    "sponsor_report_approval": SponsorReportApproval,
    "notification_log": NotificationLog,
    "telemetry": TelemetryEvent,
    "drift_event": DriftEvent,
    "user_duration_multipliers": UserDurationMultipliers,
    "checkin_event": CheckinEvent,
    "accountability_contract": AccountabilityContract,
    "accountability_state": AccountabilityState,
    "accountability_intervention": InterventionDecision,
    "nudge": NudgeRecord,
    "recommitment_request": RecommitmentRequest,
    "recommitment_event": RecommitmentEvent,
    "consent_record": ConsentRecord,
    "data_access_audit": DataAccessAuditEntry,
    "pooled_duration_model": PooledDurationModel,
    "power_user_eligibility": PowerUserEligibility,
    "per_user_refinement": PerUserRefinement,
    "llm_call_log": LlmCallLog,
    "threshold_change_log": ThresholdChange,
}


def build_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return the canonical JSON Schema for one Pydantic model.

    Pydantic emits draft-2020-12 by default; we keep that and rely on the
    schema staying byte-stable across runs.
    """
    return model.model_json_schema(mode="serialization")


def write_schemas(out_dir: Path) -> list[Path]:
    """Write one ``<contract>.schema.json`` file per registered contract.

    Returns the list of written paths in stable order. Idempotent: writing
    twice in a row produces no diff.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in CONTRACTS.items():
        schema = build_schema(model)
        path = out_dir / f"{name}.schema.json"
        text = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export the project's Pydantic contracts to JSON Schema."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("../schemas"),
        help="Output directory (default: ../schemas, relative to backend/).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Do not write; instead exit non-zero if existing files differ from "
            "what would be generated. Useful in CI."
        ),
    )
    args = parser.parse_args(argv)
    out_dir = args.out.resolve()

    if args.check:
        return _check(out_dir)
    written = write_schemas(out_dir)
    for path in written:
        print(f"wrote {path}")
    return 0


def _check(out_dir: Path) -> int:
    """Return 0 iff every on-disk schema matches the in-memory build."""
    drift: list[str] = []
    for name, model in CONTRACTS.items():
        path = out_dir / f"{name}.schema.json"
        expected = json.dumps(build_schema(model), indent=2, sort_keys=True) + "\n"
        if not path.exists():
            drift.append(f"missing: {path}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            drift.append(f"out of date: {path}")
    if drift:
        print("Schema drift detected:", file=sys.stderr)
        for d in drift:
            print(f"  {d}", file=sys.stderr)
        print(
            "Run `make schemas` to regenerate.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
