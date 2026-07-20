"""Assemble source claims from the retrieval corpus (grounding-RAG G-G).

Usage::

    # Offline preview: assemble, classify, score — write nothing.
    uv run python -m agentic_calendar.tools.refresh_claims \\
        --queries corpus/claim_queries_v4.json \\
        --manifest corpus/manifest_v1.json \\
        --corpus-db corpus/corpus.db --snapshot snap_xxxxxxxxxxxxxxxx \\
        --dry-run

    # Live: populate the app database's claim store (idempotent re-run).
    ... --app-db dogfood.db

This is the production path that finally populates ``env.claim_store``: the
injection seam (``StrategistInput.source_claims`` → prompt rule 5 → the
syllabus validator's claim-reference checks → the D1 pre-prompt curation
filter) has existed since Phase 5, but nothing ever produced claims. The
tool composes the two kernels from outside the region set — ``retrieval/``
supplies ranked chunks, ``source_claims/`` scores and stores — exactly the
composition seam both packages document.

Claim assembly is **deterministic** — no LLM anywhere (axiom 08; the axiom's
"Claim Assembly" subsection records that LLM distillation would be a fifth
node class and therefore needs an axiom 01 amendment first):

* A retrieved chunk becomes a **bounded verbatim excerpt**: its leading
  sentences, whitespace-flattened, trimmed at sentence boundaries to
  ``max_excerpt_chars``. Excerpts shorter than ``min_excerpt_chars`` (nav
  chrome, bare headings) are skipped and reported. Both bounds are heuristic
  priors, not tuned values.
* Excerpts that read as **navigation chrome** — menu/anchor soup from blog
  index pages rather than prose — are skipped and reported
  (``is_navigation_chrome``; signals and thresholds measured against the
  2026-07-14 claim store, where 10 of the 27 then-servable claims were
  chrome). The gate is deliberately conservative: title-list teasers that
  contain real sentences pass, and coherent-but-vacuous prose (marketing
  copy) is out of scope for a deterministic filter.
* Provenance: ``source_url`` is the document URL plus the chunk's section
  breadcrumb as a ``#fragment`` (the host — classification, curation cap —
  is unaffected); ``date_collected`` / ``source_published_date`` come from
  the corpus document.
* Claim identity is content-derived: ``claim_`` + sha256 over the document
  URL and the normalized excerpt — so a re-run, or a new snapshot over
  unchanged text, reproduces the same ``claim_id`` and the ingestor dedups
  it (idempotence); changed page text yields new ids.
* Corroboration is **exact-duplicate only**: the same normalized excerpt
  retrieved from two or more distinct document URLs links the claims
  mutually. Nothing fuzzier exists on purpose — a similarity threshold would
  be guesswork the deterministic scorer then amplifies (recorded open
  question). Note the ingestor credits only *already-stored* corroborators,
  so within one batch the first-ingested member of a group scores without
  the bonus while later members score with it; the stored id lists are
  complete either way (audit), and a registry-aware re-score is future work.
* Documents whose kernel-computed expiry predates their own collection date
  (old ``source_published_date`` + a short expiry window) are skipped at
  assembly — the ``SourceClaim`` contract would reject them, and evidence
  that stale can never be servable. Claims that are merely expired *now*
  are still ingested: they are auditable history, and the D1 curation
  filter keeps them out of prompts.

Scoring stays where it always was: records go through the **existing**
``SourceClaimIngestor`` — the only sanctioned producer of ``source_type`` /
``confidence_score`` / ``confidence_bucket`` / ``expires_at`` — with the
corpus manifest's declared host context, the same context the corpus
ingestion classified with. ``--dry-run`` runs the same pipeline against a
throwaway in-memory store, so the printed scores are the real ones.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from agentic_calendar.common.clock import Clock, SystemClock
from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.retrieval_query import MAX_RETRIEVAL_K, RetrievalQuery
from agentic_calendar.retrieval import (
    CorpusRegistry,
    SqliteChunkIndex,
    SqliteCorpusRegistry,
)
from agentic_calendar.source_claims.expiration import compute_expires_at
from agentic_calendar.source_claims.ingestion import (
    ClaimIngestionOutcome,
    ClaimIngestionStatus,
    InMemorySourceClaimStore,
    SourceClaimIngestor,
    SourceClaimStore,
)
from agentic_calendar.source_claims.priors import (
    DEFAULT_CONFIDENCE_PRIORS,
    ConfidencePriors,
)
from agentic_calendar.source_claims.sqlite_store import SqliteSourceClaimStore
from agentic_calendar.tools.ingest_corpus import CorpusManifest, load_manifest

#: Excerpt bounds (chars) — heuristic priors, not tuned. The ceiling keeps a
#: claim prompt-sized (well under one chunk's 1600-char target); the floor
#: drops fragments too short to state anything checkable.
DEFAULT_MAX_EXCERPT_CHARS = 500
DEFAULT_MIN_EXCERPT_CHARS = 40

_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+")

_NON_SLUG = re.compile(r"[^a-z0-9]+")


# --------------------------------------------------------------------------- #
# Navigation-chrome gate (deterministic; thresholds are heuristic priors,
# chosen by measuring every candidate signal against the real 117-claim store
# on 2026-07-14 and inspecting both sides of each cut).
# --------------------------------------------------------------------------- #

#: A sentence terminator followed by (optional closing quote/bracket and)
#: whitespace or end-of-text. Distinct from ``_SENTENCE_BREAK``: this one
#: also matches at the end of the excerpt, so a single trailing sentence
#: counts as sentence evidence.
#: (The character class includes the curly closing quotes real fetched
#: prose uses.)
_TERMINATOR = re.compile("[.!?][\"'”’)\\]]?(?:\\s|$)")  # noqa: RUF001 — real curly quotes

#: A lowercase→uppercase joint inside one token — HTML→text flattening glues
#: adjacent nav anchors into tokens like ``PrinciplesSystem``. Real camelCase
#: tech names (``JavaScript``, ``SystemVerilog``) stay under the length bound.
_CAMEL_JOINT = re.compile(r"[a-z][A-Z]")
_CAMEL_JOINT_MIN_TOKEN_CHARS = 15
_TOKEN_TRIM_CHARS = ".,;:!?\"'()[]“”‘’"  # noqa: RUF001 — real curly quotes

#: Longest Title-Case token run that flags regardless of sentence evidence
#: (nav menus / concatenated headline lists), and the lower bound that flags
#: only when the excerpt carries no sentence terminator at all.
_UPPERCASE_RUN_HARD = 20
_UPPERCASE_RUN_WITHOUT_SENTENCE = 10

#: Two or more pipes in one excerpt is title/breadcrumb separator territory
#: ("The HRT Beat | Tech Blog | Hudson River Trading"), not prose.
_PIPE_LIMIT = 2

#: Verbatim page furniture that only appears in chrome. Casefolded substring
#: match; keep this list short and unambiguous — every phrase here was seen
#: in a real stored claim.
_NAV_PHRASES = (
    "skip to main content",
    "skip to content",
    "skip navigation",
    "subscribe to email updates",
    "loginsign up",
)


def _longest_uppercase_run(text: str) -> int:
    """Longest run of consecutive uppercase-initial tokens.

    Lowercase-initial tokens break the run; digit/symbol-initial tokens are
    neutral (nav menus interleave counts, dates, and separators with their
    Title Case anchors) — they neither extend nor break it.
    """
    best = run = 0
    for token in text.split():
        first = token[0]
        if first.isupper():
            run += 1
            best = max(best, run)
        elif first.isalpha():
            run = 0
    return best


def is_navigation_chrome(text: str) -> bool:
    """True when ``text`` reads as page furniture rather than prose.

    Four independent signals, each deterministic and inspectable:

    1. a curated nav phrase ("skip to main content", …);
    2. ``>= 2`` pipe separators;
    3. a Title-Case token run ``>= 20`` (menu / headline-list soup), or
       ``>= 10`` when the excerpt contains no sentence terminator at all;
    4. a long token with an internal lowercase→uppercase joint — adjacent
       anchors glued together by HTML flattening (``PrinciplesSystem``).

    Measured on the 2026-07-14 store (117 claims): flags 20, including all
    of the levels.fyi salary-page chrome then serving as ``role_taxonomy``
    evidence; every flagged claim was verified chrome (or a bare citation
    list) by inspection, and known-good prose — Title-Case headlines,
    latency-number tables, terse study guides — passes.
    """
    lowered = text.casefold()
    if any(phrase in lowered for phrase in _NAV_PHRASES):
        return True
    if text.count("|") >= _PIPE_LIMIT:
        return True
    run = _longest_uppercase_run(text)
    if run >= _UPPERCASE_RUN_HARD:
        return True
    if run >= _UPPERCASE_RUN_WITHOUT_SENTENCE and not _TERMINATOR.search(text):
        return True
    return any(
        len(token.strip(_TOKEN_TRIM_CHARS)) >= _CAMEL_JOINT_MIN_TOKEN_CHARS
        and _CAMEL_JOINT.search(token)
        for token in text.split()
    )


# --------------------------------------------------------------------------- #
# Claim-query set (tool-local operator input, like the corpus manifest —
# versioned and checked in; the population run is reproducible from it).
# --------------------------------------------------------------------------- #


class ClaimQuery(BaseModel):
    """One curated retrieval query used to source claims for a track."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    track: CareerTrack
    query_text: str = Field(min_length=1)
    comment: str | None = None


class ClaimQuerySet(BaseModel):
    """The checked-in, review-curated query list claim assembly runs."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    query_set_version: str = Field(min_length=1)
    k: int = Field(ge=1, le=MAX_RETRIEVAL_K)
    comment: str | None = None
    queries: list[ClaimQuery] = Field(min_length=1)

    @model_validator(mode="after")
    def _queries_unique(self) -> ClaimQuerySet:
        seen: set[tuple[str, str]] = set()
        for query in self.queries:
            key = (query.track.value, query.query_text)
            if key in seen:
                raise ValueError(f"duplicate query for track {key[0]!r}: {key[1]!r}")
            seen.add(key)
        return self


def load_claim_queries(path: Path) -> ClaimQuerySet:
    """Load and validate a claim-query set file (raises on invalid)."""
    return ClaimQuerySet.model_validate(json.loads(path.read_text("utf-8")))


# --------------------------------------------------------------------------- #
# Deterministic assembly: ranked chunks → raw claim records.
# --------------------------------------------------------------------------- #


def build_excerpt(
    text: str,
    *,
    max_chars: int = DEFAULT_MAX_EXCERPT_CHARS,
    min_chars: int = DEFAULT_MIN_EXCERPT_CHARS,
) -> str | None:
    """Bounded verbatim excerpt: leading sentences, whitespace-flattened.

    Sentences are accumulated from the start of the chunk until the next one
    would exceed ``max_chars``; a single opening sentence longer than the
    bound is cut at its last word boundary inside it. Returns ``None`` when
    the result is shorter than ``min_chars`` — too short to state anything a
    reviewer could accept or reject.
    """
    flat = " ".join(text.split())
    if len(flat) <= max_chars:
        excerpt = flat
    else:
        sentences = _SENTENCE_BREAK.split(flat)
        excerpt = sentences[0]
        for sentence in sentences[1:]:
            if len(excerpt) + 1 + len(sentence) > max_chars:
                break
            excerpt = f"{excerpt} {sentence}"
        if len(excerpt) > max_chars:
            cut = excerpt.rfind(" ", 0, max_chars + 1)
            excerpt = excerpt[: cut if cut > 0 else max_chars].rstrip()
    if len(excerpt) < min_chars:
        return None
    return excerpt


def excerpt_key(excerpt: str) -> str:
    """Normalized identity of an excerpt (casefolded, whitespace-flattened)."""
    return " ".join(excerpt.split()).casefold()


def derive_claim_id(document_url: str, key: str) -> str:
    """``claim_`` + first 16 hex of sha256 over document URL + excerpt key."""
    digest = hashlib.sha256(f"{document_url}\n{key}".encode()).hexdigest()
    return f"claim_{digest[:16]}"


def _breadcrumb_fragment(breadcrumb: str | None) -> str:
    """Deterministic ``#fragment`` slug for a section breadcrumb ('' if none)."""
    if breadcrumb is None:
        return ""
    slug = _NON_SLUG.sub("-", breadcrumb.casefold()).strip("-")
    return f"#{slug}" if slug else ""


@dataclass(frozen=True)
class AssembledClaim:
    """One pre-ingestion claim record plus its assembly provenance."""

    claim_id: str
    claim_text: str
    source_url: str
    document_url: str
    doc_id: str
    chunk_id: str
    track: CareerTrack
    date_collected: date
    source_published_date: date | None
    corroborating_claim_ids: tuple[str, ...] = ()

    def raw_record(self) -> dict[str, Any]:
        """The raw payload handed to the ingestor (no derived score fields)."""
        record: dict[str, Any] = {
            "claim_id": self.claim_id,
            "claim_text": self.claim_text,
            "source_url": self.source_url,
            "date_collected": self.date_collected.isoformat(),
            "corroborating_claim_ids": list(self.corroborating_claim_ids),
        }
        if self.source_published_date is not None:
            record["source_published_date"] = self.source_published_date.isoformat()
        return record


@dataclass(frozen=True)
class AssemblyReport:
    """Assembled claims plus what assembly declined, for the operator."""

    claims: list[AssembledClaim]
    skipped_short: int
    skipped_chrome: int
    skipped_stale: int
    duplicates_folded: int
    corroboration_groups: int


def assemble_claims(
    *,
    registry: CorpusRegistry,
    index: SqliteChunkIndex,
    snapshot_id: str,
    query_set: ClaimQuerySet,
    manifest: CorpusManifest,
    priors: ConfidencePriors = DEFAULT_CONFIDENCE_PRIORS,
    max_excerpt_chars: int = DEFAULT_MAX_EXCERPT_CHARS,
    min_excerpt_chars: int = DEFAULT_MIN_EXCERPT_CHARS,
) -> AssemblyReport:
    """Run every query, excerpt the ranked chunks, dedup, link exact duplicates.

    Pure given its inputs: query file order, then rank order, decides
    first-occurrence dedup, so the same snapshot + query set + params always
    assembles the identical record list (asserted by test).
    """
    seen: set[tuple[str, str]] = set()
    claims: list[AssembledClaim] = []
    skipped_short = 0
    skipped_chrome = 0
    skipped_stale = 0
    duplicates_folded = 0
    for query in query_set.queries:
        result = index.search(
            RetrievalQuery(query_text=query.query_text, track=query.track, k=query_set.k),
            snapshot_id=snapshot_id,
        )
        for ranked in result.results:
            chunk = index.get_chunk(snapshot_id, ranked.chunk_id)
            document = registry.get_document(ranked.doc_id)
            # Both came out of the index/registry one call ago; a miss here
            # would be store corruption, which fails loudly elsewhere.
            assert chunk is not None and document is not None
            excerpt = build_excerpt(
                chunk.text, max_chars=max_excerpt_chars, min_chars=min_excerpt_chars
            )
            if excerpt is None:
                skipped_short += 1
                continue
            if is_navigation_chrome(excerpt):
                skipped_chrome += 1
                continue
            source_type = manifest.classify(document.source_url)
            anchor = document.source_published_date or document.date_collected
            expires_at = compute_expires_at(source_type, anchor=anchor, priors=priors)
            if expires_at < document.date_collected:
                skipped_stale += 1
                continue
            key = excerpt_key(excerpt)
            dedup_key = (document.source_url, key)
            if dedup_key in seen:
                duplicates_folded += 1
                continue
            seen.add(dedup_key)
            claims.append(
                AssembledClaim(
                    claim_id=derive_claim_id(document.source_url, key),
                    claim_text=excerpt,
                    source_url=document.source_url + _breadcrumb_fragment(chunk.breadcrumb),
                    document_url=document.source_url,
                    doc_id=document.doc_id,
                    chunk_id=chunk.chunk_id,
                    track=query.track,
                    date_collected=document.date_collected,
                    source_published_date=document.source_published_date,
                )
            )

    # Exact-duplicate corroboration: the dedup key is (document URL, excerpt
    # key), so members of a same-key group necessarily come from distinct
    # document URLs — link them mutually. Nothing fuzzier, on purpose.
    by_key: dict[str, list[int]] = {}
    for position, claim in enumerate(claims):
        by_key.setdefault(excerpt_key(claim.claim_text), []).append(position)
    corroboration_groups = 0
    for positions in by_key.values():
        if len(positions) < 2:
            continue
        corroboration_groups += 1
        group_ids = [claims[i].claim_id for i in positions]
        for i in positions:
            claims[i] = replace(
                claims[i],
                corroborating_claim_ids=tuple(
                    sorted(cid for cid in group_ids if cid != claims[i].claim_id)
                ),
            )

    return AssemblyReport(
        claims=claims,
        skipped_short=skipped_short,
        skipped_chrome=skipped_chrome,
        skipped_stale=skipped_stale,
        duplicates_folded=duplicates_folded,
        corroboration_groups=corroboration_groups,
    )


# --------------------------------------------------------------------------- #
# Ingestion + reporting.
# --------------------------------------------------------------------------- #


def ingest_assembled(
    claims: list[AssembledClaim],
    *,
    store: SourceClaimStore,
    manifest: CorpusManifest,
    clock: Clock,
    priors: ConfidencePriors = DEFAULT_CONFIDENCE_PRIORS,
) -> list[tuple[AssembledClaim, ClaimIngestionOutcome]]:
    """Feed every assembled record through the sanctioned ingestor, in order."""
    ingestor = SourceClaimIngestor(
        clock=clock,
        store=store,
        priors=priors,
        known_company_domains=frozenset(manifest.known_company_domains),
        engineering_blog_hosts=frozenset(manifest.engineering_blog_hosts),
        personal_blog_hosts=frozenset(manifest.personal_blog_hosts),
    )
    return [(claim, ingestor.ingest(claim.raw_record())) for claim in claims]


def _print_outcomes(
    outcomes: list[tuple[AssembledClaim, ClaimIngestionOutcome]],
    report: AssemblyReport,
    query_set: ClaimQuerySet,
) -> None:
    for assembled, outcome in outcomes:
        if outcome.claim is not None:
            stored = outcome.claim
            print(
                f"[{outcome.status.value}] {stored.claim_id} "
                f"{stored.source_type.value}/{stored.confidence_bucket.value} "
                f"{stored.confidence_score:.2f} expires {stored.expires_at} "
                f"{assembled.source_url}"
            )
        else:
            print(
                f"[{outcome.status.value}] {assembled.claim_id} "
                f"{assembled.source_url} — {outcome.error}"
            )
    print(
        f"assembly: {len(report.claims)} claims from {len(query_set.queries)} "
        f"queries (k={query_set.k}, {query_set.query_set_version}) — skipped "
        f"{report.skipped_short} short, {report.skipped_chrome} nav-chrome, "
        f"{report.skipped_stale} stale-at-source; "
        f"{report.duplicates_folded} duplicates folded; "
        f"{report.corroboration_groups} corroboration group(s)"
    )
    status_counts = Counter(outcome.status for _, outcome in outcomes)
    statuses = ", ".join(
        f"{status.value}={count}" for status, count in sorted(status_counts.items())
    )
    print(f"ingestion: {statuses or 'nothing to ingest'}")
    stored_claims = [outcome.claim for _, outcome in outcomes if outcome.claim is not None]
    if stored_claims:
        by_type = Counter(claim.source_type.value for claim in stored_claims)
        by_bucket = Counter(claim.confidence_bucket.value for claim in stored_claims)
        print(
            "by source_type: "
            + ", ".join(f"{name}={count}" for name, count in sorted(by_type.items()))
        )
        print(
            "by bucket: "
            + ", ".join(f"{name}={count}" for name, count in sorted(by_bucket.items()))
        )
    print(
        "note: confidence scores/buckets are deterministic heuristic priors "
        "(axiom 08), uncalibrated until the calibration pass"
    )


def main(argv: list[str] | None = None, *, clock: Clock | None = None) -> int:
    """CLI entry point. ``clock`` is injectable for tests."""
    parser = argparse.ArgumentParser(
        description=(
            "Assemble verbatim-excerpt source claims from a pinned corpus "
            "snapshot and populate the app's claim store (offline; "
            "deterministic assembly, sanctioned-ingestor scoring)."
        )
    )
    parser.add_argument("--queries", type=Path, required=True, help="Claim-query set JSON.")
    parser.add_argument(
        "--manifest",
        type=Path,
        required=True,
        help="Corpus manifest JSON (classifier host context).",
    )
    parser.add_argument("--corpus-db", type=Path, required=True, help="Corpus SQLite database.")
    parser.add_argument("--snapshot", required=True, help="Pinned snapshot id (snap_ + 16 hex).")
    parser.add_argument(
        "--app-db",
        type=Path,
        default=None,
        help="App SQLite database whose claim store gets populated (required unless --dry-run).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Assemble and score against a throwaway in-memory store; write nothing.",
    )
    args = parser.parse_args(argv)

    try:
        query_set = load_claim_queries(args.queries)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"error: invalid query set {args.queries}: {exc}", file=sys.stderr)
        return 1
    try:
        manifest = load_manifest(args.manifest)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"error: invalid manifest {args.manifest}: {exc}", file=sys.stderr)
        return 1
    if not args.corpus_db.exists():
        print(f"error: corpus database not found: {args.corpus_db}", file=sys.stderr)
        return 1
    if not args.dry_run and args.app_db is None:
        print("error: --app-db is required for a live run", file=sys.stderr)
        return 1

    corpus_db = SqliteDatabase(args.corpus_db)
    registry = SqliteCorpusRegistry(corpus_db)
    snapshot = registry.get_snapshot(args.snapshot)
    if snapshot is None:
        print(
            f"error: snapshot {args.snapshot!r} is not in {args.corpus_db}",
            file=sys.stderr,
        )
        return 1
    index = SqliteChunkIndex(corpus_db)
    # Derived data: (re)building is offline, idempotent, deterministic.
    index.build(registry, snapshot)

    report = assemble_claims(
        registry=registry,
        index=index,
        snapshot_id=snapshot.snapshot_id,
        query_set=query_set,
        manifest=manifest,
    )

    store: SourceClaimStore
    if args.dry_run:
        store = InMemorySourceClaimStore()
        print("dry-run: scoring against a throwaway store — nothing is written")
    else:
        store = SqliteSourceClaimStore(SqliteDatabase(args.app_db))

    outcomes = ingest_assembled(
        report.claims,
        store=store,
        manifest=manifest,
        clock=clock if clock is not None else SystemClock(),
    )
    _print_outcomes(outcomes, report, query_set)

    rejected = sum(1 for _, outcome in outcomes if outcome.status is ClaimIngestionStatus.REJECTED)
    return 1 if rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
