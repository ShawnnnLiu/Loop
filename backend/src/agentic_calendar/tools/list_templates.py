"""List the canned milestone templates (Phase 5c).

A read-only operator view of the deterministic ``templates/`` registry: prints
each :class:`MilestoneTemplate` (one per goal class) and its milestones, or just
the template for ``--goal-class``.

Like the other Phase 4+ operator tools, this is invoked as a module (it is not
registered as a console script).

Usage::

    uv run python -m agentic_calendar.tools.list_templates
    uv run python -m agentic_calendar.tools.list_templates --goal-class career_transition
    uv run python -m agentic_calendar.tools.list_templates --json
"""

from __future__ import annotations

import argparse
import json
import sys

from agentic_calendar.templates import (
    GoalClass,
    MilestoneTemplate,
    get_template,
    list_templates,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="List the canned milestone templates from the registry."
    )
    parser.add_argument(
        "--goal-class",
        help=(
            "Show only this goal class (one of: "
            f"{', '.join(g.value for g in GoalClass)})."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emit the templates as JSON instead of human-readable text.",
    )
    args = parser.parse_args(argv)

    if args.goal_class is not None:
        try:
            goal_class = GoalClass(args.goal_class)
        except ValueError:
            valid = ", ".join(g.value for g in GoalClass)
            print(
                f"error: unknown goal class {args.goal_class!r}; valid values: {valid}",
                file=sys.stderr,
            )
            return 1
        templates: tuple[MilestoneTemplate, ...] = (get_template(goal_class),)
    else:
        templates = list_templates()

    if args.emit_json:
        print(json.dumps([t.model_dump(mode="json") for t in templates], indent=2))
        return 0

    for template in templates:
        print(f"{template.goal_class.value}  [{template.template_id}]")
        print(f"  schema_version: {template.template_schema_version}")
        for m in template.milestones:
            print(
                f"  - {m.milestone_id:28}  D-{m.offset_days_before_deadline:<4}  "
                f"{m.priority.value:6}  {m.default_estimated_total_min:>5} min  {m.title}"
            )
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
