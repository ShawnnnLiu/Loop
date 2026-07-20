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

The wizard is five steps (Goal → Time & constraints → **Résumé & profile** →
**Your story** → Connect); **Résumé & profile** is step 2 (deep-linkable as
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

## The story loop (narrative pathways)

The story layer turns the confirmed profile into a **package**: curated
pathways whose evidence slots (pillars) fill from confirmed evidence, with the
gaps becoming what the plan builds toward.
Every count, ranking, and slot state on screen is the deterministic
`narrative/` kernel over your stored evidence — no LLM participates in any of
them.
The only LLM touches are two display-only prose notes that *decorate* that
deterministic picture and can never change it.

1. **Tag your evidence (step 2, Résumé & profile).** Extraction proposes a
   `kind` and `theme_tags` for each experience item from the closed
   vocabularies (`GET /api/evidence-vocabulary` is the oracle for the
   dropdowns). Edit freely; "no tag" is always valid.
2. **Your story (step 3).** The wizard ranks the pathway cards over your draft
   evidence (`POST /api/onboard/pathways`, persistence-free), each showing its
   honest "n of m pillars" count and per-pillar filled/partial/empty state.
   A short **fit note** (`POST /api/pathways/fit-notes`) loads under each card
   a moment later — 2–3 sentences on how your evidence carries the pillars. It
   is supplementary: the cards render and rank without it, and an LLM failure
   just omits it.
3. **Choose a story.** Selecting a pathway (or skipping — skipping keeps
   today's product, byte-identical) pins it to the registry version. On the
   live server a change re-runs generation so up to `max_slot_modules` modules
   name the pillars they build toward. Skipping stores nothing.
4. **Watch the pillars fill.** On the Progress screen's **Your story** panel,
   **Mark evidence** appends a confirmed artifact (`POST /api/evidence`) — the
   story-layer analog of the approval gate. Finishing a study task never fills
   a pillar; only confirming real work here does. The matching pillar flips to
   filled on the next read, deterministically.
5. **Story summary (user-initiated).** On the same panel, **Summarize** writes
   a short "where your package stands" paragraph (`POST /api/story-summary`)
   from the selected pathway's pillar states. It is generated only when you
   ask, never persisted, and never restates the count as a score.

On the keyless dev server the two prose notes come from the deterministic
fixture twin (fast, offline); the hosted deployment runs them on
`claude-haiku-4-5`, logged with prompt/response hashes only. Either way the
prose is scanned before it is shown: no prestige/tier language, no
psychological labels, and no numerals presented as a score.
