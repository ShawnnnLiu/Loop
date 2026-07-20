# T-D — Docs Claim Sweep + Gates

Align every written claim with the new reality. The bs-detector audit
pattern in this repo flags claims-vs-reality gaps; the old "content-free
summary" claims must not survive.

## Claim sweep

Must change (the only places claiming titles never reach the calendar):

- `calendar_writer/google_adapter.py` module docstring bullet
  "**No raw content.**" (`:16-20`) — rewritten in T-A; verify final
  wording states: outbound task titles allowed on the user's own dedicated
  calendar (user-approved, 2026-07-16); descriptions never written; the
  four metadata keys unchanged; inbound titles never read back or stored.
- `EVENT_SUMMARY` docstring (`:42`) — now describes a *fallback*.

Grep before finishing:

```bash
grep -rn "content-free\|never reach the external calendar" backend/src backend/tests docs/
```

Every remaining hit must be either updated or genuinely still true
(e.g., statements about descriptions, or about the inbound rule).

Optional, one sentence: `docs/axioms/06-calendar-safety.md` under the
write flow — the event summary is the task's title (outbound posture
change; descriptions never written). The existing lines stay true and
untouched: `:122` ("Duplicate detection uses metadata, not title
matching") and `:134` (rollback "not fuzzy title matching").

Leave untouched (all inbound-storage or sponsor-exposure rules,
unaffected by outbound titles):

- `CLAUDE.md` "Do not store raw calendar event titles or descriptions"
- `AGENTS.md:91` (same sentence)
- `docs/axioms/07-telemetry-and-drift.md:19`
- `docs/axioms/00-product-thesis.md:97`
- `docs/axioms/09-cost-and-metrics.md:196` ("Raw calendar title exposure
  rate = 0" — sponsor-overexposure metric group, about *sponsor* surfaces)
- All sponsor/telemetry/reconciliation specs

Explicit non-changes to state in the session summary: **no**
`docs/specs/` edits, **no** contract model changes, **no** `make schemas`
run, **no** canonicalization change.

## Gates

From `backend/`:

```bash
uv run make test-fast    # focused first
uv run make check        # full gate: tests + lint + typecheck + boundaries
```

Then `graphify update .` (repo convention after code changes).

No frontend changes: the SPA renders titles from `DraftView.task_titles`
already; nothing in `frontend/` references the summary string.

## Wrap-up checklist

- [ ] All three create sites pass titles (manager `:786`, `:557`, `:619`).
- [ ] Both `retry_write` call sites pass the map (`:2004`, `:2014`).
- [ ] `_to_record` still never populates `summary`; inbound-rule pin test in place.
- [ ] Claim-sweep grep clean.
- [ ] `make check` green; test count noted in summary.
- [ ] Live follow-up (post-merge, dogfood): next real write on Fly shows
      properly-titled events; pre-existing events keep the generic title
      until replaced by a replan (per the new-writes-only decision).
