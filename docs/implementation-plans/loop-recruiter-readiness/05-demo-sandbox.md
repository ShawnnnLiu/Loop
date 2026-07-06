# 05 · Read-Only Demo Sandbox — DEFERRED

A "Try the demo" button that lets a visitor click through the review/approve
flow themselves, with calendar writes stubbed. The draft ranked this last
("worth doing only after 1–4; the video covers most of the value at a
fraction of the effort") — that ranking stands. Do not start this until the
video has been live long enough to judge whether it's insufficient.

## Refinement: most of it already exists

The web draft assumed a from-scratch build. In fact the **keyless dev
server** (`uv run python -m agentic_calendar.app.web`) already runs the full
SPA against fixture LLM nodes and a fake calendar adapter — a single-user
demo of the whole loop with zero API spend and zero Google access. The real
remaining work is *hosting* that safely for anonymous visitors:

1. **Per-visitor isolation.** A `demo` session mode that builds an ephemeral
   in-memory environment per visitor (the in-memory store wiring already
   exists — `app/environment.py:284`), TTL-expired, never touching the
   shared SQLite volume.
2. **Zero external calls, structurally.** The demo composition root must be
   constructed without the Anthropic key and without OAuth — fixture
   strategist/planner + fake calendar only. Not "flags that skip calls":
   a root that *cannot* make them.
3. **Seeded state.** A believable profile, busy calendar, and a
   mid-loop plan so the visitor lands somewhere interesting (the Week review
   screen), not at an empty onboarding form. Optionally seed one drifted
   week so the replan surface is reachable.
4. **Abuse safety.** Rate-limit demo-session creation; cap concurrent demo
   environments; no persistence, no uploads (disable résumé paste in demo
   mode or discard it).
5. **Honest labeling.** A persistent "Demo — synthetic data, no real
   calendar" banner. The demo must not present fixture LLM output as live
   model quality; say so in the banner or tooltip.

## Axiom/spec implications

None to the engine — the demo root composes existing fakes. The no-silent-
writes axiom is trivially upheld (there is no calendar). If demo mode wants
recorded *real* model outputs instead of fixtures for showcase quality,
replaying committed eval recordings is the sanctioned source (axiom 22's
recordings are already public-repo artifacts); that's a nice-to-have, not v1.

## Entry criteria (all must be true before starting)

- Increments 01–04 shipped.
- Evidence the video isn't enough (e.g., recruiter feedback asking to "try
  it").
- User explicitly green-lights the effort (2–4 days) and the small attack
  surface a public anonymous mode adds.
