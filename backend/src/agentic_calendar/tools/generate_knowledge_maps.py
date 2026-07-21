"""Generate the committed knowledge-map artifact from curated inputs.

The ``export_schemas`` doctrine, applied to maps (``07-tree-generation.md``): a
deterministic generator, a single committed output, drift reviewable in PRs.

For every registered pathway this runs ``narrative.generation.generate_map`` over
the pinned skill taxonomy and curated skill grouping, and writes one artifact
keyed by ``pathway_id`` to ``backend/pathways/knowledge_maps.json``. The artifact
stamps the ``skill_grouping_version``, ``taxonomy_version`` and pathway-registry
version so a stale input is caught by ``--check``.

Usage::

    uv run python -m agentic_calendar.tools.generate_knowledge_maps            # write
    uv run python -m agentic_calendar.tools.generate_knowledge_maps --check    # CI guard

The CLI is deterministic: the same curated inputs produce byte-identical JSON.
``--check`` writes nothing and exits non-zero if the committed artifact differs
from a fresh regeneration - the same guard shape as ``export_schemas --check``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from agentic_calendar.contracts.common_types import KnowledgeNodeKind
from agentic_calendar.narrative.generation import (
    ADVISORY_MIN_SKILL_NODES,
    MapGenerationError,
    generate_map,
)
from agentic_calendar.skill_taxonomy import load_skill_grouping, load_taxonomy
from agentic_calendar.templates import (
    DEFAULT_KNOWLEDGE_MAPS_PATH,
    PATHWAY_REGISTRY_VERSION,
    list_pathways,
)


def render_artifact() -> str:
    """Return the canonical artifact JSON for every registered pathway.

    Deterministic: pathways in registry order, each map already canonically
    ordered by the generator, keys sorted, no timestamps.
    """
    taxonomy = load_taxonomy()
    grouping = load_skill_grouping()
    maps: dict[str, object] = {}
    for template in list_pathways():
        kmap = generate_map(template, grouping, taxonomy)
        maps[template.pathway_id] = kmap.model_dump(mode="json")
    artifact = {
        "skill_grouping_version": grouping.skill_grouping_version,
        "taxonomy_version": grouping.taxonomy_version,
        "pathway_registry_version": PATHWAY_REGISTRY_VERSION,
        "maps": maps,
    }
    return json.dumps(artifact, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _advisory_lines() -> list[str]:
    """Advisory (never failing) notes: maps thinner than the soft floor."""
    taxonomy = load_taxonomy()
    grouping = load_skill_grouping()
    lines: list[str] = []
    for template in list_pathways():
        kmap = generate_map(template, grouping, taxonomy)
        skill_nodes = sum(
            1 for n in kmap.nodes if n.kind is KnowledgeNodeKind.SKILL
        )
        if skill_nodes < ADVISORY_MIN_SKILL_NODES:
            lines.append(
                f"advisory: {template.pathway_id} has {skill_nodes} skill nodes "
                f"(< {ADVISORY_MIN_SKILL_NODES}); consider adding seeds"
            )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate the committed knowledge-map artifact from curated inputs."
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_KNOWLEDGE_MAPS_PATH,
        help="Output file (default: backend/pathways/knowledge_maps.json).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "Do not write; exit non-zero if the committed artifact differs from "
            "a fresh regeneration. Useful in CI."
        ),
    )
    args = parser.parse_args(argv)
    out = args.out.resolve()

    try:
        rendered = render_artifact()
    except MapGenerationError as exc:
        print(f"generation failed [{exc.reason_code.value}]: {exc.detail}", file=sys.stderr)
        return 2

    if args.check:
        if not out.exists():
            print(f"missing knowledge-maps artifact: {out}", file=sys.stderr)
            return 1
        current = out.read_text(encoding="utf-8")
        if current != rendered:
            print(
                f"knowledge-maps artifact is stale: {out}\n"
                "run `make maps` and commit the result.",
                file=sys.stderr,
            )
            return 1
        print(f"knowledge-maps artifact up to date: {out}")
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(rendered, encoding="utf-8")
    print(f"wrote {out}")
    for line in _advisory_lines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
