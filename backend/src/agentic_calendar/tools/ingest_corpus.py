"""Ingest corpus documents from a hand-curated source manifest.

Usage::

    uv run python -m agentic_calendar.tools.ingest_corpus \\
        --manifest corpus/manifest_v1.json --db dogfood.db [--dry-run] \\
        [--max-fetches 100] [--timeout 20] [--snapshot] \\
        [--chunk-target-chars 1600] [--chunk-overlap-chars 200]

Curation lives in the manifest, in review — not in crawler heuristics. The
tool fetches **exactly** the manifest's URLs (no crawling, no link
following), normalizes deterministically, and registers each document in the
:class:`~agentic_calendar.retrieval.SqliteCorpusRegistry`; re-running on
unchanged pages is a no-op (hash-idempotent). ``--dry-run`` prints what would
be fetched/registered and touches neither the network nor the database.

A live run is a networked command: per the operating contract the operator
confirms each run explicitly. Guardrails: robots.txt is respected, every
request carries a per-request timeout, and a per-run fetch cap bounds the
blast radius (the capture tool's cap discipline).

``source_type`` comes from the **existing** deterministic classifier
(``source_claims/classification.py``) with the manifest's declared host
context; the manifest's ``expected_type`` is the curator's assertion and is
cross-checked — a mismatch is reported loudly, and the classifier wins.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import (
    CorpusDocument,
    content_hash_for,
    derive_doc_id,
)
from agentic_calendar.contracts.corpus_snapshot import ChunkingParams
from agentic_calendar.contracts.source_claim import SourceType
from agentic_calendar.retrieval import (
    DEFAULT_CHUNKING_PARAMS,
    CorpusDocumentConflictError,
    CorpusRegistry,
    SqliteCorpusRegistry,
    normalize_fetched_text,
)
from agentic_calendar.source_claims.classification import classify_source

MANIFEST_VERSION = "corpus-manifest-v1"

_USER_AGENT = "agentic-calendar-corpus-ingest/1.0"
_DEFAULT_TIMEOUT_SECONDS = 20.0
_DEFAULT_MAX_FETCHES = 100


# --------------------------------------------------------------------------- #
# Manifest models (tool-local, like the eval-set models: operator input, not
# a cross-region contract — the registry's CorpusDocument is the contract).
# --------------------------------------------------------------------------- #


class ManifestSource(BaseModel):
    """One curated URL: what to fetch and the metadata review signed off on."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    url: str = Field(min_length=1)
    expected_type: SourceType
    track_tags: list[CareerTrack] = Field(min_length=1)
    license_note: str = Field(min_length=1)
    title: str = Field(min_length=1)
    published_date: date | None = None
    comment: str | None = None


class CorpusManifest(BaseModel):
    """The checked-in, review-curated fetch list plus classifier host context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_version: Literal["corpus-manifest-v1"]
    comment: str | None = None
    known_company_domains: list[str] = Field(default_factory=list)
    engineering_blog_hosts: list[str] = Field(default_factory=list)
    personal_blog_hosts: list[str] = Field(default_factory=list)
    sources: list[ManifestSource] = Field(min_length=1)

    def classify(self, url: str) -> SourceType:
        """Classify through the existing kernel rules with declared context."""
        return classify_source(
            url,
            known_company_domains=frozenset(self.known_company_domains),
            engineering_blog_hosts=frozenset(self.engineering_blog_hosts),
            personal_blog_hosts=frozenset(self.personal_blog_hosts),
        )


def load_manifest(path: Path) -> CorpusManifest:
    """Load and contract-validate a manifest file (raises on invalid)."""
    return CorpusManifest.model_validate(json.loads(path.read_text("utf-8")))


# --------------------------------------------------------------------------- #
# Fetching (injectable so tests never touch the network).
# --------------------------------------------------------------------------- #


class FetchStatus(StrEnum):
    OK = "ok"
    ROBOTS_DISALLOWED = "robots_disallowed"
    FETCH_FAILED = "fetch_failed"


@dataclass(frozen=True)
class FetchOutcome:
    status: FetchStatus
    text: str | None = None
    error: str | None = None


class Fetcher(Protocol):
    def fetch(self, url: str) -> FetchOutcome: ...


#: Returns (body bytes, declared charset or None). Injectable for tests.
UrlOpener = Callable[[str, float, str], tuple[bytes, str | None]]


def _default_open(url: str, timeout: float, user_agent: str) -> tuple[bytes, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset: str | None = response.headers.get_content_charset()
        return response.read(), charset


class UrllibFetcher:
    """stdlib fetcher: robots.txt respected, per-request timeout, no retries.

    robots.txt is fetched once per host and cached for the run. A robots file
    that cannot be fetched is treated as absent (allow) — the conventional
    reading; the per-source report still records every fetch failure of the
    document itself.
    """

    def __init__(
        self,
        *,
        timeout: float = _DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = _USER_AGENT,
        opener: UrlOpener = _default_open,
    ) -> None:
        self._timeout = timeout
        self._user_agent = user_agent
        self._opener = opener
        self._robots: dict[str, RobotFileParser] = {}

    def fetch(self, url: str) -> FetchOutcome:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return FetchOutcome(
                status=FetchStatus.FETCH_FAILED,
                error=f"unsupported URL (need http/https): {url!r}",
            )
        if not self._robots_allow(parts.scheme, parts.netloc, url):
            return FetchOutcome(status=FetchStatus.ROBOTS_DISALLOWED)
        try:
            body, charset = self._opener(url, self._timeout, self._user_agent)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return FetchOutcome(status=FetchStatus.FETCH_FAILED, error=str(exc))
        return FetchOutcome(
            status=FetchStatus.OK,
            text=body.decode(charset or "utf-8", errors="replace"),
        )

    def _robots_allow(self, scheme: str, netloc: str, url: str) -> bool:
        parser = self._robots.get(netloc)
        if parser is None:
            parser = RobotFileParser()
            try:
                body, charset = self._opener(
                    f"{scheme}://{netloc}/robots.txt", self._timeout, self._user_agent
                )
                parser.parse(body.decode(charset or "utf-8", "replace").splitlines())
            except (urllib.error.URLError, OSError, ValueError):
                parser.parse([])  # unreachable robots.txt → allow (absent)
            self._robots[netloc] = parser
        return parser.can_fetch(self._user_agent, url)


# --------------------------------------------------------------------------- #
# Ingestion run.
# --------------------------------------------------------------------------- #


class IngestStatus(StrEnum):
    REGISTERED = "registered"
    UNCHANGED = "unchanged"
    CONFLICT = "conflict"
    FETCH_FAILED = "fetch_failed"
    ROBOTS_DISALLOWED = "robots_disallowed"
    SKIPPED_OVER_CAP = "skipped_over_cap"
    SKIPPED_THIN = "skipped_thin"


#: Statuses that make the run exit non-zero: the operator must act (prune the
#: URL, fix the manifest, or re-fetch on a new day for a changed page). A
#: thin fetch is a failure too: the page fetched but yielded (almost) no
#: text — usually a JS-rendered shell — and registering it would plant a
#: permanently empty document in the append-only registry (the v1 corpus
#: carries exactly one such 0-char document as the cautionary example).
FAILURE_STATUSES: frozenset[IngestStatus] = frozenset(
    {
        IngestStatus.CONFLICT,
        IngestStatus.FETCH_FAILED,
        IngestStatus.ROBOTS_DISALLOWED,
        IngestStatus.SKIPPED_THIN,
    }
)

#: Minimum normalized-text size for registration — a heuristic prior (axiom
#: 08 sense) meant to catch degenerate fetches (0-byte JS shells), not to
#: judge content: the smallest real document in the v1 corpus is 277 chars.
#: ``--min-doc-chars 0`` disables the gate.
DEFAULT_MIN_DOC_CHARS = 200


@dataclass(frozen=True)
class SourceResult:
    url: str
    status: IngestStatus
    expected_type: SourceType
    classified_type: SourceType | None = None
    doc_id: str | None = None
    error: str | None = None

    @property
    def type_mismatch(self) -> bool:
        return (
            self.classified_type is not None
            and self.classified_type is not self.expected_type
        )


@dataclass(frozen=True)
class IngestionReport:
    results: list[SourceResult]
    fetches_attempted: int

    @property
    def status_counts(self) -> Counter[IngestStatus]:
        return Counter(result.status for result in self.results)

    @property
    def type_counts(self) -> Counter[SourceType]:
        return Counter(
            result.classified_type
            for result in self.results
            if result.classified_type is not None
        )

    @property
    def mismatches(self) -> list[SourceResult]:
        return [result for result in self.results if result.type_mismatch]

    @property
    def failed(self) -> bool:
        return any(result.status in FAILURE_STATUSES for result in self.results)


def run_ingestion(
    manifest: CorpusManifest,
    *,
    registry: CorpusRegistry,
    fetcher: Fetcher,
    today: date,
    max_fetches: int,
    min_doc_chars: int = DEFAULT_MIN_DOC_CHARS,
) -> IngestionReport:
    """Fetch and register every manifest source, bounded by ``max_fetches``."""
    results: list[SourceResult] = []
    fetches = 0
    for source in manifest.sources:
        classified = manifest.classify(source.url)
        if fetches >= max_fetches:
            results.append(
                SourceResult(
                    url=source.url,
                    status=IngestStatus.SKIPPED_OVER_CAP,
                    expected_type=source.expected_type,
                    classified_type=classified,
                    error=f"per-run fetch cap ({max_fetches}) reached",
                )
            )
            continue
        fetches += 1
        outcome = fetcher.fetch(source.url)
        if outcome.status is FetchStatus.ROBOTS_DISALLOWED:
            results.append(
                SourceResult(
                    url=source.url,
                    status=IngestStatus.ROBOTS_DISALLOWED,
                    expected_type=source.expected_type,
                    classified_type=classified,
                )
            )
            continue
        if outcome.status is FetchStatus.FETCH_FAILED or outcome.text is None:
            results.append(
                SourceResult(
                    url=source.url,
                    status=IngestStatus.FETCH_FAILED,
                    expected_type=source.expected_type,
                    classified_type=classified,
                    error=outcome.error,
                )
            )
            continue

        text = normalize_fetched_text(outcome.text)
        if len(text) < min_doc_chars:
            results.append(
                SourceResult(
                    url=source.url,
                    status=IngestStatus.SKIPPED_THIN,
                    expected_type=source.expected_type,
                    classified_type=classified,
                    error=(
                        f"normalized text is {len(text)} chars "
                        f"(< {min_doc_chars}); not registered — likely a "
                        "JS-rendered or empty page"
                    ),
                )
            )
            continue
        document = CorpusDocument(
            doc_id=derive_doc_id(source.url, today),
            source_url=source.url,
            source_type=classified,
            license_note=source.license_note,
            date_collected=today,
            source_published_date=source.published_date,
            track_tags=source.track_tags,
            content_hash=content_hash_for(text),
            title=source.title,
        )
        try:
            registered = registry.register(document, text=text)
        except CorpusDocumentConflictError as exc:
            results.append(
                SourceResult(
                    url=source.url,
                    status=IngestStatus.CONFLICT,
                    expected_type=source.expected_type,
                    classified_type=classified,
                    doc_id=document.doc_id,
                    error=str(exc),
                )
            )
            continue
        results.append(
            SourceResult(
                url=source.url,
                status=(
                    IngestStatus.REGISTERED if registered else IngestStatus.UNCHANGED
                ),
                expected_type=source.expected_type,
                classified_type=classified,
                doc_id=document.doc_id,
            )
        )
    return IngestionReport(results=results, fetches_attempted=fetches)


def _print_report(report: IngestionReport) -> None:
    for result in report.results:
        line = f"[{result.status.value}] {result.url}"
        if result.doc_id:
            line += f" -> {result.doc_id} ({result.classified_type})"
        if result.error:
            line += f" — {result.error}"
        print(line)
        if result.type_mismatch:
            print(
                f"[type-mismatch] {result.url}: manifest expected "
                f"{result.expected_type.value!r} but the classifier says "
                f"{result.classified_type.value!r}"  # type: ignore[union-attr]
                " — the classifier wins; fix the manifest or declare the host"
            )
    counts = ", ".join(
        f"{status.value}={count}" for status, count in sorted(report.status_counts.items())
    )
    print(f"summary: {len(report.results)} sources — {counts}")
    if report.type_counts:
        per_type = ", ".join(
            f"{source_type.value}={count}"
            for source_type, count in sorted(report.type_counts.items())
        )
        print(f"by source_type: {per_type}")
    if report.mismatches:
        print(f"type mismatches: {len(report.mismatches)} (see lines above)")


def _print_dry_run(manifest: CorpusManifest, *, today: date, max_fetches: int) -> None:
    for i, source in enumerate(manifest.sources):
        over_cap = " [over fetch cap — would be skipped]" if i >= max_fetches else ""
        classified = manifest.classify(source.url)
        mismatch = (
            f" [type-mismatch: manifest says {source.expected_type.value!r}]"
            if classified is not source.expected_type
            else ""
        )
        tags = ",".join(tag.value for tag in source.track_tags)
        print(
            f"[would-fetch] {source.url} -> {derive_doc_id(source.url, today)} "
            f"({classified.value}; tracks {tags}){mismatch}{over_cap}"
        )
    print(
        f"dry-run: {len(manifest.sources)} sources, cap {max_fetches} — "
        "nothing fetched, nothing registered"
    )


def main(
    argv: list[str] | None = None,
    *,
    fetcher: Fetcher | None = None,
    today: date | None = None,
    now: datetime | None = None,
) -> int:
    """CLI entry point. ``fetcher``/``today``/``now`` are injectable for tests."""
    parser = argparse.ArgumentParser(
        description=(
            "Fetch and register the corpus manifest's URLs (exactly those — "
            "no crawling). Live runs are networked: confirm per the operating "
            "contract, and prefer --dry-run first."
        )
    )
    parser.add_argument(
        "--manifest", type=Path, required=True, help="Path to the manifest JSON."
    )
    parser.add_argument(
        "--db", type=Path, help="SQLite database path (required unless --dry-run)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be fetched/registered; no network, no writes.",
    )
    parser.add_argument(
        "--max-fetches",
        type=int,
        default=_DEFAULT_MAX_FETCHES,
        help=f"Per-run fetch cap (default {_DEFAULT_MAX_FETCHES}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=_DEFAULT_TIMEOUT_SECONDS,
        help=f"Per-request timeout in seconds (default {_DEFAULT_TIMEOUT_SECONDS:g}).",
    )
    parser.add_argument(
        "--min-doc-chars",
        type=int,
        default=DEFAULT_MIN_DOC_CHARS,
        help=(
            "Minimum normalized-text chars to register a fetched page "
            f"(default {DEFAULT_MIN_DOC_CHARS}; 0 disables). Thin fetches "
            "report as skipped_thin and fail the run."
        ),
    )
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="After a live run, pin a snapshot over every registered document.",
    )
    parser.add_argument(
        "--chunk-target-chars",
        type=int,
        default=DEFAULT_CHUNKING_PARAMS.target_chars,
        help=(
            "Snapshot chunking target size in chars "
            f"(default {DEFAULT_CHUNKING_PARAMS.target_chars}; part of the "
            "snapshot identity — new params pin a new snapshot)."
        ),
    )
    parser.add_argument(
        "--chunk-overlap-chars",
        type=int,
        default=DEFAULT_CHUNKING_PARAMS.overlap_chars,
        help=(
            "Snapshot chunking overlap upper bound in chars "
            f"(default {DEFAULT_CHUNKING_PARAMS.overlap_chars})."
        ),
    )
    args = parser.parse_args(argv)

    try:
        manifest = load_manifest(args.manifest)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"error: invalid manifest {args.manifest}: {exc}", file=sys.stderr)
        return 1

    effective_today = today if today is not None else datetime.now(UTC).date()

    if args.dry_run:
        _print_dry_run(manifest, today=effective_today, max_fetches=args.max_fetches)
        return 0

    if args.db is None:
        print("error: --db is required for a live run", file=sys.stderr)
        return 1

    registry = SqliteCorpusRegistry(SqliteDatabase(args.db))
    effective_fetcher: Fetcher = (
        fetcher if fetcher is not None else UrllibFetcher(timeout=args.timeout)
    )
    report = run_ingestion(
        manifest,
        registry=registry,
        fetcher=effective_fetcher,
        today=effective_today,
        max_fetches=args.max_fetches,
        min_doc_chars=args.min_doc_chars,
    )
    _print_report(report)

    if args.snapshot:
        documents = registry.list_documents()
        if not documents:
            print("snapshot: skipped — registry is empty", file=sys.stderr)
        else:
            try:
                chunking_params = ChunkingParams(
                    algorithm=DEFAULT_CHUNKING_PARAMS.algorithm,
                    target_chars=args.chunk_target_chars,
                    overlap_chars=args.chunk_overlap_chars,
                )
            except ValidationError as exc:
                print(f"error: invalid chunking params: {exc}", file=sys.stderr)
                return 1
            snapshot = registry.create_snapshot(
                [document.doc_id for document in documents],
                created_at=now if now is not None else datetime.now(UTC),
                chunking_params=chunking_params,
            )
            print(
                f"snapshot: {snapshot.snapshot_id} "
                f"({len(snapshot.doc_ids)} documents; chunking "
                f"{chunking_params.algorithm} target={chunking_params.target_chars} "
                f"overlap={chunking_params.overlap_chars})"
            )

    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
