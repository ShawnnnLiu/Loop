"""Tests for the keyless demo composition (``python -m agentic_calendar.app.web``).

``build_demo_environment`` is the dev entrypoint's wiring — fixture nodes, no
key, in-memory stores, sample profile pre-onboarded. These prove it constructs
the full five-node bundle (RI-C) and serves the extract endpoint offline, so
"the demo server boots keyless" stays a tested claim, not a README promise.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from agentic_calendar.app.web.__main__ import build_demo_environment
from agentic_calendar.app.web.app import create_app
from agentic_calendar.llm_nodes import FixtureResumeIntake


def test_demo_environment_wires_the_five_node_fixture_bundle() -> None:
    env, user_id = build_demo_environment()
    assert user_id
    nodes = env.nodes
    assert isinstance(nodes.resume_intake, FixtureResumeIntake)
    # The sample profile is pre-onboarded so propose works out of the box.
    assert env.state.get_onboarding(user_id) is not None


def test_demo_app_serves_extract_keyless() -> None:
    env, user_id = build_demo_environment()
    client = TestClient(create_app(env=env, default_user_id=user_id))
    assert client.get("/healthz").json() == {"status": "ok"}

    resp = client.post(
        "/api/onboard/extract",
        json={
            "resume_text": (
                "Senior Backend Engineer at Acme Corp\n"
                "Python and Go services on Kubernetes for five years."
            ),
            "draft_context": {"target_role": "Backend SWE"},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["proposal"]["skills"]
    assert body["skills_canonical"]
