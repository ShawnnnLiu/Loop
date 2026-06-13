"""Render effective tuning values and the threshold change history (read-only).

Usage (module-only, like every Phase 7+ CLI)::

    uv run python -m agentic_calendar.tools.show_thresholds \
        --db dogfood.db [--tuning tuning.toml] [--json]

Every registered section's effective scalar values print first — defaults,
the deterministic replay of the SQLite threshold change log, and (when
``--tuning`` is given) a preview of what applying that file would serve: the
file's overrides win and every field the file does not override previews as
its default (applying would journal a reversion for removed overrides). Each
field is marked ``default`` or ``overridden``. The full change history
follows in insertion order (axiom 07 "Threshold Change Log": every change is
auditable).

Strictly read-only: this tool never appends a journal entry. The effective
preview is computed from :func:`replay_effective` plus the validated file
overrides, never through :func:`apply_tuning`'s mutating path — journaling a
change is ``build_environment``'s job. All values are heuristic priors until
calibration (axiom 07 "MVP Disclosure").
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from agentic_calendar.app.threshold_log import SqliteThresholdChangeLogStore
from agentic_calendar.app.tuning import (
    TUNABLE_SECTIONS,
    extract_overrides,
    load_tuning_file,
    replay_effective,
    scalar_fields,
)
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.threshold_change_log import ThresholdChange

_DISCLOSURE = "All values are heuristic priors pending calibration (axiom 07)."


def _effective_view(
    replayed: Mapping[str, Mapping[str, int | float]],
    file_overrides: Mapping[str, Mapping[str, int | float]] | None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Section → field → ``{"value", "status"}`` without mutating anything.

    Precedence mirrors :func:`apply_tuning`'s serving rule. With a file
    (``file_overrides`` not ``None``) the file fully defines serving: its
    overrides win and every other field previews as its default — applying
    the file would journal a reversion for any journaled override it no
    longer carries. Without a file the journal replay wins: it is the
    last-applied serving truth (reversions are journaled too, so a removed
    override reads as ``default`` here after the next apply). ``status``
    compares against the default by value — a journaled round trip back to
    the default reads as ``default`` again, which is the honest serving
    truth.
    """
    view: dict[str, dict[str, dict[str, Any]]] = {}
    for section, (config_type, default) in TUNABLE_SECTIONS.items():
        fields: dict[str, dict[str, Any]] = {}
        for field_name in scalar_fields(config_type):
            default_value = getattr(default, field_name)
            if file_overrides is not None:
                value = file_overrides.get(section, {}).get(field_name, default_value)
            else:
                value = replayed.get(section, {}).get(field_name, default_value)
            fields[field_name] = {
                "value": value,
                "status": "default" if value == default_value else "overridden",
            }
        view[section] = fields
    return view


def _print_human(
    view: Mapping[str, Mapping[str, Mapping[str, Any]]],
    history: Sequence[ThresholdChange],
) -> None:
    for section, fields in view.items():
        print(f"[{section}]")
        for field_name, info in fields.items():
            print(f"  {field_name} = {info['value']} ({info['status']})")
    print(f"history ({len(history)} entries):")
    for change in history:
        print(
            f"  {change.change_id}  {change.config_section}.{change.threshold_field}"
            f"  {change.prior_value} -> {change.new_value}"
            f"  at {change.effective_at.isoformat()}"
        )
        print(
            f"    justification: {change.justification}\n"
            f"    dataset_reference: {change.dataset_reference}"
        )
    print(_DISCLOSURE)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="show_thresholds",
        description="Show effective tuning values and the threshold change history.",
    )
    parser.add_argument("--db", type=Path, required=True, help="SQLite database path")
    parser.add_argument(
        "--tuning",
        type=Path,
        default=None,
        help="tuning.toml to preview on top of the journal replay (read-only)",
    )
    parser.add_argument("--json", action="store_true", help="emit one JSON document")
    args = parser.parse_args(argv)

    try:
        store = SqliteThresholdChangeLogStore(SqliteDatabase(args.db))
        replayed = replay_effective(store)
        file_overrides: Mapping[str, Mapping[str, int | float]] | None = None
        if args.tuning is not None:
            file_overrides = extract_overrides(load_tuning_file(args.tuning)).overrides
        history = store.list_all()
    except (AgenticCalendarError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    view = _effective_view(replayed, file_overrides)
    if args.json:
        print(
            json.dumps(
                {
                    "sections": view,
                    "history": [c.model_dump(mode="json") for c in history],
                },
                indent=2,
            )
        )
        return 0
    _print_human(view, history)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
