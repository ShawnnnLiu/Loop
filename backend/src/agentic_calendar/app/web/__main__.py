"""Offline demo runner: ``python -m agentic_calendar.app.web``.

Wires an in-memory, fixture-backed :class:`CycleService` (the same offline
nodes the operator CLI's ``--llm fixture`` uses), auto-onboards the sample
"Backend SWE" profile so ``propose`` works out of the box, and serves the
Increment-1 JSON API on localhost. This is a *demo* composition — no auth, no
persistence, in-memory calendar; the hosted multi-user composition (real
adapter, SQLite, sessions) arrives in later increments.
"""

from __future__ import annotations

from agentic_calendar.app.cycle import CycleService
from agentic_calendar.app.environment import AppEnvironment, build_environment
from agentic_calendar.tools.llm_smoke import sample_fixture_inputs
from agentic_calendar.tools.run_cycle import _fixture_bundle

from .app import create_app


def build_demo_environment() -> tuple[AppEnvironment, str]:
    """An in-memory fixture environment with the sample profile onboarded.

    Reuses ``tools.run_cycle._fixture_bundle`` (the CLI's offline node bundle)
    rather than duplicating the claim-stripping sample-data prep. Returns the
    environment plus the sample profile's user id (the single acting user in
    this no-auth dev mode).
    """
    env = build_environment(nodes_factory=_fixture_bundle, db_path=None)
    profile, _syllabus, _plan = sample_fixture_inputs()
    CycleService(env).onboard(
        {"user_profile": profile.model_dump(mode="json"), "timezone": "UTC"}
    )
    return env, profile.user_id


def main() -> None:
    import uvicorn

    env, user_id = build_demo_environment()
    app = create_app(env=env, default_user_id=user_id)
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
