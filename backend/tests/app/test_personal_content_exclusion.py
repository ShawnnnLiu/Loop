"""The personal-content injection wall (KT-C-d, ``06-knowledge-tree.md``).

Custom groups, custom nodes, and notes are the personal layer: free text that
**never** enters a prompt, a coverage metric, or a sponsor payload. This is the
categorical guarantee the whole content-class split rests on, so it gets its own
adversarial test - distinctive sentinel strings planted in every personal-content
surface, then asserted absent everywhere they must never appear.
"""

from __future__ import annotations

import json

from agentic_calendar.contracts.sponsor_report import SponsorReportInput
from tests.app.test_cycle import USER_ID, make_service
from tests.narrative._helpers import make_profile, selection

BACKEND = "backend-infrastructure-engineer"

# Sentinels that must never leak out of the personal layer.
_GROUP_NAME = "ZZ_SECRET_GROUP_NAME"
_NODE_NAME = "ZZ_SECRET_NODE_NAME"
_NODE_DESC = "ZZ_SECRET_NODE_DESCRIPTION"
_NOTE_TEXT = "ZZ_SECRET_NOTE_TEXT"
_SENTINELS = (_GROUP_NAME, _NODE_NAME, _NODE_DESC, _NOTE_TEXT)


def _service_with_personal_content():
    service, _env, _clock = make_service(onboard=False, seed_claims=False)
    service.onboard(
        {
            "user_profile": make_profile([], selection(pathway_id=BACKEND)).model_dump(
                mode="json"
            ),
            "timezone": "UTC",
        }
    )
    view = service.create_custom_group(USER_ID, name=_GROUP_NAME)
    gid = next(g.group_id for g in view.groups if g.is_personal)
    service.create_custom_node(
        USER_ID, name=_NODE_NAME, group_id=gid, description=_NODE_DESC
    )
    # A note on a curated skill node (free text on pathway content is still personal).
    skill = next(n for n in service.knowledge_map_view(USER_ID).nodes if n.kind == "skill")
    service.upsert_note(USER_ID, node_id=skill.node_id, text=_NOTE_TEXT)
    return service


def test_personal_content_never_enters_the_strategist_bundle() -> None:
    service = _service_with_personal_content()
    profile = service._require_onboarding(USER_ID).user_profile
    constraints, _template = service._pathway_constraints(profile)
    assert constraints is not None

    # The exact bytes embedded in the Strategist prompt are the constraints JSON.
    blob = json.dumps(constraints.model_dump(mode="json"))
    for sentinel in _SENTINELS:
        assert sentinel not in blob
    # And no personal-layer id reaches the knowledge-node vocabulary.
    assert all(
        n.node_id.startswith("kn-") for n in constraints.knowledge_nodes
    )


def test_personal_content_moves_no_coverage_metric() -> None:
    service = _service_with_personal_content()

    # Pathway fit is unchanged by the personal layer.
    result = service.pathways_view(USER_ID, track="swe")
    selected = next(c for c in result.cards if c.pathway_id == BACKEND)
    assert selected.filled_slots == 0  # no evidence; custom content adds nothing

    # Knowledge-map header/branch/group counts cover pathway content only.
    view = service.knowledge_map_view(USER_ID)
    assert all(b.honed_count == 0 for b in view.branches)
    custom_group = next(g for g in view.groups if g.is_personal)
    assert custom_group.honed_count == 0 and custom_group.total_count == 0


def test_sponsor_report_boundary_carries_no_map_content() -> None:
    # The sponsor report is built from an already-computed SponsorReportInput -
    # completion / milestone / task summaries. It has no field that could carry a
    # map, an overlay record, or any personal free text: the wall is structural.
    fields = set(SponsorReportInput.model_fields)
    assert not any(
        token in name
        for name in fields
        for token in ("knowledge", "overlay", "custom", "note", "map")
    )
