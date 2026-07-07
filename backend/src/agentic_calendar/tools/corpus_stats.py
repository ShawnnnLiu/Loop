"""Corpus + claim-store freshness stats (grounding-RAG G-I).

Usage::

    # Corpus side only: doc age distribution per track, snapshot ages.
    uv run python -m agentic_calendar.tools.corpus_stats \\
        --corpus-db corpus/corpus.db

    # Claims side too: expired / stale-window shares per source type and,
    # via the corpus join, per track.
    ... --app-db dogfood.db
    ... --json

The freshness *machinery* has existed since Phase 5 — expiry stamps, the
inclusive ``is_expired`` boundary, the stale-penalty ramp (axiom 08 priors).
This tool is the missing *report*: "is the corpus decaying, and does the
operator know?". It computes, it never mutates — the refresh loop stays
manual and gated (re-run ``ingest_corpus`` + ``refresh_claims`` when these
numbers say so; no cron, no automation in v1).

Definitions (all reusing the shipped priors, never re-declaring them):

* a claim is **expired** when ``expires_at <= today`` (the inclusive
  boundary shared by every expiry in the system);
* a claim is in the **stale window** when it is not expired but within
  ``ConfidencePriors.stale_ramp_days`` (default 30) of expiry — exactly the
  span where the scorer's ``stale_penalty`` ramps;
* a **track is decaying** when more than ``DECAY_STALE_SHARE_THRESHOLD`` of
  its claims are expired-or-stale. That threshold is a **heuristic prior**
  in the axiom 08 sense — chosen to be plausible (half the evidence base
  old means refresh), not derived from data, and uncalibrated until claims
  accumulate.

Claims do not carry a track: the per-track view joins each claim's document
URL (its ``source_url`` minus the ``#fragment`` breadcrumb that claim
assembly appends) to the registered corpus documents' ``track_tags``. A
document tagged with several tracks counts its claims toward each; claims
whose URL matches no registered document report as ``unmapped``.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from agentic_calendar.common.clock import Clock, SystemClock
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.source_claim import SourceClaim
from agentic_calendar.retrieval import SqliteCorpusRegistry
from agentic_calendar.source_claims.priors import DEFAULT_CONFIDENCE_PRIORS
from agentic_calendar.source_claims.sqlite_store import SqliteSourceClaimStore

#: Share of expired-or-stale claims above which a track counts as decaying.
#: Heuristic prior (axiom 08 "Freshness Monitoring"), not a tuned value.
DECAY_STALE_SHARE_THRESHOLD = 0.50


# --------------------------------------------------------------------------- #
# Report shapes (dataclasses so ``--json`` is one ``asdict`` away).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FreshnessCounts:
    """Expired / stale-window / fresh split of one group of claims."""

    total: int
    expired: int
    stale_window: int
    fresh: int

    @property
    def stale_or_expired_share(self) -> float:
        """Share of claims expired or inside the stale-penalty window."""
        if self.total == 0:
            return 0.0
        return (self.expired + self.stale_window) / self.total


@dataclass(frozen=True)
class TrackClaimFreshness:
    """Freshness of one track's claims plus the decay-flag verdict."""

    track: str
    counts: FreshnessCounts
    decaying: bool


@dataclass(frozen=True)
class ClaimsReport:
    """Claim-store freshness: overall, per source type, per track."""

    overall: FreshnessCounts
    by_source_type: dict[str, FreshnessCounts]
    by_track: list[TrackClaimFreshness]
    unmapped_claims: int


@dataclass(frozen=True)
class AgeDistribution:
    """Min / median / max age in days over one group of dates."""

    count: int
    min_days: int
    median_days: float
    max_days: int


@dataclass(frozen=True)
class TrackCorpusStats:
    """One track's document count and age distributions."""

    track: str
    documents: int
    collected_age: AgeDistribution
    published_age: AgeDistribution | None


@dataclass(frozen=True)
class CorpusReport:
    """Corpus-registry side: documents per track and snapshot ages."""

    documents: int
    snapshots: int
    oldest_snapshot_age_days: int | None
    newest_snapshot_age_days: int | None
    by_track: list[TrackCorpusStats]


# --------------------------------------------------------------------------- #
# Computation (pure given the stores' contents and ``today``).
# --------------------------------------------------------------------------- #


def _classify_claim(claim: SourceClaim, *, today: date) -> str:
    """``expired`` / ``stale_window`` / ``fresh`` for one claim at ``today``."""
    if claim.expires_at <= today:
        return "expired"
    days_to_expiry = (claim.expires_at - today).days
    if days_to_expiry <= DEFAULT_CONFIDENCE_PRIORS.stale_ramp_days:
        return "stale_window"
    return "fresh"


def _counts_for(claims: list[SourceClaim], *, today: date) -> FreshnessCounts:
    states = [_classify_claim(claim, today=today) for claim in claims]
    return FreshnessCounts(
        total=len(claims),
        expired=states.count("expired"),
        stale_window=states.count("stale_window"),
        fresh=states.count("fresh"),
    )


def document_url_of(claim_source_url: str) -> str:
    """The claim's document URL: ``source_url`` minus the breadcrumb fragment."""
    return claim_source_url.split("#", 1)[0]


def build_claims_report(
    claims: list[SourceClaim],
    *,
    today: date,
    tracks_by_document_url: dict[str, set[str]] | None,
) -> ClaimsReport:
    """Freshness split overall, per source type, and (when joinable) per track.

    ``tracks_by_document_url`` is the corpus join (``None`` when no corpus
    database was given — the per-track view is then empty and every claim
    counts as unmapped).
    """
    by_source_type: dict[str, list[SourceClaim]] = defaultdict(list)
    for claim in claims:
        by_source_type[claim.source_type.value].append(claim)

    by_track: dict[str, list[SourceClaim]] = defaultdict(list)
    unmapped = 0
    for claim in claims:
        tracks = (tracks_by_document_url or {}).get(document_url_of(claim.source_url))
        if not tracks:
            unmapped += 1
            continue
        for track in tracks:
            by_track[track].append(claim)

    track_rows = []
    for track in sorted(by_track):
        counts = _counts_for(by_track[track], today=today)
        track_rows.append(
            TrackClaimFreshness(
                track=track,
                counts=counts,
                decaying=counts.stale_or_expired_share > DECAY_STALE_SHARE_THRESHOLD,
            )
        )
    return ClaimsReport(
        overall=_counts_for(claims, today=today),
        by_source_type={
            name: _counts_for(group, today=today)
            for name, group in sorted(by_source_type.items())
        },
        by_track=track_rows,
        unmapped_claims=unmapped,
    )


def _age_distribution(dates: list[date], *, today: date) -> AgeDistribution:
    ages = sorted((today - value).days for value in dates)
    return AgeDistribution(
        count=len(ages),
        min_days=ages[0],
        median_days=float(statistics.median(ages)),
        max_days=ages[-1],
    )


def build_corpus_report(registry: SqliteCorpusRegistry, *, today: date) -> CorpusReport:
    """Document ages per track and snapshot ages, straight off the registry."""
    documents = registry.list_documents()
    snapshots = registry.list_snapshots()
    snapshot_ages = sorted((today - s.created_at.date()).days for s in snapshots)

    by_track: dict[str, list[tuple[date, date | None]]] = defaultdict(list)
    for document in documents:
        for tag in document.track_tags:
            by_track[tag.value].append(
                (document.date_collected, document.source_published_date)
            )

    track_rows = []
    for track in sorted(by_track):
        collected = [c for c, _ in by_track[track]]
        published = [p for _, p in by_track[track] if p is not None]
        track_rows.append(
            TrackCorpusStats(
                track=track,
                documents=len(collected),
                collected_age=_age_distribution(collected, today=today),
                published_age=(
                    _age_distribution(published, today=today) if published else None
                ),
            )
        )
    return CorpusReport(
        documents=len(documents),
        snapshots=len(snapshots),
        oldest_snapshot_age_days=snapshot_ages[-1] if snapshot_ages else None,
        newest_snapshot_age_days=snapshot_ages[0] if snapshot_ages else None,
        by_track=track_rows,
    )


# --------------------------------------------------------------------------- #
# Rendering.
# --------------------------------------------------------------------------- #


def _pct(share: float) -> str:
    return f"{share * 100:.1f}%"


def _freshness_line(counts: FreshnessCounts) -> str:
    return (
        f"{counts.total} claims — {counts.expired} expired, "
        f"{counts.stale_window} in the "
        f"{DEFAULT_CONFIDENCE_PRIORS.stale_ramp_days}d stale window, "
        f"{counts.fresh} fresh ({_pct(counts.stale_or_expired_share)} stale-or-expired)"
    )


def _age_line(ages: AgeDistribution) -> str:
    return f"min/median/max {ages.min_days}/{ages.median_days:.0f}/{ages.max_days}d"


def _print_corpus(report: CorpusReport) -> None:
    if report.oldest_snapshot_age_days is None:
        snapshot_note = "no snapshots"
    else:
        snapshot_note = (
            f"newest {report.newest_snapshot_age_days}d old, "
            f"oldest {report.oldest_snapshot_age_days}d old"
        )
    print(
        f"corpus: {report.documents} documents, "
        f"{report.snapshots} snapshot(s) ({snapshot_note})"
    )
    for row in report.by_track:
        published = (
            f"published age {_age_line(row.published_age)} "
            f"({row.published_age.count}/{row.documents} dated)"
            if row.published_age is not None
            else f"published date unknown for all {row.documents}"
        )
        print(
            f"  {row.track}: {row.documents} docs — collected age "
            f"{_age_line(row.collected_age)}; {published}"
        )


def _print_claims(report: ClaimsReport) -> None:
    print(f"claims: {_freshness_line(report.overall)}")
    for name, counts in report.by_source_type.items():
        print(f"  {name}: {_freshness_line(counts)}")
    if report.by_track:
        print("claims by track (via corpus join; multi-track docs count in each):")
        for row in report.by_track:
            flag = "  DECAYING — re-run ingest_corpus + refresh_claims" if row.decaying else ""
            print(f"  {row.track}: {_freshness_line(row.counts)}{flag}")
    if report.unmapped_claims:
        print(
            f"  unmapped: {report.unmapped_claims} claim(s) with no registered "
            f"corpus document (no track attribution)"
        )
    decaying = [row.track for row in report.by_track if row.decaying]
    print(
        f"decay flag (heuristic prior: >{_pct(DECAY_STALE_SHARE_THRESHOLD)} "
        f"stale-or-expired): {', '.join(decaying) if decaying else 'no track decaying'}"
    )


# --------------------------------------------------------------------------- #
# CLI.
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None, *, clock: Clock | None = None) -> int:
    """CLI entry point. ``clock`` is injectable for tests."""
    parser = argparse.ArgumentParser(
        description=(
            "Report corpus and claim-store freshness: doc/snapshot ages per "
            "track, expired and stale-window claim shares per source type "
            "and track. Read-only; the refresh loop stays manual and gated."
        )
    )
    parser.add_argument(
        "--corpus-db", type=Path, default=None, help="Corpus SQLite database."
    )
    parser.add_argument(
        "--app-db",
        type=Path,
        default=None,
        help="App SQLite database whose claim store is reported.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emit the report as JSON instead of human-readable text.",
    )
    args = parser.parse_args(argv)

    if args.corpus_db is None and args.app_db is None:
        print("error: give --corpus-db and/or --app-db", file=sys.stderr)
        return 1
    for label, path in (("corpus", args.corpus_db), ("app", args.app_db)):
        if path is not None and not path.exists():
            print(f"error: {label} database not found: {path}", file=sys.stderr)
            return 1

    today = (clock if clock is not None else SystemClock()).now().date()

    corpus_report: CorpusReport | None = None
    tracks_by_document_url: dict[str, set[str]] | None = None
    if args.corpus_db is not None:
        registry = SqliteCorpusRegistry(SqliteDatabase(args.corpus_db))
        corpus_report = build_corpus_report(registry, today=today)
        tracks_by_document_url = defaultdict[str, set[str]](set)
        for document in registry.list_documents():
            tracks_by_document_url[document.source_url].update(
                tag.value for tag in document.track_tags
            )

    claims_report: ClaimsReport | None = None
    if args.app_db is not None:
        store = SqliteSourceClaimStore(SqliteDatabase(args.app_db))
        claims_report = build_claims_report(
            store.all(), today=today, tracks_by_document_url=tracks_by_document_url
        )

    if args.emit_json:
        payload = {
            "as_of": today.isoformat(),
            "stale_window_days": DEFAULT_CONFIDENCE_PRIORS.stale_ramp_days,
            "decay_stale_share_threshold": DECAY_STALE_SHARE_THRESHOLD,
            "corpus": dataclasses.asdict(corpus_report) if corpus_report else None,
            "claims": dataclasses.asdict(claims_report) if claims_report else None,
        }
        print(json.dumps(payload, indent=2))
        return 0

    if corpus_report is not None:
        _print_corpus(corpus_report)
    if claims_report is not None:
        _print_claims(claims_report)
    print(
        "note: the stale window and the decay threshold are heuristic priors "
        "(axiom 08), uncalibrated until the calibration pass"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
