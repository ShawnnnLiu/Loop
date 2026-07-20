# Loop landing page rework - design handoff

## Task

Rework `landing/index.html` (the Loop landing page) into a scroll-driven animated showcase, inspired by https://pi.dev/ - fetch and study that page's scroll mechanics before designing.

## What to build

Four animated scenes, one per core feature, in this order:

1. **Resume extraction** - a resume document dissolving into typed evidence chips (kind + theme tags, per `backend/src/agentic_calendar/contracts/resume_extraction.py` and the intake UI in `frontend/src/screens/Onboarding.tsx`).
2. **Strategist** - goal + availability + constraints flowing into a structured plan candidate that passes deterministic validation gates (see `frontend/src/screens/Generation.tsx` for the real run states).
3. **Grid calendar** - a week grid where proposed study blocks slide in around existing busy blocks, ending on an approval moment (model it on `frontend/src/components/WeekPlanView.tsx` and the existing `.mock-grid` markup already in the landing page).
4. **Pathway clusters** - the five pathway templates from `backend/src/agentic_calendar/templates/pathways.py` rendered as labeled theme clusters that light up as evidence maps onto them (shape reference: `backend/src/agentic_calendar/contracts/pathway_template.py`).

## Animation mechanics

Each scene slides in when the user scrolls to its trigger point, plays its animation, then fades to clear before the next scene's trigger.
Use IntersectionObserver (or CSS scroll-driven animations with a JS fallback) plus CSS transforms/opacity and inline SVG only.
No videos, GIFs, Lottie files, or canvas recordings - everything is DOM/SVG/CSS.
Animate only `transform` and `opacity` for performance.
Provide a `prefers-reduced-motion` fallback that shows each scene as a static final frame.

## Hard constraints

- The file must remain a single self-contained static HTML file: all CSS and JS inline, no build step, no npm dependencies, no CDN scripts.
  The only allowed external requests are the existing Google Fonts links.
  It is served as-is by the backend at `/`.
- Keep the existing design language exactly: the paper/clay/sage token palette, Newsreader serif headings, Hanken Grotesk body, Spline Sans Mono accents (canonical tokens: `frontend/src/styles/tokens.css`; tone reference: `landing/how-its-built.html`).
  This is a rework of layout and motion, not a rebrand.
- Preserve all content Google OAuth verification depends on: the closed-beta strip, the how-it-works and scope/consent copy, the "writes to Google Calendar only after you approve" messaging, sign-in CTAs, and the nav links to /how-its-built, privacy, and terms.
  You may restructure where this copy sits, but none of it may be removed or weakened.
- Every animation must depict real product behavior - use the referenced source files as ground truth and do not invent capabilities.
  The calendar is drafts-only until approval; keep that framing.
- The page must be fully readable with JS disabled (scenes degrade to static sections).
- No em dashes anywhere in copy; use plain dashes.

## Verify before finishing

- Open the page in a browser and scroll the full sequence.
- Check trigger points fire once and in order.
- Check `prefers-reduced-motion`.
- Check a 375px-wide viewport.
- Confirm no horizontal scroll and no layout shift from animations.

## Bundle contents

- `landing/index.html` - the file to rework (design tokens are inlined in its `<style>` block).
- `landing/how-its-built.html` - tone reference + existing SVG diagram style.
- `frontend/src/styles/tokens.css` - canonical design tokens.
- `frontend/src/screens/Onboarding.tsx` - real resume intake UI (scene 1).
- `frontend/src/screens/Generation.tsx` - real strategist run UI (scene 2).
- `frontend/src/components/WeekPlanView.tsx` - real grid calendar (scene 3).
- `backend/src/agentic_calendar/templates/pathways.py` - pathway seed content (scene 4).
- `backend/src/agentic_calendar/contracts/resume_extraction.py` - evidence record shape.
- `backend/src/agentic_calendar/contracts/pathway_template.py` - pathway template shape.

Only `landing/index.html` should be modified; everything else is read-only reference.
