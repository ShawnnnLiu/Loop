"""Tests for deterministic corpus text normalization."""

from __future__ import annotations

from agentic_calendar.retrieval.normalize import (
    html_to_text,
    looks_like_html,
    normalize_fetched_text,
    normalize_text,
)

_HTML = """<!DOCTYPE html>
<html>
  <head>
    <title>Guide</title>
    <style>body { color: red; }</style>
    <script>console.log("tracking");</script>
  </head>
  <body>
    <h1>Interview   guide</h1>
    <p>We emphasize <b>API design</b> &amp; observability.</p>
    <ul><li>Round one</li><li>Round two</li></ul>
  </body>
</html>
"""


def test_html_to_text_strips_tags_scripts_and_entities() -> None:
    text = html_to_text(_HTML)
    assert "Interview guide" in text
    assert "API design & observability." in text
    assert "Round one\nRound two" in text
    assert "console.log" not in text
    assert "color: red" not in text
    assert "<" not in text


def test_normalize_text_collapses_whitespace_deterministically() -> None:
    raw = "  a\tb  \r\n\r\n\r\n c  d \n\n\n"
    assert normalize_text(raw) == "a b\n\nc d"


def test_normalize_text_is_idempotent() -> None:
    raw = "  Line   one \n\n\n Line\ttwo \n"
    once = normalize_text(raw)
    assert normalize_text(once) == once


def test_html_sniff_is_deterministic() -> None:
    assert looks_like_html(_HTML)
    assert looks_like_html("   <!doctype HTML><p>x</p>")
    assert not looks_like_html("Use vector<T> for the buffer; std::map<K, V> too.")
    assert not looks_like_html("plain text about interviews")


def test_normalize_fetched_text_leaves_plain_text_markup_alone() -> None:
    # Angle-bracket source snippets in a plain-text payload must survive:
    # the tag parser only runs when the payload sniffs as HTML.
    plain = "Prefer vector<T> over raw arrays.\n\n\nUse   spaces wisely."
    assert normalize_fetched_text(plain) == (
        "Prefer vector<T> over raw arrays.\n\nUse spaces wisely."
    )
    assert "API design & observability." in normalize_fetched_text(_HTML)
