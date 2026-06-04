"""``notification_log`` contract.

Canonical spec: ``docs/specs/notification-log.schema.md``.

:class:`NotificationLog` is the append-only audit record for every sponsor
report delivery attempt — drafted, approved, sent, dry-run, blocked, or failed.
Axiom 21 requires that generation, approval, and delivery are logged, and the
Phase 3 acceptance criteria require each delivery to record ``report_id``,
``sponsor_id``, ``visibility_level``, and status.

The log stores identifiers and outcome metadata only. It must never contain
report body content (milestone names, calendar titles, denylisted fields).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .motivation_profile import NudgeChannel, SponsorVisibility
from .reason_codes import ReasonCode


class NotificationStatus(StrEnum):
    """Terminal outcome of a delivery attempt (spec "Status Semantics")."""

    DRAFTED = "drafted"
    APPROVED = "approved"
    SENT = "sent"
    DRY_RUN = "dry_run"
    BLOCKED = "blocked"
    FAILED = "failed"


#: Statuses that require a non-null ``reason_code``.
_FAILURE_STATUSES: frozenset[NotificationStatus] = frozenset(
    {NotificationStatus.BLOCKED, NotificationStatus.FAILED}
)


class NotificationLog(BaseModel):
    """Append-only audit record for one sponsor report delivery attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    notification_log_id: str = Field(min_length=1)
    report_id: str = Field(min_length=1)
    sponsor_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    visibility_level: SponsorVisibility
    channel: NudgeChannel
    status: NotificationStatus
    reason_code: ReasonCode | None = None
    engineering_review: bool = False
    dry_run: bool = False
    created_at: datetime

    @model_validator(mode="after")
    def _created_at_aware(self) -> NotificationLog:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at must be timezone-aware")
        return self

    @model_validator(mode="after")
    def _reason_code_matches_status(self) -> NotificationLog:
        is_failure = self.status in _FAILURE_STATUSES
        if is_failure and self.reason_code is None:
            raise ValueError(f"status '{self.status.value}' requires a non-null reason_code")
        if not is_failure and self.reason_code is not None:
            raise ValueError(f"status '{self.status.value}' must have a null reason_code")
        return self

    @model_validator(mode="after")
    def _engineering_review_only_on_blocked(self) -> NotificationLog:
        if self.engineering_review and self.status is not NotificationStatus.BLOCKED:
            raise ValueError("engineering_review may be true only on a blocked entry")
        return self

    @model_validator(mode="after")
    def _visibility_none_only_on_permission_block(self) -> NotificationLog:
        """A ``none`` visibility is legitimate only on the no-permission block.

        Every other status carries the level the report was filtered to, which
        is never ``none`` (a ``none``-level report is never built)."""
        if self.visibility_level is SponsorVisibility.NONE:
            permission_block = (
                self.status is NotificationStatus.BLOCKED
                and self.reason_code is ReasonCode.SPONSOR_PERMISSION_MISSING
            )
            if not permission_block:
                raise ValueError(
                    "visibility_level 'none' is only valid on a blocked entry "
                    "with reason_code SPONSOR_PERMISSION_MISSING"
                )
        return self
