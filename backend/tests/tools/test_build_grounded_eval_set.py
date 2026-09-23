"""The v10 grounded eval set is a pure function of the pinned corpus."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.contracts.user_profile import UserProfile
from agentic_calendar.llm_nodes.call_log import LlmNodeName
from agentic_calendar.llm_nodes.eval import EvalSet
from agentic_calendar.tools.build_grounded_eval_set import (
    _PROFILE_MATRIX,
    DEFAULT_MIN_CONFIDENCE,
    _claim_window,
    build_eval_set,
    main,
    render,
    servable_claims_by_track,
)
from tests._fixture_loader import iter_valid

_BACKEND = Path(__file__).parents[2]
_EVAL_SET_V10 = _BACKEND / "evalsets" / "eval_set_v10.json"
_SNAPSHOT = "snap_0217291f46e331b9"
_AS_OF = date(2026, 9, 23)
_K = 10
_CLI = [
    "--queries",
    str(_BACKEND / "corpus" / "claim_queries_v4.json"),
    "--manifest",
    str(_BACKEND / "corpus" / "manifest_v1.json"),
    "--corpus-db",
    str(_BACKEND / "corpus" / "corpus.db"),
    "--snapshot",
    _SNAPSHOT,
    "--k",
    str(_K),
    "--as-of",
    _AS_OF.isoformat(),
]


def _load_v10() -> EvalSet:
    return EvalSet.model_validate(json.loads(_EVAL_SET_V10.read_text(encoding="utf-8")))


def test_committed_v10_matches_regeneration() -> None:
    """``--check`` against the committed file: the set is derived, not hand
    edited, so any drift between corpus/query/matrix and the file fails."""
    assert main([*_CLI, "--out", str(_EVAL_SET_V10), "--check"]) == 0


def test_v10_has_at_least_forty_grounded_strategist_cases() -> None:
    """The reason the set exists: citation coverage averaged over ≥40 cases."""
    eval_set = _load_v10()
    assert eval_set.eval_set_version == "v10"
    assert len(eval_set.cases) >= 40
    assert all(case.node is LlmNodeName.STRATEGIST for case in eval_set.cases)
    assert all(case.case_id.endswith("_grounded") for case in eval_set.cases)


def test_v10_cases_carry_servable_contract_valid_inputs() -> None:
    """Every case pins a valid profile and ≥1 claim the D1 floor would keep,
    with ids unique within the case and disjoint from golden fixture ids."""
    eval_set = _load_v10()
    fixture_ids = {str(fixture.payload["claim_id"]) for fixture in iter_valid("source_claim")}
    for case in eval_set.cases:
        UserProfile.model_validate(case.inputs["user_profile"])
        claims = [SourceClaim.model_validate(raw) for raw in case.inputs["source_claims"]]
        assert claims, case.case_id
        ids = [claim.claim_id for claim in claims]
        assert len(ids) == len(set(ids)), case.case_id
        assert not set(ids) & fixture_ids
        assert all(claim.confidence_score >= DEFAULT_MIN_CONFIDENCE for claim in claims)
        assert all(claim.expires_at > _AS_OF for claim in claims), case.case_id


def test_v10_spans_tracks_with_distinct_profiles_and_rotating_claims() -> None:
    """Coverage is only meaningful if the cases differ: distinct profiles per
    track, more than one track, and consecutive cases not sharing one claim
    window wholesale."""
    eval_set = _load_v10()
    tracks = {case.case_id.split("_")[1] for case in eval_set.cases}
    assert len(tracks) >= 4
    versions = [case.inputs["user_profile"]["profile_version"] for case in eval_set.cases]
    assert len(versions) == len(set(versions))
    windows = [
        tuple(c["claim_id"] for c in case.inputs["source_claims"]) for case in eval_set.cases
    ]
    assert len(set(windows)) > len(windows) // 2


def test_claim_window_rotates_and_wraps() -> None:
    claims = list(range(7))  # type: ignore[arg-type]
    assert _claim_window(claims, 0, 5) == [0, 1, 2, 3, 4]  # type: ignore[comparison-overlap]
    assert _claim_window(claims, 1, 5) == [5, 6, 0, 1, 2]  # type: ignore[comparison-overlap]
    assert _claim_window(claims, 0, 10) == list(range(7))  # type: ignore[comparison-overlap]
    assert _claim_window([], 3, 5) == []


def test_tracks_without_servable_claims_are_skipped_and_min_cases_enforced() -> None:
    """A track with no claims contributes no cases (never empty grounded
    cases), and the builder reports it so a thinning corpus is visible."""
    claims_by_track = servable_claims_by_track(
        queries=_BACKEND / "corpus" / "claim_queries_v4.json",
        manifest_path=_BACKEND / "corpus" / "manifest_v1.json",
        corpus_db=_BACKEND / "corpus" / "corpus.db",
        snapshot_id=_SNAPSHOT,
        k=_K,
        as_of=_AS_OF,
        min_confidence=DEFAULT_MIN_CONFIDENCE,
    )
    only_swe = {CareerTrack.SWE: claims_by_track[CareerTrack.SWE]}
    eval_set, skipped = build_eval_set(
        version="test",
        claims_by_track=only_swe,
        claims_per_case=5,
        snapshot_id=_SNAPSHOT,
        k=_K,
        as_of=_AS_OF,
    )
    assert len(eval_set.cases) == len(_PROFILE_MATRIX[CareerTrack.SWE])
    assert set(skipped) == set(_PROFILE_MATRIX) - {CareerTrack.SWE}
    assert render(eval_set).endswith("\n")


def test_cli_refuses_a_set_below_min_cases(tmp_path: Path) -> None:
    out = tmp_path / "set.json"
    assert main([*_CLI, "--out", str(out), "--min-cases", "1000"]) == 1
    assert not out.exists()
