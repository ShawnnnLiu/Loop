# RI-C · App Layer and API

One commit. Wires the node into the composition root and exposes one
persistence-free endpoint. `app/` never constructs SDK transports itself
(`environment.py:10-14`) — that stays true.

## 1. Environment / bundle wiring (`app/environment.py`)

- Add a `ResumeIntakeNode` Protocol next to the existing four (`:126-194`):
  `run(*, run_id: str, intake: ResumeIntakeInput) -> ResumeExtraction`.
- `LlmNodeBundle` (`:197-204`) grows a fifth member `resume_intake`.
- `NodeDependencies` / `NodesFactory` shapes are unchanged; both factories in
  `tools/run_cycle.py` are updated:
  - `_fixture_bundle` (`:76-101`): construct `FixtureResumeIntake`.
  - `_live_bundle` (`:104-143`): construct `AnthropicResumeIntake` on the
    shared `AnthropicMessagesTransport` (same `ANTHROPIC_API_KEY` guard).
- Keyless demo server `app/web/__main__.py:35` picks the fixture bundle
  automatically — no change beyond the bundle growing; verify the demo boots.

## 2. Service method (`app/cycle.py`)

`CycleService.extract_resume(user_id: str, payload: Mapping) ->
ExtractResumeResult`:

1. Validate the payload into `ResumeIntakeInput`, forcing
   `user_id` to the acting user (same trust boundary as onboard,
   `routes_cycle.py:136-140`). Invalid → the router's standard 422 path.
   Resolve the career track from `draft_context.target_role`
   (deterministic map, `skill_taxonomy/`), load the pinned taxonomy, and
   fill `allowed_weak_spots` with the track slice (union of tracks when
   unresolvable).
2. Mint `run_id = f"intake-{id_generator()}"` — documented in the
   llm-call-log spec (RI-A). This is a pre-run LLM call; it never touches
   run/checkpoint state.
3. `env.nodes.resume_intake.run(run_id=run_id, intake=intake)`.
4. Success → normalize `proposal.skills` through the taxonomy kernel, then
   `ExtractResumeResult(status="ok", proposal=extraction,
   skills_canonical=[{skill_id, display_name, surface}],
   skills_unmatched=[...], taxonomy_version=..., run_id=run_id)`. Unmatched
   surfaces are returned flagged, never silently promoted (per
   `06-skill-taxonomy.md`).
5. `LLMGenerationError`/`LLMNodeError` → failure result with the error's
   typed `reason_code` and a short detail string (mirror the `_llm_failure`
   mapping, `cycle.py:950-951`, but WITHOUT routing to
   `UNRECOVERABLE_ERROR` — there is no run to fail; extraction failure is a
   local, retryable UX event).

**No store reads or writes.** The method does not touch
`save_onboarding`; profile persistence remains exclusively
`CycleService.onboard()`.

`ExtractResumeResult` goes in `app/results.py` following the existing result
dataclass/model style (`OnboardResult`, `MeResult`).

## 3. Route (`app/web/routes_cycle.py`)

- `POST /api/onboard/extract` → `service.extract_resume(...)`, session user
  via `require_user`, same JSON response conventions as the rest of the
  router (`:1-18`): HTTP 200 with `status`/`reason_code` for LLM failures,
  422 for contract-invalid payloads (résumé too short/long, bad draft
  context).
- Request body: `{ resume_text, draft_context: { goal?, target_role?,
  experience_level?, timeline_weeks?, weekly_hours? } }`.
- Response body: `{ status, proposal?, skills_canonical?, skills_unmatched?,
  taxonomy_version?, reason_code?, detail?, run_id }` — proposal is the
  `ResumeExtraction` JSON verbatim; the normalized-skills view rides beside
  it; the frontend maps field groups to provenance labels.

Rate limiting beyond auth is deliberately out of scope for MVP (explicit
button + Haiku pricing); note it in the route docstring as a deferred
concern rather than silently omitting it.

## 4. Onboard path (unchanged, verify)

`POST /api/onboard` already round-trips the whole `UserProfile`; the new
`experience`/`skills` fields ride the existing payload with **zero route or
service changes** (additive contract change from RI-A). `GET /api/me`
returns them for wizard prefill automatically. Re-onboard semantics
(`cycle.py:294-304` — preserve `created_at`, preserve sync opt-in) are
untouched; add one regression test proving a re-onboard preserves
`experience`/`skills` round-trip.

## 5. Tests

- Route tests: happy path with fixture bundle; 422 for a 10-char résumé;
  LLM failure surfaces `reason_code` with HTTP 200; `user_id` in the body is
  ignored in favor of the session user; **no** `app_documents` row appears
  after extract (persistence-free assertion).
- Service tests: run_id prefix; failure mapping does not mutate any store;
  fixture-bundle determinism through the service layer; fake-skill résumé
  ("Flurbo.js expert") lands in `skills_unmatched`, absent from
  `skills_canonical`; track resolution fallback (unmappable role → union
  vocabulary).
- Demo-server test (existing pattern for `__main__`): boots keyless with the
  five-node bundle.

Gate: `uv run make check` green.
