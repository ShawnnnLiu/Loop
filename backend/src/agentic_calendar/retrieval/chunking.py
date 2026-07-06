"""Deterministic, structure-aware chunking (``structure_v1``).

Chunks are the retrieval unit the FTS index (G-D) serves and claim assembly
(G-G) excerpts from. Everything here is a pure function of the normalized
document text plus an explicit
:class:`~agentic_calendar.contracts.corpus_snapshot.ChunkingParams` — the
byte-identical re-chunk property is what lets a pinned snapshot stand in for
"the evidence this eval ran against".

``structure_v1`` in one paragraph: markdown ATX headings (``# `` … ``###### ``)
open *sections*; chunks never span a section boundary and carry the heading
stack as a breadcrumb. Within a section, the packing units are paragraphs
(blank-line-separated runs); a paragraph longer than ``target_chars`` falls
back to its lines (HTML-derived text arrives as one line per source block
element, so this is the common path for web pages), and a single oversized
line is hard-split at ``target_chars``. Units pack greedily up to
``target_chars``, then each chunk (except a section's first) extends backward
over the previous chunk's trailing units by at most ``overlap_chars``.

Every chunk is an exact contiguous slice of the normalized text
(``chunk.text == text[start_char:end_char]``), so a claim can always point
back into the exact document region (auditability).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from agentic_calendar.contracts.corpus_snapshot import (
    ChunkingParams,
    CorpusSnapshot,
    chunking_fingerprint,
)

from .errors import UnknownCorpusDocumentError
from .registry import CorpusRegistry

#: Heuristic priors (axiom 08): chunk size is an eval ablation, not a tuned
#: constant. ~1600 chars is roughly 400 tokens of English prose.
DEFAULT_CHUNKING_PARAMS = ChunkingParams(
    algorithm="structure_v1", target_chars=1600, overlap_chars=200
)

#: ``chunk_`` + first 16 hex chars of the derivation hash.
CHUNK_ID_PATTERN = re.compile(r"^chunk_[0-9a-f]{16}$")

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)")

_BREADCRUMB_SEPARATOR = " > "


def derive_chunk_id(doc_id: str, ordinal: int, params: ChunkingParams) -> str:
    """Stable chunk identity: document + position + chunking configuration.

    Re-chunking the same text under the same params reproduces the same ids;
    changing params changes every id, so results from different chunkings can
    never be silently mixed.
    """
    digest = hashlib.sha256(
        f"{doc_id}\n{ordinal}\n{chunking_fingerprint(params)}".encode()
    ).hexdigest()
    return f"chunk_{digest[:16]}"


@dataclass(frozen=True)
class Chunk:
    """One retrieval unit: an exact slice of a document's normalized text."""

    chunk_id: str
    doc_id: str
    ordinal: int
    text: str
    start_char: int
    end_char: int
    breadcrumb: str | None


@dataclass(frozen=True)
class _Span:
    start: int
    end: int


def _line_spans(text: str) -> list[_Span]:
    spans: list[_Span] = []
    pos = 0
    for line in text.split("\n"):
        spans.append(_Span(pos, pos + len(line)))
        pos += len(line) + 1
    return spans


def _paragraph_atoms(text: str, lines: list[_Span], target: int) -> list[_Span]:
    """Fold a run of non-blank lines into atoms no larger than ``target``.

    The whole run is one atom when it fits; otherwise fall back to its lines;
    a single line longer than ``target`` is hard-split at ``target`` chars.
    """
    if not lines:
        return []
    start, end = lines[0].start, lines[-1].end
    if end - start <= target:
        return [_Span(start, end)]
    atoms: list[_Span] = []
    for line in lines:
        if line.end - line.start <= target:
            atoms.append(line)
            continue
        for piece_start in range(line.start, line.end, target):
            atoms.append(_Span(piece_start, min(piece_start + target, line.end)))
    return atoms


@dataclass(frozen=True)
class _Section:
    breadcrumb: str | None
    atoms: list[_Span]


def _sections(text: str, params: ChunkingParams) -> list[_Section]:
    """Split normalized text into heading-bounded sections of packed atoms."""
    sections: list[_Section] = []
    heading_stack: list[tuple[int, str]] = []
    atoms: list[_Span] = []
    paragraph: list[_Span] = []

    def close_paragraph() -> None:
        atoms.extend(_paragraph_atoms(text, paragraph, params.target_chars))
        paragraph.clear()

    def close_section() -> None:
        close_paragraph()
        if atoms:
            breadcrumb = (
                _BREADCRUMB_SEPARATOR.join(title for _, title in heading_stack)
                or None
            )
            sections.append(_Section(breadcrumb=breadcrumb, atoms=list(atoms)))
            atoms.clear()

    for span in _line_spans(text):
        line = text[span.start : span.end]
        if not line:
            close_paragraph()
            continue
        heading = _HEADING.match(line)
        if heading is not None:
            close_section()
            level = len(heading.group(1))
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, heading.group(2)))
            atoms.extend(_paragraph_atoms(text, [span], params.target_chars))
            continue
        paragraph.append(span)
    close_section()
    return sections


def _pack_section(
    section: _Section, params: ChunkingParams
) -> list[tuple[int, int, str | None]]:
    """Greedy-pack a section's atoms into (start, end, breadcrumb) chunks."""
    groups: list[list[_Span]] = []
    current: list[_Span] = []
    for atom in section.atoms:
        if current and atom.end - current[0].start > params.target_chars:
            groups.append(current)
            current = []
        current.append(atom)
    if current:
        groups.append(current)

    chunks: list[tuple[int, int, str | None]] = []
    for i, group in enumerate(groups):
        start = group[0].start
        if i > 0:
            # Extend backward over the previous group's trailing atoms; the
            # overlap is measured to the previous chunk's end and never
            # crosses a section boundary.
            previous = groups[i - 1]
            previous_end = previous[-1].end
            for atom in reversed(previous):
                if previous_end - atom.start > params.overlap_chars:
                    break
                start = atom.start
        chunks.append((start, group[-1].end, section.breadcrumb))
    return chunks


def chunk_text(text: str, *, doc_id: str, params: ChunkingParams) -> list[Chunk]:
    """Chunk one document's normalized text. Pure and deterministic.

    Empty text yields no chunks. Ordinals are contiguous from 0 in document
    order; every chunk satisfies ``chunk.text == text[start_char:end_char]``.
    """
    placed: list[tuple[int, int, str | None]] = []
    for section in _sections(text, params):
        placed.extend(_pack_section(section, params))
    return [
        Chunk(
            chunk_id=derive_chunk_id(doc_id, ordinal, params),
            doc_id=doc_id,
            ordinal=ordinal,
            text=text[start:end],
            start_char=start,
            end_char=end,
            breadcrumb=breadcrumb,
        )
        for ordinal, (start, end, breadcrumb) in enumerate(placed)
    ]


def chunk_snapshot(registry: CorpusRegistry, snapshot: CorpusSnapshot) -> list[Chunk]:
    """Chunk every member of ``snapshot`` under its pinned ``chunking_params``.

    Documents are processed in the snapshot's canonical (sorted) order, so the
    output ordering is as deterministic as the chunks themselves. A member the
    registry cannot resolve is a typed error — a snapshot must never silently
    chunk to fewer documents than it pins.
    """
    chunks: list[Chunk] = []
    missing: list[str] = []
    for doc_id in snapshot.doc_ids:
        text = registry.get_text(doc_id)
        if text is None:
            missing.append(doc_id)
            continue
        chunks.extend(
            chunk_text(text, doc_id=doc_id, params=snapshot.chunking_params)
        )
    if missing:
        raise UnknownCorpusDocumentError(missing)
    return chunks
