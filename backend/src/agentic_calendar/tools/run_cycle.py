"""Operator CLI for the full dogfood cycle (Phase 9b).

Usage (module-only, like every Phase 7+ CLI):

    uv run python -m agentic_calendar.tools.run_cycle onboard --db dogfood.db profile.json
    uv run python -m agentic_calendar.tools.run_cycle propose --db dogfood.db --user user_123
    uv run python -m agentic_calendar.tools.run_cycle approve --db dogfood.db --user user_123
    uv run python -m agentic_calendar.tools.run_cycle write   --db dogfood.db --user user_123 --dry-run
    uv run python -m agentic_calendar.tools.run_cycle write   --db dogfood.db --user user_123
    uv run python -m agentic_calendar.tools.run_cycle ingest  --db dogfood.db --user user_123 events.json
    uv run python -m agentic_calendar.tools.run_cycle status  --db dogfood.db --user user_123

``--db`` is required: the whole point of the cycle CLI is state that survives
between invocations (SQLite, Phase 9a). Every command prints one JSON result
document on stdout and exits 0; operator errors (wrong state, missing user)
print to stderr and exit 1.

LLM backend (``propose`` / ``ingest`` only): ``--llm fixture`` (default) uses
the deterministic nodes over the smoke-test sample data — offline, no API
key, intended for demos and tests with the sample "Backend SWE" profile.
``--llm live`` uses the real Anthropic adapters (Phase 8) and requires
``ANTHROPIC_API_KEY``. The calendar backend defaults to in-memory; pass
``write --calendar google --target-calendar-id <id>`` after running the
one-time ``tools/google_calendar_auth.py`` flow to write to the dedicated
secondary Google calendar (Phase 9c). Tuning overrides load from
``tuning.toml`` (or ``--tuning``) and are journaled to the threshold change
log (Phase 9d).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from agentic_calendar.app.cycle import (
    DEFAULT_TARGET_CALENDAR_ID,
    CycleError,
    CycleService,
)
from agentic_calendar.app.environment import (
    AppEnvironment,
    LlmNodeBundle,
    NodeDependencies,
    build_environment,
)
from agentic_calendar.calendar_writer.adapter import ExternalCalendarAdapter
from agentic_calendar.calendar_writer.google_adapter import (
    GoogleApiHttpTransport,
    GoogleCalendarAdapter,
)
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.contracts.checkin_event import RecoveryAction
from agentic_calendar.contracts.syllabus_units import SyllabusUnits
from agentic_calendar.llm_nodes import (
    AnthropicMessagesTransport,
    AnthropicPlanner,
    AnthropicReflectionSummary,
    AnthropicResumeIntake,
    AnthropicStrategist,
    AnthropicUserFacingExplanation,
    DeterministicReflectionSummary,
    DeterministicUserFacingExplanation,
    FixturePlanner,
    FixtureResumeIntake,
    FixtureStrategist,
)
from agentic_calendar.skill_taxonomy import SkillTaxonomyRegistry, load_registry, resolve
from agentic_calendar.tools.google_calendar_auth import (
    DEFAULT_TOKEN_PATH,
    build_calendar_service,
)
from agentic_calendar.tools.llm_smoke import sample_fixture_inputs


def _taxonomy_aliases(registry: SkillTaxonomyRegistry) -> dict[str, str]:
    """Alias → canonical display name, extracted as plain data for the fixture
    node (which must not import the kernel; ``.importlinter`` contract 18)."""
    return {
        alias: entry.display_name
        for entry in registry.entries
        for alias in entry.aliases
    }


def _weak_spot_resolver(registry: SkillTaxonomyRegistry) -> Callable[[str], str | None]:
    """Surface → ``skill_id`` (or ``None`` when out-of-vocabulary): the kernel's
    resolver wrapped as the plain callable the Anthropic adapter's post-validator
    takes (same no-kernel-import boundary as the fixture aliases)."""

    def _resolve(surface: str) -> str | None:
        entry = resolve(surface, registry)
        return entry.skill_id if entry is not None else None

    return _resolve


def _fixture_bundle(deps: NodeDependencies) -> LlmNodeBundle:
    """Deterministic nodes over the smoke sample data (offline default).

    The sample syllabus's source-claim references are stripped: fixture mode
    runs against an empty claim store, and an orphaned reference would
    (rightly) fail syllabus validation. The modules are not company-specific,
    so claim-free modules are contract-legal; the claim-registry path is
    exercised by the app test suite with seeded stores, not by this demo.
    """
    del deps  # deterministic nodes need no transport, store, or clock
    profile, syllabus, plan = sample_fixture_inputs()
    clean_syllabus = SyllabusUnits.model_validate(
        syllabus.model_dump()
        | {
            "modules": [
                m | {"source_claim_ids": []}
                for m in (mod.model_dump() for mod in syllabus.modules)
            ]
        }
    )
    return LlmNodeBundle(
        strategist=FixtureStrategist({profile.target_role: clean_syllabus}),
        planner=FixturePlanner({clean_syllabus.syllabus_version: plan}),
        reflection=DeterministicReflectionSummary(),
        explanation=DeterministicUserFacingExplanation(),
        resume_intake=FixtureResumeIntake(
            taxonomy_aliases=_taxonomy_aliases(load_registry())
        ),
    )


def _live_bundle(deps: NodeDependencies) -> LlmNodeBundle:
    """Real Anthropic adapters (Phase 8); requires ``ANTHROPIC_API_KEY``.

    Checked here, before any node is constructed: without the guard a
    missing key surfaces as a raw SDK ``TypeError`` traceback mid-propose
    instead of a clean operator error (same precondition gate as
    ``llm_smoke --live``).
    """
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise CycleError(
            "--llm live requires ANTHROPIC_API_KEY in the environment; "
            "export it or use --llm fixture for the offline demo nodes"
        )
    transport = AnthropicMessagesTransport()
    return LlmNodeBundle(
        strategist=AnthropicStrategist(
            transport=transport,
            store=deps.call_log_store,
            clock=deps.clock,
            id_generator=deps.id_generator,
        ),
        planner=AnthropicPlanner(
            transport=transport,
            store=deps.call_log_store,
            clock=deps.clock,
            id_generator=deps.id_generator,
        ),
        reflection=AnthropicReflectionSummary(
            transport=transport,
            store=deps.call_log_store,
            clock=deps.clock,
            id_generator=deps.id_generator,
        ),
        explanation=AnthropicUserFacingExplanation(
            transport=transport,
            store=deps.call_log_store,
            clock=deps.clock,
            id_generator=deps.id_generator,
        ),
        resume_intake=AnthropicResumeIntake(
            transport=transport,
            store=deps.call_log_store,
            clock=deps.clock,
            id_generator=deps.id_generator,
            weak_spot_resolver=_weak_spot_resolver(load_registry()),
        ),
    )


def _calendar_adapter(args: argparse.Namespace) -> ExternalCalendarAdapter | None:
    """The real Google adapter for ``--calendar google``; ``None`` keeps the
    in-memory default. The dedicated secondary calendar id must be passed
    explicitly — the adapter itself additionally refuses ``primary``."""
    if getattr(args, "calendar", "memory") != "google":
        return None
    if args.target_calendar_id == DEFAULT_TARGET_CALENDAR_ID:
        raise CycleError(
            "--calendar google requires an explicit --target-calendar-id "
            "(the id of your dedicated secondary calendar)"
        )
    service = build_calendar_service(token_path=args.google_token)
    return GoogleCalendarAdapter(
        transport=GoogleApiHttpTransport(service),
        dedicated_calendar_id=args.target_calendar_id,
    )


def _tuning_path(args: argparse.Namespace) -> Path | None:
    """An explicit ``--tuning`` flag wins; otherwise a backend-relative
    ``tuning.toml`` is picked up only when it exists. Either way every
    override is journaled to the threshold change log before serving
    (axiom 07: no silent threshold changes)."""
    explicit: Path | None = getattr(args, "tuning", None)
    if explicit is not None:
        return explicit
    default = Path("tuning.toml")
    return default if default.exists() else None


def _build(args: argparse.Namespace) -> CycleService:
    llm = getattr(args, "llm", "fixture")
    env: AppEnvironment = build_environment(
        nodes_factory=_live_bundle if llm == "live" else _fixture_bundle,
        db_path=Path(args.db),
        calendar_adapter=_calendar_adapter(args),
        tuning_path=_tuning_path(args),
    )
    return CycleService(env)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _emit(result: Any) -> int:
    print(result.model_dump_json(indent=2))
    return 0


def _cmd_onboard(args: argparse.Namespace) -> int:
    service = _build(args)
    payload = _read_json(args.file)
    return _emit(service.onboard(payload))


def _cmd_propose(args: argparse.Namespace) -> int:
    service = _build(args)
    extra: dict[str, Any] = {}
    if args.input is not None:
        extra = _read_json(args.input)
    return _emit(
        service.propose(
            args.user,
            free_busy=extra.get("free_busy", ()),
            horizon_days=extra.get("horizon_days"),
            recovery_mode=(
                RecoveryAction(args.recovery_mode) if args.recovery_mode else None
            ),
        )
    )


def _cmd_approve(args: argparse.Namespace) -> int:
    service = _build(args)
    return _emit(service.approve(args.user, run_id=args.run, reject=args.reject))


def _cmd_write(args: argparse.Namespace) -> int:
    service = _build(args)
    return _emit(
        service.write(
            args.user,
            run_id=args.run,
            target_calendar_id=args.target_calendar_id,
            dry_run=args.dry_run,
        )
    )


def _cmd_ingest(args: argparse.Namespace) -> int:
    service = _build(args)
    raw = _read_json(args.file)
    payloads = raw if isinstance(raw, list) else [raw]
    return _emit(service.ingest(args.user, payloads))


def _cmd_status(args: argparse.Namespace) -> int:
    service = _build(args)
    return _emit(service.status(args.user))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_cycle",
        description="Drive the full plan cycle against one persistent database.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser, *, user: bool = True) -> None:
        p.add_argument("--db", required=True, help="SQLite database path")
        p.add_argument(
            "--tuning",
            type=Path,
            default=None,
            help="tuning.toml path (default: ./tuning.toml when it exists); "
            "overrides are journaled to the threshold change log",
        )
        if user:
            p.add_argument("--user", required=True, help="user id")

    p_onboard = sub.add_parser("onboard", help="validate and store the user bundle")
    common(p_onboard, user=False)
    p_onboard.add_argument(
        "file",
        type=Path,
        help="JSON: {user_profile, timezone?, motivation_profile?}",
    )
    p_onboard.set_defaults(func=_cmd_onboard)

    p_propose = sub.add_parser(
        "propose", help="produce a draft plan + schedule awaiting approval"
    )
    common(p_propose)
    p_propose.add_argument("--input", type=Path, default=None,
                           help="JSON: {free_busy?, horizon_days?}")
    p_propose.add_argument("--llm", choices=("fixture", "live"), default="fixture")
    p_propose.add_argument(
        "--recovery-mode",
        choices=tuple(m.value for m in RecoveryAction),
        default=None,
        help="user's recovery choice when the replan asked for one",
    )
    p_propose.set_defaults(func=_cmd_propose)

    p_approve = sub.add_parser("approve", help="approve (or reject) the awaiting draft")
    common(p_approve)
    p_approve.add_argument("--run", default=None, help="run id (default: latest)")
    p_approve.add_argument("--reject", action="store_true")
    p_approve.set_defaults(func=_cmd_approve)

    p_write = sub.add_parser("write", help="execute the approved calendar write")
    common(p_write)
    p_write.add_argument("--run", default=None, help="run id (default: latest)")
    p_write.add_argument("--target-calendar-id", default=DEFAULT_TARGET_CALENDAR_ID)
    p_write.add_argument("--dry-run", action="store_true")
    p_write.add_argument(
        "--calendar",
        choices=("memory", "google"),
        default="memory",
        help="calendar backend; google requires a stored OAuth token "
        "(see tools/google_calendar_auth.py) and an explicit "
        "--target-calendar-id for the dedicated secondary calendar",
    )
    p_write.add_argument("--google-token", type=Path, default=DEFAULT_TOKEN_PATH)
    p_write.set_defaults(func=_cmd_write)

    p_ingest = sub.add_parser("ingest", help="store telemetry and assess the plan")
    common(p_ingest)
    p_ingest.add_argument("--llm", choices=("fixture", "live"), default="fixture")
    p_ingest.add_argument("file", type=Path, help="JSON telemetry payload or array")
    p_ingest.set_defaults(func=_cmd_ingest)

    p_status = sub.add_parser("status", help="read-only snapshot")
    common(p_status)
    p_status.set_defaults(func=_cmd_status)

    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (CycleError, AgenticCalendarError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
