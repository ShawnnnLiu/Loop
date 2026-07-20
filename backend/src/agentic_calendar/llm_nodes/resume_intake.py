"""ResumeIntake node — fixture-backed fake (résumé intake RI-B).

The ResumeIntakeNode's job is to turn a pasted résumé plus draft onboarding
answers into a structured :class:`ResumeExtraction` proposal the user reviews
and edits. :class:`FixtureResumeIntake` is the keyless-dev twin: deterministic,
zero network, honest about what it fakes —

- ``skills``: a word-boundary scan of the résumé against the taxonomy alias
  table (the same vocabulary the real adapter's validator uses — one
  vocabulary, zero drift). Grounded by construction: every emitted surface is
  a span of the résumé text. The alias data arrives as a plain mapping via
  the constructor; this module never imports the ``skill_taxonomy/`` kernel
  (``.importlinter`` enforces it).
- ``experience``: the first ≤3 lines matching a trivial
  ``<title> at|·|— <org>`` pattern — a real parser is exactly what the LLM
  node exists to replace. Each item's ``kind`` comes from a small
  title-keyword map (default ``work``), and its ``theme_tags`` are the
  ``allowed_themes`` whose text is a grounded substring of the résumé —
  grounded by construction like ``skills``, never coined. When
  ``allowed_themes`` is empty the fixture proposes no tags.
- ``known_strengths`` / ``inferred_weak_spots`` /
  ``target_company_categories``: canned lists keyed by
  ``draft_context.target_role`` with a generic fallback (the fixture
  Strategist's canned-syllabus idea). Weak spots honor the closed-choice
  invariant: when ``allowed_weak_spots`` is non-empty, only members of it are
  ever returned (canned picks are filtered to it; if none survive, the first
  two allowed entries are used).

Input is re-validated at the boundary and the output is constructed through
the ``ResumeExtraction`` contract (``base.py`` re-validation policy), so a
malformed bundle or a fixture bug is caught here, not three layers deep.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

from agentic_calendar.contracts._dedup import casefold_key
from agentic_calendar.contracts.common_types import EvidenceKind
from agentic_calendar.contracts.resume_extraction import ResumeExtraction
from agentic_calendar.contracts.resume_intake_input import ResumeIntakeInput
from agentic_calendar.contracts.user_profile import THEME_TAGS_MAX_PER_ITEM, ExperienceItem

#: Canned inferred/suggested lists per normalized ``target_role``; the twin's
#: analogue of the fixture Strategist's canned syllabi. Weak-spot values are
#: taxonomy display names so they survive the allowed-vocabulary filter.
_CANNED_BY_ROLE: dict[str, dict[str, list[str]]] = {
    "backend swe": {
        "known_strengths": ["backend services", "API design"],
        "inferred_weak_spots": ["System design", "Dynamic programming"],
        "target_company_categories": ["infra startups", "big tech"],
    },
    "ml engineer": {
        "known_strengths": ["model training pipelines"],
        "inferred_weak_spots": ["MLOps", "System design"],
        "target_company_categories": ["ML platform companies", "AI-native products"],
    },
    "ai engineer": {
        "known_strengths": ["LLM application prototyping"],
        "inferred_weak_spots": ["Evals", "System design"],
        "target_company_categories": ["AI-native products", "developer-tools companies"],
    },
}

_GENERIC_CANNED: dict[str, list[str]] = {
    "known_strengths": ["shipped real projects"],
    "inferred_weak_spots": ["System design", "Data structures & algorithms"],
    "target_company_categories": ["product startups", "big tech"],
}

#: ``<title> at|·|— <org>`` — the deliberately trivial experience-line shape.
_EXPERIENCE_LINE = re.compile(
    r"^\s*(?P<title>.{1,120}?)\s+(?:at|·|—)\s+(?P<org>.{1,160}?)\s*$"
)

_MAX_EXPERIENCE_ITEMS = 3
_MAX_SKILLS = 40

#: Title-keyword → evidence ``kind``, first match wins (default ``work``).
#: A deliberately shallow heuristic: the deterministic twin does not read the
#: whole résumé, so it classifies from the title alone — the real Haiku node
#: is exactly what replaces this.
_KIND_KEYWORDS: tuple[tuple[str, EvidenceKind], ...] = (
    ("volunteer", EvidenceKind.VOLUNTEERING),
    ("research", EvidenceKind.RESEARCH),
    ("project", EvidenceKind.PROJECT),
    ("coursework", EvidenceKind.COURSEWORK),
    ("scholar", EvidenceKind.AWARD),
    ("award", EvidenceKind.AWARD),
    ("president", EvidenceKind.LEADERSHIP),
    ("captain", EvidenceKind.LEADERSHIP),
    ("lead", EvidenceKind.LEADERSHIP),
)


def _normalize_key(text: str) -> str:
    return " ".join(text.lower().split())


def _alias_pattern(alias: str) -> re.Pattern[str]:
    # Word-boundary-ish matching on lowered text. ``+``/``#`` join the
    # boundary classes so alias "c" never matches inside "c++"/"c#", and
    # short aliases ("go", "r", "ml") never match inside ordinary words.
    return re.compile(rf"(?<![a-z0-9+#]){re.escape(alias)}(?![a-z0-9+#])")


class FixtureResumeIntake:
    """Fake ResumeIntake node; deterministic and grounded by construction."""

    def __init__(self, *, taxonomy_aliases: Mapping[str, str]) -> None:
        """``taxonomy_aliases`` maps lowercase-normalized alias → canonical
        display name — plain data extracted from the taxonomy registry by the
        composition root (never the kernel itself; see module docstring)."""
        if not taxonomy_aliases:
            raise ValueError("FixtureResumeIntake requires a non-empty alias mapping")
        self._aliases = dict(taxonomy_aliases)

    def run(self, *, run_id: str, intake: ResumeIntakeInput) -> ResumeExtraction:
        # Accepted for protocol parity; not used by the deterministic fake.
        del run_id
        # Re-validate at the boundary so an object built around the contract
        # (e.g. ``model_construct``) is rejected before it shapes output.
        intake = ResumeIntakeInput.model_validate(intake.model_dump(mode="json"))

        canned = _GENERIC_CANNED
        if intake.draft_context.target_role is not None:
            canned = _CANNED_BY_ROLE.get(
                _normalize_key(intake.draft_context.target_role), _GENERIC_CANNED
            )

        # Constructing through the contract re-validates the output at the
        # boundary (bounds, uniqueness) before it leaves this method.
        theme_tags = _pick_theme_tags(intake.resume_text, intake.allowed_themes)
        return ResumeExtraction(
            experience=_scan_experience(intake.resume_text, theme_tags),
            skills=_scan_skills(intake.resume_text, self._aliases),
            known_strengths=list(canned["known_strengths"]),
            inferred_weak_spots=_pick_weak_spots(
                canned["inferred_weak_spots"], intake.allowed_weak_spots
            ),
            target_company_categories=list(canned["target_company_categories"]),
        )


def _scan_skills(resume_text: str, aliases: Mapping[str, str]) -> list[str]:
    """Surfaces of the résumé that match taxonomy aliases, in résumé order.

    At most one surface per canonical display name (the earliest hit), so
    "python" and "python3" in one résumé yield one skill, not two.
    """
    lowered = resume_text.lower()
    earliest: dict[str, tuple[int, str]] = {}
    for alias in sorted(aliases):
        match = _alias_pattern(alias).search(lowered)
        if match is None:
            continue
        display = aliases[alias]
        surface = resume_text[match.start() : match.end()]
        if display not in earliest or match.start() < earliest[display][0]:
            earliest[display] = (match.start(), surface)
    ordered = sorted(earliest.values())
    return [surface for _position, surface in ordered][:_MAX_SKILLS]


def _classify_kind(title: str) -> EvidenceKind:
    """Shallow title-keyword classification; ``work`` when nothing matches."""
    lowered = title.lower()
    for keyword, kind in _KIND_KEYWORDS:
        if keyword in lowered:
            return kind
    return EvidenceKind.WORK


def _pick_theme_tags(resume_text: str, allowed: list[str]) -> list[str]:
    """Allowed themes whose text is a grounded substring of the résumé.

    Grounded by construction (like ``skills``): a theme is proposed only when
    its literal string appears in the résumé, so the fake never coins one.
    Capped at the per-item maximum and de-duplicated case-insensitively; the
    same résumé-wide set is attached to every extracted item, since the
    trivial parser has no per-item text to distinguish them.
    """
    if not allowed:
        return []
    lowered = resume_text.lower()
    picked: list[str] = []
    seen: set[str] = set()
    for theme in allowed:
        key = casefold_key(theme)
        if key in seen or theme.lower() not in lowered:
            continue
        seen.add(key)
        picked.append(theme)
        if len(picked) == THEME_TAGS_MAX_PER_ITEM:
            break
    return picked


def _scan_experience(resume_text: str, theme_tags: list[str]) -> list[ExperienceItem]:
    items: list[ExperienceItem] = []
    seen: set[tuple[str, str]] = set()
    for line in resume_text.splitlines():
        match = _EXPERIENCE_LINE.match(line)
        if match is None:
            continue
        title = match.group("title").strip()
        # Trim trailing annotations ("Acme Corp (2019-2023)") — the kept
        # prefix is still a résumé span, so groundedness holds.
        organization = re.split(r"[(,;|]", match.group("org"))[0].strip()
        if not title or not organization or len(organization) > 120:
            continue
        key = (title.lower(), organization.lower())
        if key in seen:
            continue
        seen.add(key)
        items.append(
            ExperienceItem(
                title=title,
                organization=organization,
                kind=_classify_kind(title),
                theme_tags=list(theme_tags),
            )
        )
        if len(items) == _MAX_EXPERIENCE_ITEMS:
            break
    return items


def _pick_weak_spots(canned: list[str], allowed: list[str]) -> list[str]:
    """Canned picks filtered to the allowed vocabulary (closed choice).

    Returns the ALLOWED list's spelling so the result is canonical by
    construction; with no vocabulary restriction the canned list passes
    through unchanged.
    """
    if not allowed:
        return list(canned)
    by_key = {_normalize_key(item): item for item in allowed}
    picked = [by_key[key] for c in canned if (key := _normalize_key(c)) in by_key]
    return picked if picked else list(allowed[:2])
