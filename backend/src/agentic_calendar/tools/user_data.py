"""Data-control CLI: view, export, or delete one user's data (Phase 6a).

ADR-0007 deliverable — the operator surface for the three data controls. This
CLI is the composition root that wires the consent region to user-scoped
store contents from outside the region set: it loads consent history and
per-store payloads from a JSON file, wraps each store as a
:class:`UserDataSource`, and runs the audited operation.

Reads a JSON file shaped as::

    {
      "consent_records": [ ...consent_record payloads... ],
      "data_access_audit": [ ...pre-existing audit payloads... ],
      "stores": {
        "telemetry": {
          "user_123": [ ...telemetry payloads... ],
          "user_456": [ ...telemetry payloads... ]
        },
        "placement_preferences": {
          "user_123": [ ...placement_preference payloads... ]
        }
      }
    }

``stores`` maps store name → user id → that user's rows; the composition
root owns user attribution (telemetry events carry no ``user_id`` — the
caller scopes them by the user's task ids before building this file).
Every per-user store belongs here — placement-preference observations
(``docs/specs/placement-preference.schema.md``) included — so view,
export, and delete cover the user's complete footprint.

Usage::

    uv run python -m agentic_calendar.tools.user_data state.json view --user user_123
    uv run python -m agentic_calendar.tools.user_data state.json export --user user_123
    uv run python -m agentic_calendar.tools.user_data state.json delete --user user_123 \
        --at 2026-06-10T09:00:00-07:00

``--at`` pins "now" for deterministic replay. Every action writes a
data-access audit entry; the deletion entry is printed so the audit trail is
visible in the operator's terminal.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from agentic_calendar.common.clock import Clock, FrozenClock, SystemClock
from agentic_calendar.common.ids import UuidIdGenerator
from agentic_calendar.consent import (
    ConsentStoreError,
    InMemoryConsentStore,
    InMemoryDataAccessAuditStore,
    collect_user_data,
    delete_user_data,
)
from agentic_calendar.contracts.consent_record import ConsentRecord
from agentic_calendar.contracts.data_access_audit import (
    DataAccessAuditEntry,
    DataAccessor,
    DataAccessPurpose,
)


class _StaticUserDataSource:
    """A :class:`UserDataSource` over payloads pre-bucketed by user id."""

    def __init__(self, name: str, rows_by_user: dict[str, list[dict[str, Any]]]) -> None:
        self._name = name
        self._rows_by_user = rows_by_user

    @property
    def name(self) -> str:
        return self._name

    def list_payloads_for_user(self, user_id: str) -> list[dict[str, Any]]:
        return list(self._rows_by_user.get(user_id, []))

    def delete_for_user(self, user_id: str) -> int:
        return len(self._rows_by_user.pop(user_id, []))


def _fail(message: str) -> int:
    print(f"error: {message}", file=sys.stderr)
    return 1


def _build_sources(raw: Any) -> list[_StaticUserDataSource]:
    if not isinstance(raw, dict):
        raise ValueError("'stores' must be a JSON object of store name -> user id -> rows")
    sources: list[_StaticUserDataSource] = []
    for name, by_user in raw.items():
        if not isinstance(by_user, dict):
            raise ValueError(f"store '{name}' must map user ids to row arrays")
        rows_by_user: dict[str, list[dict[str, Any]]] = {}
        for user_id, rows in by_user.items():
            if not isinstance(rows, list):
                raise ValueError(f"store '{name}' rows for '{user_id}' must be a JSON array")
            rows_by_user[user_id] = rows
        sources.append(_StaticUserDataSource(name, rows_by_user))
    return sources


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="View, export, or delete one user's data (audited)."
    )
    parser.add_argument("file", type=Path, help="Path to the user-data input JSON.")
    parser.add_argument(
        "action", choices=("view", "export", "delete"), help="Data control to run."
    )
    parser.add_argument("--user", required=True, help="The subject user id.")
    parser.add_argument(
        "--at",
        type=str,
        default=None,
        help="ISO timestamp to pin 'now' for deterministic replay.",
    )
    args = parser.parse_args(argv)

    try:
        data: Any = json.loads(args.file.read_text(encoding="utf-8"))
    except OSError as exc:
        return _fail(f"cannot read {args.file}: {exc}")
    except json.JSONDecodeError as exc:
        return _fail(f"invalid JSON in {args.file}: {exc}")
    if not isinstance(data, dict):
        return _fail(f"expected a JSON object, got {type(data).__name__}")

    clock: Clock
    if args.at is not None:
        try:
            pinned = datetime.fromisoformat(args.at)
        except ValueError as exc:
            return _fail(f"invalid --at timestamp: {exc}")
        if pinned.tzinfo is None:
            return _fail("--at must be timezone-aware (include an offset)")
        clock = FrozenClock(pinned)
    else:
        clock = SystemClock()

    consent_store = InMemoryConsentStore(clock=clock)
    audit_store = InMemoryDataAccessAuditStore()
    try:
        for raw_record in data.get("consent_records", []):
            consent_store.load(ConsentRecord.model_validate(raw_record))
        for raw_entry in data.get("data_access_audit", []):
            audit_store.append(DataAccessAuditEntry.model_validate(raw_entry))
        sources = _build_sources(data.get("stores", {}))
    except (ValidationError, ValueError, ConsentStoreError) as exc:
        return _fail(str(exc))

    ids = UuidIdGenerator()
    if args.action == "delete":
        counts = delete_user_data(
            args.user,
            list(sources),
            consent_store=consent_store,
            audit_store=audit_store,
            clock=clock,
            id_generator=ids,
            accessor=DataAccessor.OPERATOR_CLI,
        )
        audit_entry = audit_store.list_for_user(args.user)[-1]
        print(f"deleted data for {args.user}:")
        for name in sorted(counts):
            print(f"  {name}: {counts[name]} row(s) removed")
        print(
            f"audit: {audit_entry.audit_entry_id} "
            f"({audit_entry.reason_code.value if audit_entry.reason_code else 'none'})"
        )
        return 0

    purpose = (
        DataAccessPurpose.DATA_EXPORT if args.action == "export" else DataAccessPurpose.DATA_VIEW
    )
    bundle = collect_user_data(
        args.user,
        list(sources),
        consent_store=consent_store,
        audit_store=audit_store,
        clock=clock,
        id_generator=ids,
        accessor=DataAccessor.OPERATOR_CLI,
        purpose=purpose,
    )
    if args.action == "export":
        print(json.dumps(bundle, indent=2))
        return 0

    print(f"data held for {args.user}:")
    for record in bundle["consent_records"]:
        print(
            f"  consent {record['scope']}: {record['status']} "
            f"(version {record['consent_version']})"
        )
    if not bundle["consent_records"]:
        print("  consent: no records")
    for name in sorted(bundle["stores"]):
        print(f"  {name}: {len(bundle['stores'][name])} row(s)")
    print(f"  data_access_audit: {len(bundle['data_access_audit'])} entr(ies)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
