# Dogfooding Walkthrough

How to drive the product loop by hand, as a user. Created with résumé intake
RI-E — earlier phases dogfooded through the operator CLIs and the hosted
deployment; this doc starts with the onboarding wizard because the résumé
extract step is the first flow worth a scripted walkthrough. Extend it as
later flows earn one.

## Boot

From `backend/` (needs a built `frontend/dist`; run `npm run build` in
`frontend/` first):

```bash
uv run python -m agentic_calendar.app.web
```

This is the **keyless dev server**: fixture LLM nodes, in-memory calendar, no
Anthropic key, no Google connection, single auto-onboarded demo user. The SPA
is at `http://127.0.0.1:8000/app`. The hosted deployment runs the same flow
over the real `claude-haiku-4-5` adapter; everything below behaves
identically except that extraction quality is a real model proposal instead
of a deterministic alias scan.

## Onboarding: the résumé extract step

The wizard is four steps; **Résumé & profile** is step 2 (deep-linkable as
`/app?step=2`).

1. Paste a résumé into the textarea (minimum 50 characters). Nothing happens
   on paste — extraction is an explicit button press, never automatic.
2. Press **Extract**. One extraction runs under an `intake-` run id (on the
   live adapter that is one Haiku call, logged with prompt/response hashes
   only — the résumé text is never stored anywhere except your own profile
   field). Nothing is persisted by this call.
3. The proposal fills five editable sections, labeled by how they were
   produced:
   - *extracted* — experience entries and skills, groundedness-checked: every
     value is a literal span of your résumé text;
   - *inferred* — strengths and weak areas (weak areas are flagged "a
     guess" and come only from the closed skill-taxonomy vocabulary);
   - *suggested* — target-company **categories** (never company names, never
     prestige tiers).
4. Skills the taxonomy does not recognize appear as "not recognized" chips
   (keep or remove them yourself — they are never silently promoted to
   canonical skills). Target level is always manual.
5. Edit anything: add or delete experience rows, change chips, rewrite text.
   Re-extracting over edited sections asks for confirmation before replacing
   them.
6. Finish the wizard. Only now does anything persist, via the existing
   `POST /api/onboard` — exactly what you confirmed on screen, nothing else.

## When extraction fails

A failed LLM call (refusal, truncation, rate limit, exhausted repair loop, …)
shows a banner with the typed `reason_code` — extraction returns HTTP 200
with `status: "failed"`; only a malformed request is a 422. The wizard keeps
working: type the same fields by hand, or skip the résumé entirely. Manual
entry is the contract; extraction is an enhancement, never a blocker.

## Verifying what persisted

`GET /api/me` (or reloading the SPA) echoes the confirmed profile — useful
for checking that an edit-then-finish round-trip stored your edits, not the
raw proposal.
