"""``corpus_document`` contract.

Canonical spec: ``docs/specs/corpus-document.schema.md`` (axiom 08,
corpus-registry subsection).

A :class:`CorpusDocument` is the registered metadata record for one fetched
public-web document in the retrieval corpus: provenance, license basis, track
tags, and a content hash pinning the normalized text. The text itself is
stored by the corpus registry (``retrieval/``) next to this record — it is not
a contract field, so the metadata schema stays small and exportable.

Contract vs. registry split:

* This module owns **shape and internal consistency**: ``doc_id`` matches its
  derivation (:func:`derive_doc_id`), ``content_hash`` is a well-formed sha256
  hex digest, ``track_tags`` is non-empty and duplicate-free, and
  ``source_published_date`` is not after ``date_collected``.
* The **registry** owns what the contract cannot see: the stored text really
  hashes to ``content_hash`` (checked on register and read), registered
  documents are immutable, and re-registering an identical document is a
  no-op.

``source_type`` reuses :class:`~agentic_calendar.contracts.source_claim.SourceType`
and is computed by the existing URL-rule classifier
(``source_claims/classification.py``) at ingestion — never by LLM judgment.
The contract checks only that the value is a known member.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agentic_calendar.contracts.career_track import CareerTrack
from agentic_calendar.contracts.source_claim import SourceType

#: sha256 hex digest — 64 lowercase hex chars.
CONTENT_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")

#: ``doc_`` + first 16 hex chars of the derivation hash.
DOC_ID_PATTERN = re.compile(r"^doc_[0-9a-f]{16}$")


def content_hash_for(text: str) -> str:
    """sha256 hex digest of ``text`` (UTF-8) — the single hash definition.

    Callers hash the *normalized* text; normalization itself is the ingestion
    tool's job and is defined there, not here.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def derive_doc_id(source_url: str, date_collected: date) -> str:
    """Derive the stable document id from provenance.

    ``doc_`` + first 16 hex chars of sha256 over
    ``"{source_url}\\n{date_collected.isoformat()}"``. The same URL fetched on
    a new day is a new document (pages change); the same URL on the same day
    is the same document (hash-idempotent re-ingest).
    """
    digest = hashlib.sha256(
        f"{source_url}\n{date_collected.isoformat()}".encode()
    ).hexdigest()
    return f"doc_{digest[:16]}"


class CorpusDocument(BaseModel):
    """Registered metadata for one corpus document (text lives in the registry)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str = Field(pattern=DOC_ID_PATTERN.pattern)
    source_url: str = Field(min_length=1)
    source_type: SourceType
    license_note: str = Field(min_length=1)
    date_collected: date
    source_published_date: date | None = None
    track_tags: list[CareerTrack] = Field(min_length=1)
    content_hash: str = Field(pattern=CONTENT_HASH_PATTERN.pattern)
    title: str = Field(min_length=1)

    @model_validator(mode="after")
    def _doc_id_matches_derivation(self) -> CorpusDocument:
        expected = derive_doc_id(self.source_url, self.date_collected)
        if self.doc_id != expected:
            raise ValueError(
                f"doc_id {self.doc_id!r} does not match its derivation from "
                f"source_url + date_collected (expected {expected!r})"
            )
        return self

    @model_validator(mode="after")
    def _track_tags_unique(self) -> CorpusDocument:
        seen: set[CareerTrack] = set()
        duplicates: set[str] = set()
        for tag in self.track_tags:
            if tag in seen:
                duplicates.add(tag.value)
            seen.add(tag)
        if duplicates:
            raise ValueError(f"track_tags contains duplicates: {sorted(duplicates)}")
        return self

    @model_validator(mode="after")
    def _published_not_after_collected(self) -> CorpusDocument:
        if (
            self.source_published_date is not None
            and self.source_published_date > self.date_collected
        ):
            raise ValueError(
                f"source_published_date ({self.source_published_date}) must not "
                f"be after date_collected ({self.date_collected})"
            )
        return self
