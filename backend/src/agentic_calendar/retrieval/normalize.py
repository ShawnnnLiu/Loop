"""Deterministic text normalization for corpus ingestion.

The registry pins document text by ``content_hash``, so normalization must be
a pure function: the same fetched payload always yields the same normalized
text, hence the same hash (hash-idempotent re-ingest). stdlib only
(``html.parser``, ``unicodedata``) — no parser dependency without an explicit
ask (G-B gate).

Two layers:

* :func:`normalize_text` — Unicode NFC, per-line whitespace collapse, blank
  runs collapsed to single paragraph breaks. Idempotent.
* :func:`html_to_text` — tag stripping via ``HTMLParser`` (``script`` /
  ``style`` / ``noscript`` / ``template`` contents dropped, block boundaries
  become line breaks, entities unescaped), then :func:`normalize_text`.

:func:`normalize_fetched_text` picks between them with a deterministic sniff:
a payload whose first kilobyte opens with an HTML doctype or contains an
``<html`` tag is HTML; anything else is treated as plain text so that
angle-bracket source snippets (``list<T>``) in text files are never eaten by
the tag parser. The sniff is a heuristic prior — documented, not tuned.
"""

from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser

#: Tags whose entire content is dropped.
_SKIPPED_CONTENT_TAGS: frozenset[str] = frozenset(
    {"script", "style", "noscript", "template"}
)

#: Tags that imply a line break around their content.
_BLOCK_TAGS: frozenset[str] = frozenset(
    {
        "address",
        "article",
        "aside",
        "blockquote",
        "br",
        "div",
        "dd",
        "dl",
        "dt",
        "fieldset",
        "figcaption",
        "figure",
        "footer",
        "form",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "header",
        "hr",
        "li",
        "main",
        "nav",
        "ol",
        "p",
        "pre",
        "section",
        "table",
        "td",
        "th",
        "tr",
        "ul",
    }
)

_INLINE_WHITESPACE = re.compile(r"[ \t\f\v\r]+")


def normalize_text(text: str) -> str:
    """Deterministic, idempotent whitespace/encoding normalization.

    Unicode NFC; runs of intra-line whitespace collapse to one space; lines
    are stripped; runs of blank lines collapse to a single blank line
    (paragraph break); no leading/trailing blank lines.
    """
    normalized = unicodedata.normalize("NFC", text)
    lines = [
        _INLINE_WHITESPACE.sub(" ", line).strip() for line in normalized.splitlines()
    ]
    out: list[str] = []
    for line in lines:
        if line:
            out.append(line)
        elif out and out[-1] != "":
            out.append("")
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


class _TextExtractor(HTMLParser):
    """Collects text nodes, dropping skipped-tag content, breaking on blocks."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag in _SKIPPED_CONTENT_TAGS:
            self._skip_depth += 1
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIPPED_CONTENT_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._parts.append(data)

    @property
    def text(self) -> str:
        return "".join(self._parts)


def html_to_text(html: str) -> str:
    """Strip HTML to normalized plain text, deterministically.

    One line per block boundary. Blank lines are dropped entirely: in HTML,
    whitespace is not semantic (structure lives in the tags), so adjacent
    block boundaries must not fabricate paragraph breaks.
    """
    extractor = _TextExtractor()
    extractor.feed(html)
    extractor.close()
    normalized = normalize_text(extractor.text)
    return "\n".join(line for line in normalized.splitlines() if line)


def looks_like_html(payload: str) -> bool:
    """Deterministic HTML sniff over the first kilobyte."""
    head = payload[:1024].lstrip().lower()
    return head.startswith("<!doctype html") or "<html" in head


def normalize_fetched_text(payload: str) -> str:
    """Normalize a fetched payload: strip tags when it sniffs as HTML."""
    if looks_like_html(payload):
        return html_to_text(payload)
    return normalize_text(payload)
