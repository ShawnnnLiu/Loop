"""Annotate the skill taxonomy with corpus evidence (résumé-intake RI-F).

Usage::

    # Offline preview: count, report — write nothing.
    uv run python -m agentic_calendar.tools.enrich_taxonomy \\
        --corpus-db corpus/corpus.db --snapshot snap_xxxxxxxxxxxxxxxx \\
        --dry-run

    # Live: write the NEW taxonomy file version (default: next version
    # number next to the input file; refuses to overwrite).
    ... --taxonomy taxonomy/skill_taxonomy_v4.json

Operator-run and fully offline against a **pinned corpus snapshot**: for each
taxonomy entry, count alias occurrences via the FTS5 index and write
``corpus_evidence`` (snapshot id, counts, supporting doc ids) into a NEW
taxonomy file version — append-only versioning, like every vocabulary change.
The tool composes the two kernels from outside the region set —
``skill_taxonomy/`` supplies the vocabulary, ``retrieval/`` the index — the
same seam discipline as ``refresh_claims``.

Counting semantics (``docs/specs/skill-taxonomy.schema.md``, "Enrichment
semantics"):

* Each alias compiles to an FTS5 **phrase** query (consecutive tokens, never
  bag-of-words) — the enrichment counterpart of the resolver's exact-alias
  restraint.
* Matches are restricted to chunks of documents tagged with at least one of
  the entry's ``track_tags`` — track-scoped support, not corpus-wide
  frequency.
* ``occurrence_count`` is the number of **distinct chunks** matching any
  alias; ``supporting_doc_ids`` are those chunks' distinct documents, sorted.
* The report breaks counts down **per alias**, not just per entry: short
  ambiguous aliases (``go``, ``r``, ``c``) inflate counts against ordinary
  prose, and the long distinctive alias's count is the trustworthy signal
  (career-track expansion ``01-expansion-mechanics.md``).

Curation walls (axiom 08 "Controlled Vocabularies"): evidence annotates —
zero-support entries are **flagged in the report for human review**, never
deleted; high counts never add an entry; and this tool never flips the
registry pin (``skill_taxonomy/registry.py`` ``DEFAULT_TAXONOMY_PATH``) —
adopting the new version is a separate reviewed change, because app-layer
surfaces pin ``taxonomy_version`` explicitly.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.skill_taxonomy import (
    CorpusEvidence,
    SkillEntry,
    SkillTaxonomy,
)
from agentic_calendar.retrieval import SqliteChunkIndex, SqliteCorpusRegistry
from agentic_calendar.skill_taxonomy.registry import (
    DEFAULT_TAXONOMY_PATH,
    SkillTaxonomyLoadError,
    load_taxonomy,
)

_VERSION = re.compile(r"^skill-taxonomy-v(\d+)$")


@dataclass(frozen=True)
class AliasEvidence:
    """One alias's phrase-match count (advisory prior, per report design)."""

    alias: str
    chunk_count: int


@dataclass(frozen=True)
class EntryEvidence:
    """Evidence gathered for one taxonomy entry, plus its per-alias breakdown."""

    skill_id: str
    display_name: str
    per_alias: tuple[AliasEvidence, ...]
    occurrence_count: int
    supporting_doc_ids: tuple[str, ...]


def gather_evidence(
    *,
    index: SqliteChunkIndex,
    snapshot_id: str,
    taxonomy: SkillTaxonomy,
) -> list[EntryEvidence]:
    """Count alias occurrences for every entry. Pure given (index, snapshot).

    Entry order follows the curated file; per-alias order follows the entry's
    alias list; matches order by ``chunk_id`` — so the same snapshot + taxonomy
    always yields the identical evidence list (asserted by test).
    """
    evidence: list[EntryEvidence] = []
    for entry in taxonomy.entries:
        per_alias: list[AliasEvidence] = []
        chunk_ids: set[str] = set()
        doc_ids: set[str] = set()
        for alias in entry.aliases:
            matches = index.match_phrase(snapshot_id, alias, tracks=entry.track_tags)
            per_alias.append(AliasEvidence(alias=alias, chunk_count=len(matches)))
            for chunk_id, doc_id in matches:
                chunk_ids.add(chunk_id)
                doc_ids.add(doc_id)
        evidence.append(
            EntryEvidence(
                skill_id=entry.skill_id,
                display_name=entry.display_name,
                per_alias=tuple(per_alias),
                occurrence_count=len(chunk_ids),
                supporting_doc_ids=tuple(sorted(doc_ids)),
            )
        )
    return evidence


def next_taxonomy_version(taxonomy_version: str) -> str:
    """``skill-taxonomy-vN`` → ``skill-taxonomy-v(N+1)`` (typed raise otherwise)."""
    match = _VERSION.match(taxonomy_version)
    if match is None:
        raise ValueError(f"malformed taxonomy_version: {taxonomy_version!r}")
    return f"skill-taxonomy-v{int(match.group(1)) + 1}"


def build_enriched_taxonomy(
    taxonomy: SkillTaxonomy,
    evidence: list[EntryEvidence],
    *,
    snapshot_id: str,
) -> SkillTaxonomy:
    """The NEW taxonomy version: entries verbatim, only ``corpus_evidence`` filled.

    Every entry gets evidence — a zero count is recorded honestly, not left
    ``null``. Rebuilt through the contract constructors so the full validation
    set (global alias uniqueness included) re-runs on the output.
    """
    by_id = {e.skill_id: e for e in evidence}
    entries = [
        SkillEntry(
            **{
                **entry.model_dump(),
                "corpus_evidence": CorpusEvidence(
                    snapshot_id=snapshot_id,
                    occurrence_count=by_id[entry.skill_id].occurrence_count,
                    supporting_doc_ids=list(by_id[entry.skill_id].supporting_doc_ids),
                ),
            }
        )
        for entry in taxonomy.entries
    ]
    return SkillTaxonomy(
        taxonomy_version=next_taxonomy_version(taxonomy.taxonomy_version),
        entries=entries,
    )


def _print_report(evidence: list[EntryEvidence], *, snapshot_id: str) -> None:
    for entry in evidence:
        breakdown = ", ".join(f"{a.alias}={a.chunk_count}" for a in entry.per_alias)
        print(
            f"{entry.skill_id} ({entry.display_name}) — "
            f"{entry.occurrence_count} chunk(s), "
            f"{len(entry.supporting_doc_ids)} doc(s) [{breakdown}]"
        )
    zero = [e for e in evidence if e.occurrence_count == 0]
    supported = len(evidence) - len(zero)
    print(
        f"evidence: {supported}/{len(evidence)} entries with corpus support "
        f"in {snapshot_id}"
    )
    if zero:
        print(f"zero-support entries ({len(zero)}) — flagged for human curation review:")
        for entry in zero:
            print(f"  {entry.skill_id} ({entry.display_name})")
        print(
            "  possible meanings: genuinely niche (keep), corpus missing a "
            "document class (fix the manifest), or aliases don't match corpus "
            "spelling (fix aliases in the next version)"
        )
    print(
        "note: counts are advisory FTS5 phrase-match priors — short ambiguous "
        "aliases overcount; trust the distinctive long alias's count "
        "(per-alias breakdown above)"
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Count per-track alias occurrences over a pinned corpus snapshot "
            "and write corpus_evidence into a NEW taxonomy file version "
            "(offline, deterministic; evidence annotates, never curates)."
        )
    )
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=DEFAULT_TAXONOMY_PATH,
        help="Input taxonomy JSON (default: the registry's pinned version).",
    )
    parser.add_argument("--corpus-db", type=Path, required=True, help="Corpus SQLite database.")
    parser.add_argument("--snapshot", required=True, help="Pinned snapshot id (snap_ + 16 hex).")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "Output path for the new version (default: next version number "
            "next to the input file). Refuses to overwrite an existing file."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the would-be evidence table; write nothing.",
    )
    args = parser.parse_args(argv)

    try:
        taxonomy = load_taxonomy(args.taxonomy)
    except SkillTaxonomyLoadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    try:
        new_version = next_taxonomy_version(taxonomy.taxonomy_version)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    out_path: Path = (
        args.out
        if args.out is not None
        else args.taxonomy.with_name(f"skill_taxonomy_v{new_version.rsplit('v', 1)[1]}.json")
    )
    if not args.dry_run and out_path.exists():
        print(
            f"error: {out_path} already exists — taxonomy versions are "
            "append-only, never overwritten",
            file=sys.stderr,
        )
        return 1
    if not args.corpus_db.exists():
        print(f"error: corpus database not found: {args.corpus_db}", file=sys.stderr)
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

    evidence = gather_evidence(
        index=index, snapshot_id=snapshot.snapshot_id, taxonomy=taxonomy
    )
    _print_report(evidence, snapshot_id=snapshot.snapshot_id)

    if args.dry_run:
        print(f"dry-run: nothing written ({out_path} would hold {new_version})")
        return 0

    enriched = build_enriched_taxonomy(
        taxonomy, evidence, snapshot_id=snapshot.snapshot_id
    )
    out_path.write_text(
        json.dumps(enriched.model_dump(mode="json"), indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {out_path} ({enriched.taxonomy_version})")
    print(
        "note: the registry pin (skill_taxonomy/registry.py "
        "DEFAULT_TAXONOMY_PATH) is unchanged — adopting the new version is a "
        "separate reviewed change"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
