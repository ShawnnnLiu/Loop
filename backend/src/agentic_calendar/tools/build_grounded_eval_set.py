"""Build a grounded strategist eval set from the pinned retrieval corpus.

Usage::

    # Regenerate the committed set (offline, deterministic).
    uv run python -m agentic_calendar.tools.build_grounded_eval_set \\
        --queries corpus/claim_queries_v4.json \\
        --manifest corpus/manifest_v1.json \\
        --corpus-db corpus/corpus.db --snapshot snap_0217291f46e331b9 \\
        --k 10 --as-of 2026-09-23 \\
        --out evalsets/eval_set_v10.json

    # Drift check (the test suite runs this against the committed file).
    ... --check

Why this exists: the v4 grounded twins carry three grounded cases, so the
Tier-1 citation-coverage rate (axiom 22, grounding-RAG G-H) averaged over
three data points and swung 0.64 → 0.23 on the SAME model between July and
September. A model or prompt decision needs the metric averaged over tens of
cases. Hand-pinning forty claim payloads is not reviewable; deriving them is.

What it does — all deterministic, no LLM, no network:

* Runs the checked-in claim-assembly path (``refresh_claims.assemble_claims``
  → the sanctioned ``SourceClaimIngestor`` scoring against a throwaway store)
  on the pinned snapshot, with the retrieval ``k`` overridden so the eval
  set has more claim supply than the production query set needs.
* Keeps only claims the D1 serving floor would keep (``--min-confidence``,
  default 0.30 — the same floor the v4 test asserts), grouped by the track
  the query that retrieved them belongs to.
* Pairs each track's claims with a fixed matrix of user profiles (below):
  every case gets a rotating window of ``--claims-per-case`` claims so
  consecutive cases in a track see different claim sets, and each profile
  varies level, timeline, hours, strengths and weaknesses — the inputs the
  strategist prompt actually renders.
* Tracks with no servable claims are skipped and reported; the tool fails
  loudly if fewer than ``--min-cases`` grounded cases result, so a shrinking
  corpus cannot silently thin the metric back down.

The claims' ``date_collected`` / ``expires_at`` come from the corpus
documents and the ingestion clock (``--as-of``), so the committed set is a
pure function of (snapshot, query set, k, as-of date, profile matrix) and
``--check`` proves it.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from pydantic import ValidationError

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.common_types import Day, ExperienceLevel
from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.contracts.user_profile import (
    DeepWorkWindow,
    HardConstraints,
    Preferences,
    UserProfile,
)
from agentic_calendar.llm_nodes.call_log import LlmNodeName
from agentic_calendar.llm_nodes.eval import EvalCase, EvalSet
from agentic_calendar.retrieval import SqliteChunkIndex, SqliteCorpusRegistry
from agentic_calendar.source_claims.ingestion import (
    ClaimIngestionStatus,
    InMemorySourceClaimStore,
)
from agentic_calendar.tools.ingest_corpus import load_manifest
from agentic_calendar.tools.refresh_claims import (
    assemble_claims,
    ingest_assembled,
    load_claim_queries,
)

DEFAULT_MIN_CONFIDENCE = 0.30
"""The D1 serving floor: claims below it never reach a production prompt."""
DEFAULT_CLAIMS_PER_CASE = 5
DEFAULT_MIN_CASES = 40


@dataclass(frozen=True)
class ProfileSpec:
    """One row of the profile matrix — the strategist-visible fields that vary."""

    slug: str
    goal: str
    target_role: str
    target_level: str
    experience_level: ExperienceLevel
    timeline_weeks: int
    weekly_hours: float
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    companies: tuple[str, ...] = ()


_EVENING = (
    DeepWorkWindow(day=Day.MON, start="18:00", end="21:00"),
    DeepWorkWindow(day=Day.WED, start="19:00", end="21:30"),
)
_MORNING = (
    DeepWorkWindow(day=Day.TUE, start="07:00", end="09:00"),
    DeepWorkWindow(day=Day.THU, start="07:00", end="09:00"),
    DeepWorkWindow(day=Day.SAT, start="09:00", end="12:00"),
)
_WEEKEND = (
    DeepWorkWindow(day=Day.SAT, start="10:00", end="14:00"),
    DeepWorkWindow(day=Day.SUN, start="10:00", end="13:00"),
)

_BEG = ExperienceLevel.BEGINNER
_INT = ExperienceLevel.INTERMEDIATE
_ADV = ExperienceLevel.ADVANCED

#: Cases per track follow the servable-claim supply measured on
#: snap_0217291f46e331b9 at k=10 (swe 21, ai_engineer 11, quant_dev 11,
#: product_manager 8, data_scientist 3, mle 2 claims ≥0.30). data_analyst /
#: data_engineer have no servable claims on that snapshot — every one of their
#: documents has aged past its source-type expiry — so they carry no rows
#: here; add rows when a refreshed snapshot serves them.
_PROFILE_MATRIX: dict[CareerTrack, tuple[ProfileSpec, ...]] = {
    CareerTrack.SWE: (
        ProfileSpec(
            "backend_ng",
            "Backend SWE interview prep",
            "Backend SWE",
            "new_grad",
            _INT,
            10,
            8,
            ("arrays", "hash maps"),
            ("system design", "behavioral interviews"),
            ("Uber",),
        ),
        ProfileSpec(
            "backend_mid",
            "Move from IC2 to a senior backend role",
            "Senior Backend Engineer",
            "senior",
            _ADV,
            8,
            6,
            ("distributed systems", "Go"),
            ("system design at scale", "leadership stories"),
            ("Stripe",),
        ),
        ProfileSpec(
            "frontend_ng",
            "Land a first frontend job",
            "Frontend Developer",
            "new_grad",
            _BEG,
            16,
            10,
            ("HTML/CSS",),
            ("data structures", "JavaScript async", "system design"),
            (),
        ),
        ProfileSpec(
            "fullstack_career_change",
            "Career change into full-stack engineering",
            "Full Stack Developer",
            "junior",
            _BEG,
            20,
            12,
            ("SQL", "communication"),
            ("algorithms", "system design", "testing"),
            (),
        ),
        ProfileSpec(
            "platform_mid",
            "Platform engineering interviews",
            "Platform Engineer",
            "mid",
            _INT,
            6,
            5,
            ("Kubernetes", "CI/CD"),
            ("coding interviews", "system design"),
            ("Datadog",),
        ),
        ProfileSpec(
            "sre_mid",
            "Site reliability interviews",
            "Site Reliability Engineer",
            "mid",
            _INT,
            8,
            7,
            ("Linux", "incident response"),
            ("coding interviews", "distributed systems theory"),
            ("Cloudflare",),
        ),
        ProfileSpec(
            "backend_intern",
            "Backend internship interviews",
            "Backend SWE Intern",
            "intern",
            _BEG,
            12,
            9,
            ("Python",),
            ("data structures", "behavioral interviews"),
            (),
        ),
        ProfileSpec(
            "fullstack_senior",
            "Staff-level full-stack loop",
            "Staff Software Engineer",
            "staff",
            _ADV,
            6,
            4,
            ("system design", "mentoring"),
            ("coding under time pressure", "behavioral interviews"),
            ("Airbnb",),
        ),
        ProfileSpec(
            "devops_junior",
            "DevOps engineer interviews",
            "DevOps Engineer",
            "junior",
            _INT,
            10,
            6,
            ("Docker", "bash"),
            ("algorithms", "networking fundamentals"),
            (),
        ),
        ProfileSpec(
            "backend_faang",
            "Big-tech backend loop in eight weeks",
            "Software Engineer",
            "mid",
            _INT,
            8,
            10,
            ("graphs", "dynamic programming"),
            ("system design", "behavioral interviews"),
            ("Google", "Meta"),
        ),
    ),
    CareerTrack.AI_ENGINEER: (
        ProfileSpec(
            "aie_ng",
            "AI engineer roles building LLM products",
            "AI Engineer",
            "new_grad",
            _INT,
            10,
            8,
            ("Python", "REST APIs"),
            ("evaluation of LLM systems", "retrieval augmented generation", "system design"),
            (),
        ),
        ProfileSpec(
            "aie_mid",
            "Move from backend to applied AI engineering",
            "Applied AI Engineer",
            "mid",
            _INT,
            8,
            6,
            ("backend services", "SQL"),
            ("prompt engineering", "vector search", "model evaluation"),
            ("Anthropic",),
        ),
        ProfileSpec(
            "aie_senior",
            "Senior AI engineering loop",
            "Senior AI Engineer",
            "senior",
            _ADV,
            6,
            5,
            ("distributed systems", "LLM APIs"),
            ("agent architectures", "cost and latency tradeoffs"),
            (),
        ),
        ProfileSpec(
            "genai_career_change",
            "Career change into generative AI engineering",
            "GenAI Engineer",
            "junior",
            _BEG,
            20,
            12,
            ("data analysis",),
            ("coding interviews", "machine learning fundamentals", "LLM application design"),
            (),
        ),
        ProfileSpec(
            "llm_platform",
            "LLM platform engineering interviews",
            "LLM Platform Engineer",
            "mid",
            _INT,
            8,
            7,
            ("Kubernetes", "Python"),
            ("inference optimization", "evaluation pipelines"),
            ("OpenAI",),
        ),
        ProfileSpec(
            "aie_intern",
            "AI engineering internship",
            "AI Engineering Intern",
            "intern",
            _BEG,
            12,
            9,
            ("Python",),
            ("data structures", "retrieval augmented generation"),
            (),
        ),
        ProfileSpec(
            "aie_research_to_eng",
            "Research engineer to product AI engineer",
            "AI Engineer",
            "mid",
            _ADV,
            6,
            5,
            ("PyTorch", "experiment design"),
            ("production systems", "system design", "behavioral interviews"),
            (),
        ),
        ProfileSpec(
            "aie_startup",
            "Startup AI engineer generalist",
            "Founding AI Engineer",
            "senior",
            _ADV,
            4,
            8,
            ("full-stack", "LLM APIs"),
            ("evaluation of LLM systems", "scaling retrieval"),
            (),
        ),
    ),
    CareerTrack.QUANT_DEV: (
        ProfileSpec(
            "quant_ng",
            "Quant developer interviews",
            "Quant Developer",
            "new_grad",
            _INT,
            12,
            10,
            ("C++", "probability"),
            ("low-latency systems", "brainteasers", "behavioral interviews"),
            ("Jane Street",),
        ),
        ProfileSpec(
            "quant_mid",
            "Move from backend to quant development",
            "Quantitative Developer",
            "mid",
            _INT,
            10,
            7,
            ("Python", "distributed systems"),
            ("C++ performance", "statistics", "market microstructure"),
            (),
        ),
        ProfileSpec(
            "quant_senior",
            "Senior quant dev loop",
            "Senior Quant Developer",
            "senior",
            _ADV,
            6,
            5,
            ("C++", "linux internals"),
            ("probability puzzles", "system design"),
            ("Citadel",),
        ),
        ProfileSpec(
            "quant_intern",
            "Quant developer internship",
            "Quant Developer Intern",
            "intern",
            _BEG,
            14,
            9,
            ("Python", "linear algebra"),
            ("C++", "probability", "coding under time pressure"),
            (),
        ),
        ProfileSpec(
            "quant_phd",
            "PhD to quant developer",
            "Quantitative Developer",
            "new_grad",
            _ADV,
            8,
            8,
            ("numerical methods", "research"),
            ("software engineering practices", "coding interviews"),
            ("Two Sigma",),
        ),
        ProfileSpec(
            "quant_lowlat",
            "Low-latency trading systems roles",
            "Low Latency Developer",
            "mid",
            _ADV,
            6,
            6,
            ("C++", "networking"),
            ("probability", "behavioral interviews"),
            (),
        ),
        ProfileSpec(
            "quant_career_change",
            "Career change into quant development",
            "Quant Developer",
            "junior",
            _BEG,
            20,
            12,
            ("mathematics",),
            ("C++", "data structures", "system design"),
            (),
        ),
        ProfileSpec(
            "quant_python",
            "Python-first quant dev roles",
            "Quant Developer",
            "mid",
            _INT,
            8,
            6,
            ("pandas", "statistics"),
            ("C++", "concurrency", "brainteasers"),
            (),
        ),
    ),
    CareerTrack.PRODUCT_MANAGER: (
        ProfileSpec(
            "pm_apm",
            "Associate product manager programs",
            "Associate Product Manager",
            "new_grad",
            _BEG,
            12,
            8,
            ("communication", "SQL"),
            ("product sense", "estimation questions", "execution interviews"),
            ("Google",),
        ),
        ProfileSpec(
            "pm_eng_to_pm",
            "Engineer to product manager",
            "Product Manager",
            "mid",
            _INT,
            10,
            6,
            ("technical depth", "system design"),
            ("product sense", "metrics and analytics", "behavioral interviews"),
            (),
        ),
        ProfileSpec(
            "pm_senior",
            "Senior PM loop",
            "Senior Product Manager",
            "senior",
            _ADV,
            6,
            5,
            ("roadmapping", "stakeholder management"),
            ("strategy questions", "case interviews"),
            ("Meta",),
        ),
        ProfileSpec(
            "pm_platform",
            "Platform PM interviews",
            "Platform Product Manager",
            "mid",
            _INT,
            8,
            7,
            ("APIs", "developer experience"),
            ("product sense", "execution interviews"),
            (),
        ),
        ProfileSpec(
            "pm_growth",
            "Growth PM interviews",
            "Growth Product Manager",
            "mid",
            _INT,
            8,
            6,
            ("experimentation", "SQL"),
            ("product sense", "estimation questions"),
            (),
        ),
        ProfileSpec(
            "pm_career_change",
            "Career change into product management",
            "Product Manager",
            "junior",
            _BEG,
            16,
            10,
            ("customer research",),
            ("metrics and analytics", "technical fundamentals", "execution interviews"),
            (),
        ),
    ),
    CareerTrack.DATA_SCIENTIST: (
        ProfileSpec(
            "ds_ng",
            "Data scientist interviews",
            "Data Scientist",
            "new_grad",
            _INT,
            10,
            8,
            ("Python", "statistics"),
            ("SQL interviews", "product case questions", "machine learning fundamentals"),
            (),
        ),
        ProfileSpec(
            "ds_mid",
            "Senior data scientist loop",
            "Senior Data Scientist",
            "senior",
            _ADV,
            8,
            6,
            ("experimentation", "causal inference"),
            ("coding interviews", "machine learning system design"),
            ("Netflix",),
        ),
        ProfileSpec(
            "ds_analyst_to_ds",
            "Analyst to data scientist",
            "Data Scientist",
            "junior",
            _INT,
            14,
            9,
            ("SQL", "dashboards"),
            ("statistics", "machine learning fundamentals", "Python"),
            (),
        ),
        ProfileSpec(
            "ds_phd",
            "PhD to industry data science",
            "Data Scientist",
            "new_grad",
            _ADV,
            8,
            7,
            ("research", "modeling"),
            ("SQL interviews", "product case questions", "behavioral interviews"),
            (),
        ),
    ),
    CareerTrack.MLE: (
        ProfileSpec(
            "mle_ng",
            "ML engineer interviews",
            "Machine Learning Engineer",
            "new_grad",
            _INT,
            12,
            10,
            ("PyTorch", "Python"),
            ("ML system design", "coding interviews", "behavioral interviews"),
            (),
        ),
        ProfileSpec(
            "mle_mid",
            "Backend to ML engineering",
            "Machine Learning Engineer",
            "mid",
            _INT,
            10,
            7,
            ("distributed systems", "Python"),
            ("deep learning fundamentals", "ML system design"),
            ("Uber",),
        ),
        ProfileSpec(
            "mle_senior",
            "Senior MLE loop",
            "Senior ML Engineer",
            "senior",
            _ADV,
            6,
            5,
            ("model training", "feature pipelines"),
            ("ML system design at scale", "leadership stories"),
            (),
        ),
        ProfileSpec(
            "mle_intern",
            "ML engineering internship",
            "ML Engineer Intern",
            "intern",
            _BEG,
            14,
            9,
            ("Python", "linear algebra"),
            ("data structures", "deep learning fundamentals"),
            (),
        ),
    ),
}

_PROFILE_STAMP = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)


def _profile(track: CareerTrack, spec: ProfileSpec, ordinal: int) -> UserProfile:
    windows = (_EVENING, _MORNING, _WEEKEND)[ordinal % 3]
    session = (60, 90, 45)[ordinal % 3]
    return UserProfile(
        user_id="user_eval",
        profile_version=f"profile_eval_v10_{track.value}_{spec.slug}",
        goal=spec.goal,
        target_role=spec.target_role,
        target_companies=list(spec.companies),
        target_level=spec.target_level,
        timeline_weeks=spec.timeline_weeks,
        weekly_hours=spec.weekly_hours,
        experience_level=spec.experience_level,
        known_strengths=list(spec.strengths),
        known_weaknesses=list(spec.weaknesses),
        preferred_session_length_min=session,
        max_session_length_min=session * 2,
        deep_work_windows=list(windows),
        hard_constraints=HardConstraints(
            no_events_before="08:00" if ordinal % 3 != 1 else "06:30",
            no_events_after="22:30",
            allow_weekends=ordinal % 2 == 0,
            max_daily_study_min=180,
            min_break_between_deep_blocks_min=30,
        ),
        preferences=Preferences(
            prefer_evening_sessions=ordinal % 3 == 0,
            prefer_weekend_long_blocks=ordinal % 3 == 2,
            avoid_back_to_back_deep_work=True,
        ),
        created_at=_PROFILE_STAMP,
        updated_at=_PROFILE_STAMP,
    )


def _claim_window(claims: list[SourceClaim], ordinal: int, size: int) -> list[SourceClaim]:
    """Rotating wrap-around slice: consecutive cases see different claim sets."""
    if not claims:
        return []
    size = min(size, len(claims))
    start = (ordinal * size) % len(claims)
    return [claims[(start + i) % len(claims)] for i in range(size)]


def servable_claims_by_track(
    *,
    queries: Path,
    manifest_path: Path,
    corpus_db: Path,
    snapshot_id: str,
    k: int,
    as_of: date,
    min_confidence: float,
) -> dict[CareerTrack, list[SourceClaim]]:
    """The sanctioned claim pipeline, scored against a throwaway store."""
    query_set = load_claim_queries(queries).model_copy(update={"k": k})
    manifest = load_manifest(manifest_path)
    db = SqliteDatabase(corpus_db)
    registry = SqliteCorpusRegistry(db)
    snapshot = registry.get_snapshot(snapshot_id)
    if snapshot is None:
        raise ValueError(f"snapshot {snapshot_id!r} is not in {corpus_db}")
    index = SqliteChunkIndex(db)
    index.build(registry, snapshot)
    report = assemble_claims(
        registry=registry,
        index=index,
        snapshot_id=snapshot.snapshot_id,
        query_set=query_set,
        manifest=manifest,
    )
    clock = FrozenClock(datetime(as_of.year, as_of.month, as_of.day, 12, 0, tzinfo=UTC))
    outcomes = ingest_assembled(
        report.claims, store=InMemorySourceClaimStore(), manifest=manifest, clock=clock
    )
    by_track: dict[CareerTrack, list[SourceClaim]] = defaultdict(list)
    for assembled, outcome in outcomes:
        if outcome.status is not ClaimIngestionStatus.INGESTED or outcome.claim is None:
            continue
        if outcome.claim.confidence_score < min_confidence:
            continue
        by_track[assembled.track].append(outcome.claim)
    return dict(by_track)


def build_eval_set(
    *,
    version: str,
    claims_by_track: dict[CareerTrack, list[SourceClaim]],
    claims_per_case: int,
    snapshot_id: str,
    k: int,
    as_of: date,
) -> tuple[EvalSet, list[CareerTrack]]:
    """Pair the profile matrix with claim windows; returns the set and the
    tracks skipped for having no servable claims."""
    cases: list[EvalCase] = []
    skipped: list[CareerTrack] = []
    for track, specs in _PROFILE_MATRIX.items():
        claims = claims_by_track.get(track, [])
        if not claims:
            skipped.append(track)
            continue
        for ordinal, spec in enumerate(specs):
            window = _claim_window(claims, ordinal, claims_per_case)
            cases.append(
                EvalCase(
                    case_id=f"strategist_{track.value}_{spec.slug}_grounded",
                    node=LlmNodeName.STRATEGIST,
                    description=(
                        f"{spec.target_role} ({spec.target_level}, "
                        f"{spec.experience_level.value}) with {len(window)} "
                        f"corpus-derived claims from {snapshot_id} (k={k}, "
                        f"as-of {as_of.isoformat()}, window {ordinal}) — "
                        f"grounded arm, v10 coverage set."
                    ),
                    inputs={
                        "user_profile": _profile(track, spec, ordinal).model_dump(mode="json"),
                        "source_claims": [c.model_dump(mode="json") for c in window],
                    },
                )
            )
    return EvalSet(eval_set_version=version, cases=cases), skipped


def render(eval_set: EvalSet) -> str:
    return json.dumps(eval_set.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a grounded strategist eval set from the pinned corpus (offline)."
    )
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--corpus-db", type=Path, required=True)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--k", type=int, required=True, help="Retrieval k override.")
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--version", default="v10")
    parser.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)
    parser.add_argument("--claims-per-case", type=int, default=DEFAULT_CLAIMS_PER_CASE)
    parser.add_argument("--min-cases", type=int, default=DEFAULT_MIN_CASES)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Regenerate and compare against --out; exit 1 on drift, write nothing.",
    )
    args = parser.parse_args(argv)

    try:
        claims_by_track = servable_claims_by_track(
            queries=args.queries,
            manifest_path=args.manifest,
            corpus_db=args.corpus_db,
            snapshot_id=args.snapshot,
            k=args.k,
            as_of=args.as_of,
            min_confidence=args.min_confidence,
        )
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    eval_set, skipped = build_eval_set(
        version=args.version,
        claims_by_track=claims_by_track,
        claims_per_case=args.claims_per_case,
        snapshot_id=args.snapshot,
        k=args.k,
        as_of=args.as_of,
    )
    for track in skipped:
        print(f"skipped {track.value}: no servable claims on this snapshot", file=sys.stderr)
    for track, claims in sorted(claims_by_track.items(), key=lambda kv: kv[0].value):
        print(f"{track.value}: {len(claims)} servable claims", file=sys.stderr)
    if len(eval_set.cases) < args.min_cases:
        print(
            f"error: only {len(eval_set.cases)} grounded cases; --min-cases is "
            f"{args.min_cases} (claim supply shrank?)",
            file=sys.stderr,
        )
        return 1

    text = render(eval_set)
    if args.check:
        current: str | None = args.out.read_text(encoding="utf-8") if args.out.exists() else None
        if current != text:
            print(f"drift: {args.out} does not match regeneration", file=sys.stderr)
            return 1
        print(f"{args.out} is up to date ({len(eval_set.cases)} cases)", file=sys.stderr)
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {args.out} ({len(eval_set.cases)} grounded cases)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
