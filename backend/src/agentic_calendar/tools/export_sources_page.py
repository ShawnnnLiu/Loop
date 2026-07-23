"""Generate the public ``/sources`` bibliography page from the corpus.

Renders ``landing/sources.html`` - the crawlable list of every cited source,
grouped by career track - directly from the committed corpus registry
(``backend/corpus/corpus.db``). The corpus *is* the labeled source list: each
:class:`~agentic_calendar.contracts.corpus_document.CorpusDocument` already
carries ``source_url``, ``title``, ``source_type`` and ``track_tags`` (the
career labels), so scraping more sources into the corpus is all that is needed -
this tool re-derives the page, it never maintains a second list.

Tracks are discovered from the data, so a track that gains its first source
(e.g. ``data_analyst``) appears automatically on the next regeneration.

Usage::

    uv run python -m agentic_calendar.tools.export_sources_page
    uv run python -m agentic_calendar.tools.export_sources_page --check

The CLI is deterministic: the same corpus produces byte-identical HTML, so
``--check`` can gate merges (see ``make sources-check``).
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

from agentic_calendar.common.sqlite import SqliteDatabase
from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.corpus_document import CorpusDocument
from agentic_calendar.contracts.source_claim import SourceType
from agentic_calendar.retrieval import SqliteCorpusRegistry

#: Default corpus database (committed), relative to ``backend/``.
DEFAULT_CORPUS_DB = Path("corpus/corpus.db")
#: Default output page, relative to ``backend/``.
DEFAULT_OUT = Path("../landing/sources.html")

#: Display order for tracks. Any enum member missing here is appended in enum
#: order, so a newly populated track still renders without a code change.
_PREFERRED_ORDER: tuple[CareerTrack, ...] = (
    CareerTrack.SWE,
    CareerTrack.AI_ENGINEER,
    CareerTrack.MLE,
    CareerTrack.DATA_SCIENTIST,
    CareerTrack.DATA_ANALYST,
    CareerTrack.DATA_ENGINEER,
    CareerTrack.QUANT_DEV,
    CareerTrack.PRODUCT_MANAGER,
)

_TRACK_LABEL: dict[CareerTrack, str] = {
    CareerTrack.SWE: "Software Engineering",
    CareerTrack.AI_ENGINEER: "AI Engineering",
    CareerTrack.MLE: "Machine Learning Engineering",
    CareerTrack.DATA_SCIENTIST: "Data Science",
    CareerTrack.DATA_ANALYST: "Data Analytics",
    CareerTrack.DATA_ENGINEER: "Data Engineering",
    CareerTrack.QUANT_DEV: "Quantitative Development",
    CareerTrack.PRODUCT_MANAGER: "Product Management",
}

_TRACK_BLURB: dict[CareerTrack, str] = {
    CareerTrack.SWE: (
        "Systems, reliability, incident management, and code craft from the teams "
        "that run production at scale."
    ),
    CareerTrack.AI_ENGINEER: (
        "Building LLM-powered products: agents, retrieval, evaluation, and the "
        "practitioners defining the discipline."
    ),
    CareerTrack.MLE: (
        "Modeling, training, and deployment - from first principles to production "
        "ML platforms."
    ),
    CareerTrack.DATA_SCIENTIST: (
        "Experimentation, causal inference, and the analytics cultures behind "
        "data-driven products."
    ),
    CareerTrack.DATA_ANALYST: (
        "Analytics, dashboards, SQL, and turning messy data into decisions people "
        "act on."
    ),
    CareerTrack.DATA_ENGINEER: (
        "Pipelines, warehouses, and the data infrastructure everything else is "
        "built on."
    ),
    CareerTrack.QUANT_DEV: (
        "Low-latency systems, market microstructure, and life inside quantitative "
        "trading firms."
    ),
    CareerTrack.PRODUCT_MANAGER: (
        "Discovery, strategy, prioritization, and what great product teams actually "
        "do."
    ),
}

_TYPE_LABEL: dict[SourceType, str] = {
    SourceType.OFFICIAL_JOB_POSTING: "Job posting",
    SourceType.COMPANY_ENGINEERING_BLOG: "Engineering blog",
    SourceType.ROLE_TAXONOMY: "Role & levels",
    SourceType.INTERVIEW_POSTMORTEM: "Interview postmortem",
    SourceType.INTERVIEW_REPORT: "Interview report",
    SourceType.PERSONAL_ANECDOTE: "Practitioner essay",
    SourceType.UNCLASSIFIED: "Reference",
    SourceType.CANONICAL_TOPIC_MODULE: "Topic module",
}

_FAVICON = (
    "data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20viewBox='0%200%2034%2034'"
    "%3E%3Crect%20width='34'%20height='34'%20rx='9'%20fill='%2316212e'/%3E%3Ctext%20x='16.5'%20y='24'"
    "%20font-family='Georgia,serif'%20font-size='21'%20font-weight='600'%20fill='%23fbf8f2'"
    "%20text-anchor='middle'%3EL%3C/text%3E%3Ccircle%20cx='27'%20cy='28'%20r='5.5'%20fill='%23bd5a39'"
    "/%3E%3C/svg%3E"
)


class _Source:
    """One unique cited source (deduplicated by URL)."""

    __slots__ = ("source_type", "title", "url")

    def __init__(self, url: str, title: str, source_type: SourceType) -> None:
        self.url = url
        self.title = title
        self.source_type = source_type


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _track_order(present: set[CareerTrack]) -> list[CareerTrack]:
    """Preferred order first, then any remaining tracks in enum order."""
    ordered = [t for t in _PREFERRED_ORDER if t in present]
    ordered += [t for t in CareerTrack if t in present and t not in _PREFERRED_ORDER]
    return ordered


def _collect(documents: list[CorpusDocument]) -> tuple[list[CareerTrack], dict[CareerTrack, list[_Source]], int]:
    """Deduplicate documents by URL and bucket them per track.

    Returns the ordered tracks that actually have sources, the per-track lists
    (sorted by title), and the total unique-URL count.
    """
    unique: dict[str, _Source] = {}
    tags_by_url: dict[str, set[CareerTrack]] = {}
    for doc in documents:
        if doc.source_url not in unique:
            unique[doc.source_url] = _Source(doc.source_url, doc.title, doc.source_type)
            tags_by_url[doc.source_url] = set()
        tags_by_url[doc.source_url].update(doc.track_tags)

    buckets: dict[CareerTrack, list[_Source]] = {}
    for url, source in unique.items():
        for track in tags_by_url[url]:
            buckets.setdefault(track, []).append(source)
    for sources in buckets.values():
        sources.sort(key=lambda s: s.title.lower())

    order = _track_order(set(buckets))
    return order, buckets, len(unique)


def render(documents: list[CorpusDocument]) -> str:
    """Render the full ``sources.html`` document from corpus documents."""
    order, buckets, total = _collect(documents)

    toc = "\n".join(
        f'          <a class="toc-chip" href="#{track.value}">{_esc(_TRACK_LABEL[track])} '
        f'<span class="toc-n">{len(buckets[track])}</span></a>'
        for track in order
    )

    sections: list[str] = []
    for track in order:
        items = buckets[track]
        lis = "\n".join(
            f'            <li><a href="{_esc(s.url)}" target="_blank" rel="noopener">'
            f"{_esc(s.title)}</a>"
            f'<span class="stype">{_esc(_TYPE_LABEL.get(s.source_type, s.source_type.value))}</span></li>'
            for s in items
        )
        sections.append(
            f'''      <section class="tracksec" id="{track.value}">
        <div class="wrap">
          <div class="tracksec-head">
            <div>
              <span class="eyebrow">{_esc(_TRACK_LABEL[track])}</span>
              <p class="tracksec-blurb">{_esc(_TRACK_BLURB[track])}</p>
            </div>
            <span class="tracksec-count">{len(items)} sources</span>
          </div>
          <ul class="biblist">
{lis}
          </ul>
        </div>
      </section>'''
        )
    sections_html = "\n\n".join(sections)

    return f'''<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="The full reading list behind Loop: {total}+ cited engineering blogs, interview postmortems, and practitioner essays across software, AI, ML, data, quant, and product management." />
    <meta name="robots" content="index, follow, max-image-preview:large" />
    <meta name="author" content="Shawn Liu" />
    <meta name="theme-color" content="#bd5a39" />
    <link rel="canonical" href="https://loop-study.com/sources" />
    <link rel="icon" href="{_FAVICON}" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&family=Hanken+Grotesk:wght@400;500;600;700&family=Spline+Sans+Mono:wght@400;500&display=swap" rel="stylesheet" />
    <meta property="og:site_name" content="Loop" />
    <meta property="og:type" content="website" />
    <meta property="og:url" content="https://loop-study.com/sources" />
    <meta property="og:title" content="Sources & further reading - Loop" />
    <meta property="og:description" content="The curated corpus behind Loop's study plans: {total}+ cited sources across career tracks." />
    <meta name="twitter:card" content="summary" />
    <meta name="twitter:title" content="Sources & further reading - Loop" />
    <meta name="twitter:description" content="The curated corpus behind Loop's study plans: {total}+ cited sources across career tracks." />
    <title>Sources &amp; further reading - Loop</title>
    <script type="application/ld+json">
      {{
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Sources & further reading",
        "url": "https://loop-study.com/sources",
        "description": "The curated corpus of {total}+ cited sources behind Loop's study plans, grouped by career track.",
        "isPartOf": {{ "@type": "WebSite", "name": "Loop", "url": "https://loop-study.com/" }},
        "breadcrumb": {{
          "@type": "BreadcrumbList",
          "itemListElement": [
            {{ "@type": "ListItem", "position": 1, "name": "Home", "item": "https://loop-study.com/" }},
            {{ "@type": "ListItem", "position": 2, "name": "Sources", "item": "https://loop-study.com/sources" }}
          ]
        }}
      }}
    </script>
    <style>
      :root{{--ink:#16212e;--ink-soft:#38485a;--muted:#6c7886;--muted-2:#97a0ab;--paper:#fbf8f2;--paper-2:#f4ece0;--card:#ffffff;--clay:#bd5a39;--clay-deep:#9c4527;--clay-soft:#f1ddd1;--sage:#5f7a64;--line:#e9e0d2;--line-2:#ddd2bf;--serif:'Newsreader',Georgia,serif;--sans:'Hanken Grotesk',system-ui,-apple-system,sans-serif;--mono:'Spline Sans Mono',ui-monospace,'SF Mono',Menlo,monospace;--r:16px;--r-sm:11px;--shadow-sm:0 1px 2px rgba(22,33,46,.05),0 4px 14px rgba(22,33,46,.05)}}
      *{{box-sizing:border-box}}
      html{{scroll-behavior:smooth}}
      body{{margin:0;background:var(--paper);color:var(--ink);font-family:var(--sans);font-size:16px;line-height:1.55;-webkit-font-smoothing:antialiased}}
      h1,h2,h3{{margin:0;font-family:var(--serif);font-weight:500;letter-spacing:-.015em;line-height:1.1}}
      a{{color:inherit}}
      a:hover{{color:var(--clay-deep)}}
      .wrap{{max-width:1080px;margin:0 auto;padding:0 clamp(20px,5vw,48px)}}
      .eyebrow{{font-family:var(--sans);font-size:12px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--clay-deep)}}
      .nav{{display:flex;align-items:center;gap:14px;padding:18px clamp(20px,5vw,48px);max-width:1080px;margin:0 auto}}
      .brand{{display:flex;align-items:center;gap:11px;text-decoration:none}}
      .glyph{{width:34px;height:34px;border-radius:10px;background:var(--ink);color:var(--paper);display:grid;place-items:center;font-family:var(--serif);font-size:19px;font-weight:600;position:relative}}
      .glyph::after{{content:'\\2713';position:absolute;right:-4px;bottom:-4px;width:16px;height:16px;border-radius:50%;background:var(--clay);color:#fff;font-size:9px;font-weight:800;display:grid;place-items:center;border:2px solid var(--paper)}}
      .word{{font-family:var(--serif);font-size:20px;font-weight:600}}
      .spacer{{flex:1}}
      .nav-links{{display:flex;align-items:center;gap:2px}}
      @media (max-width:760px){{.nav-links{{display:none}}}}
      .btn{{display:inline-flex;align-items:center;justify-content:center;gap:8px;font-family:var(--sans);font-weight:600;font-size:15px;padding:12px 20px;border-radius:11px;border:1px solid transparent;cursor:pointer;text-decoration:none;white-space:nowrap}}
      .btn-ghost{{background:var(--card);color:var(--ink);border-color:var(--line-2);box-shadow:var(--shadow-sm)}}
      .btn-quiet{{background:transparent;color:var(--ink-soft);padding:8px 12px}}
      .head{{padding:clamp(30px,5vw,56px) 0 clamp(20px,3vw,30px)}}
      .head h1{{font-size:clamp(30px,4.6vw,46px);margin-top:12px;max-width:20ch}}
      .head .lede{{font-size:clamp(16px,2vw,18px);color:var(--ink-soft);margin:16px 0 0;max-width:62ch}}
      .head .stat{{font-family:var(--mono);font-size:13px;color:var(--muted);margin-top:14px}}
      .toc{{display:flex;flex-wrap:wrap;gap:9px;margin-top:22px}}
      .toc-chip{{display:inline-flex;align-items:center;gap:8px;background:var(--card);border:1px solid var(--line-2);border-radius:999px;padding:7px 14px;font-size:13px;font-weight:600;color:var(--ink-soft);text-decoration:none;box-shadow:var(--shadow-sm)}}
      .toc-chip:hover{{color:var(--clay-deep);border-color:var(--clay-soft)}}
      .toc-n{{font-family:var(--mono);font-size:11px;font-weight:500;color:var(--muted-2)}}
      .tracksec{{padding:clamp(28px,4vw,44px) 0;border-top:1px solid var(--line)}}
      .tracksec:nth-child(even){{background:var(--paper-2)}}
      .tracksec-head{{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:12px}}
      .tracksec-blurb{{font-size:14.5px;color:var(--ink-soft);margin:8px 0 0;max-width:60ch}}
      .tracksec-count{{font-family:var(--mono);font-size:12px;color:var(--muted);background:var(--card);border:1px solid var(--line);border-radius:999px;padding:4px 12px;white-space:nowrap}}
      .biblist{{list-style:none;margin:22px 0 0;padding:0;columns:2;column-gap:34px}}
      @media (max-width:720px){{.biblist{{columns:1}}}}
      .biblist li{{break-inside:avoid;padding:8px 0;border-bottom:1px solid var(--line);display:flex;flex-direction:column;gap:3px}}
      .biblist a{{font-size:14px;font-weight:600;color:var(--ink);text-decoration:none;line-height:1.35}}
      .biblist a:hover{{color:var(--clay-deep)}}
      .stype{{font-family:var(--mono);font-size:10.5px;letter-spacing:.04em;color:var(--muted-2)}}
      .provenance{{padding:clamp(30px,5vw,52px) 0;border-top:1px solid var(--line)}}
      .provenance p{{font-size:14.5px;color:var(--ink-soft);max-width:64ch;margin:10px 0 0}}
      footer{{border-top:1px solid var(--line);padding:28px clamp(20px,5vw,48px)}}
      .foot-inner{{max-width:1080px;margin:0 auto;display:flex;flex-wrap:wrap;align-items:center;gap:14px;font-size:13px;color:var(--muted)}}
      .muted{{color:var(--muted)}}
    </style>
  </head>
  <body>
    <header class="nav">
      <a class="brand" href="/">
        <span class="glyph">L</span>
        <span class="word">Loop</span>
      </a>
      <span class="spacer"></span>
      <nav class="nav-links" aria-label="Primary">
        <a class="btn btn-quiet" href="/#how">How it works</a>
        <a class="btn btn-quiet" href="/#safety">Safety</a>
        <a class="btn btn-quiet" href="/how-its-built">How it&#8217;s built</a>
      </nav>
      <a class="btn btn-ghost" href="/auth/login">Sign in</a>
    </header>

    <main>
      <section class="head">
        <div class="wrap">
          <span class="eyebrow">Sources &amp; further reading</span>
          <h1>The reading list behind every plan.</h1>
          <p class="lede">
            Loop doesn&#8217;t invent advice. Its study modules are grounded in a curated corpus of
            engineering blogs, interview postmortems, and practitioner essays - snapshotted with
            attribution and used only for bounded, cited retrieval. This is the full list, grouped
            by career track.
          </p>
          <p class="stat">{total} unique sources · {len(order)} career tracks · retrieved, not generated</p>
          <div class="toc">
{toc}
          </div>
        </div>
      </section>

{sections_html}

      <section class="provenance">
        <div class="wrap">
          <span class="eyebrow">How we use these</span>
          <p>
            Each source is captured as a bounded snapshot held for research and retrieval quotation
            with attribution. Loop respects <span class="muted">robots.txt</span> when collecting,
            never republishes full articles, and cites the original whenever a passage informs a
            study module. Titles link to the original publishers - please support their work.
          </p>
        </div>
      </section>
    </main>

    <footer>
      <div class="foot-inner">
        <a class="brand" href="/">
          <span class="glyph">L</span>
          <span class="word">Loop</span>
        </a>
        <span class="muted">Interview prep, scheduled around your real life.</span>
        <span class="spacer"></span>
        <a class="muted" href="/">Home</a>
        <a class="muted" href="/how-its-built">How it&#8217;s built</a>
        <a class="muted" href="/privacy">Privacy</a>
        <a class="muted" href="/terms">Terms</a>
      </div>
    </footer>
  </body>
</html>
'''


def load_documents(corpus_db: Path) -> list[CorpusDocument]:
    """Read every corpus document from the registry, in insertion order."""
    registry = SqliteCorpusRegistry(SqliteDatabase(corpus_db))
    return registry.list_documents()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the public /sources bibliography page from the corpus."
    )
    parser.add_argument(
        "--corpus-db",
        type=Path,
        default=DEFAULT_CORPUS_DB,
        help=f"Corpus SQLite database (default: {DEFAULT_CORPUS_DB}, relative to backend/).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output HTML path (default: {DEFAULT_OUT}, relative to backend/).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Do not write; exit non-zero if the on-disk page differs from what "
            "would be generated. Useful in CI."
        ),
    )
    args = parser.parse_args(argv)
    corpus_db = args.corpus_db.resolve()
    out = args.out.resolve()

    if not corpus_db.is_file():
        print(f"error: corpus database not found: {corpus_db}", file=sys.stderr)
        return 1

    expected = render(load_documents(corpus_db))

    if args.check:
        if not out.exists():
            print(f"missing: {out}", file=sys.stderr)
            print("Run `make sources` to generate.", file=sys.stderr)
            return 1
        if out.read_text(encoding="utf-8") != expected:
            print(f"Sources page out of date: {out}", file=sys.stderr)
            print("Run `make sources` to regenerate.", file=sys.stderr)
            return 1
        return 0

    out.write_text(expected, encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
