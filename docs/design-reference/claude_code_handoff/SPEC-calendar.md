# SPEC · Calendar

The main app screen. **Google Calendar owns scheduling**; Tandem surfaces tasks & milestones and writes accepted blocks into gcal. Three stacked regions: milestone track → week grid + day rail.

Reference component: `reference/calendar.jsx` → `reference/preview.html` (section 02). Data shapes: `DATA-MODEL.md` (`Block`, `Milestone`, `BlockState`).

## Layout (top → bottom)
1. **Product topbar** (`ProductTopbar`) — brand · nav (Today / **Week** / Milestones / Plan) · **"Google Calendar synced · 2m ago"** pill (green dot; driven by `CalendarLink.syncStatus`) · ⌘K · avatar.
2. **Milestone bar** (`MilestoneBar`) — a horizontal **milestone track** for the program ("Undergrad applications, Class of 2027"): done (✓) → active (◔, e.g. "Personal essay · 60%") → todo, connected by links. Right side: target ("Nov 1, 2026 · EA · ~21 wks").
3. **Body** = two columns: **week grid (≈1.62fr)** + **day rail (1fr)**.

## Week grid (`DayColumn` × 7)
Each day column: dow + date number, a meta line ("5 to go" / "all done" / "rest" / "milestone"), then stacked **blocks**. The selected day (Wed) is emphasized (`.sel`), today gets `.today`, rest days `.rest`. Each block shows time + name, styled by **state** (see grammar below). "click a day to expand →" feeds the rail.

## Day rail (`DayRail`) — the selected day, expanded
- Header: "Selected · today", H1 "Wed, Jul 8", a status line ("6 tasks · 1 done · 2 proposed · **on track**" — the on-track badge comes from deterministic drift detection), and a **"Accept 2 proposed"** batch button.
- A scrolling list of **rail items**, each with time, title, meta, optional **"WHY"** rationale block (model-generated), and **state-specific actions**:
  - `proposed` → **Edit** + **Accept**
  - `accepted` → **Mark done**
  - `done` → "logged ✓" chip
  - `locked` → "gcal" chip (e.g. "Café shift · from Google Calendar · can't be moved")
- Legend + keyboard hints at the bottom of the grid: **↵ accept · D done · R reschedule**.

## Block state grammar (the core concept — same as DATA-MODEL §4)
| State | Calendar/rail look | Action available |
|---|---|---|
| **proposed** | dashed clay outline | Accept / Edit |
| **accepted** | solid card (on gcal) | Mark done |
| **done** | ink/struck · "logged ✓" | none (immutable record) |
| **locked** | muted · 🔒 / "gcal" | none (external event) |
| **rest** | faint italic "Rest day" | none |

## Behavior to implement
- **Accept** (single or "Accept N proposed") → `proposed→accepted`, **writes the block to Google Calendar** (idempotent), returns a 60-second **undo** window.
- **Mark done** → `accepted→done`, logs **actual duration** (telemetry: "30m planned · 26m actual"). Feeds calibration + milestone progress.
- **Reschedule** (R) → deterministic move that **respects busy windows, locked gcal events, and quiet hours**; never silently mutates an external event.
- **Locked blocks** are imported from gcal and immovable — the planner routes around them.
- **Drift / "on track"** is rule-based (missed % + reschedule count), not a model call.
- The week is addressable (`/weeks/:isoWeek`); ←/→ paginate; "Today" jumps back.
- Everything renders off `Block.state` — get the state machine right and the UI is mostly a projection of it.
