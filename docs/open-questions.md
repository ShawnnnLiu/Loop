# Open Questions

These questions are tracked alongside the axioms. Resolving them refines product scope but must not change the deterministic invariants.

1. **Initial target user segment** — Should the first wedge be new-grad SWE candidates, experienced engineers, or general career switchers?
2. **Company-specific interview prep** — Should it be part of the MVP or held for Phase 2 / Phase 4?
3. **Calendar provider** — Which provider should be supported first? (Default: Google Calendar.)
4. **User editing before approval** — How much editing of a draft schedule should be allowed before calendar approval?
5. **Web vs mobile** — Should the product start as web-only before mobile?
6. **Onboarding question set** — What exact onboarding questions are required to generate a good first plan?
7. **Schedule quality threshold** — What is the minimum acceptable schedule quality before showing the user a draft?
8. **Privacy promises** — Which privacy promises should be made explicitly in the product UI?
9. **Task completion model** — Should completion be binary, duration-based, or include subjective difficulty ratings?
10. **One active goal** — Should the first version support only one active goal per user?

## How to Resolve

Resolutions should be:

- Compatible with `axioms/00-product-thesis.md` and `axioms/01-system-boundaries.md`.
- Tracked in `decisions/` when the choice is irreversible or expensive to change.
- Reflected in the relevant `axioms/`, `specs/`, and `implementation-plans/` docs.

Open questions must never become reasons to weaken determinism, calendar safety, or privacy.

## Related Docs

- `axioms/00-product-thesis.md`
- `axioms/10-mvp-roadmap.md`
- `decisions/`
