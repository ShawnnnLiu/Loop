# SPEC · Agent

A **docked right rail** — always docked, **never a floating chat pill**. It shares the calendar chrome (same topbar + milestone bar) so the agent lives *beside* the week, not over it. Plus a standalone **capability map** screen.

Reference component: `reference/agent.jsx` → `reference/preview.html` (section 03). The dock reuses `ProductTopbar`, `MilestoneBar`, `WK`, `DayColumn` from `calendar.jsx` — load calendar before agent.

## Screen layout
Left: a condensed **week summary** (`WeekSummary` — the same `DayColumn` grid, read-only here, "5 proposed · 5 accepted · 5 done"). Right: the **dock** (`AgentDock`), a fixed ~392px rail.

## The dock, top → bottom (order is intentional)
1. **Header** — ✦ agent mark, "Agent", subtitle **"bounded · proposes only · you approve"**, collapse affordance.
2. **Approvals** (`Pending · N proposals`) — the priority surface. Each approval row: title + when ("Wed 10:00 · 1h focus") + **✕ / ✓ Accept**. This is the same `Proposal` queue the calendar's "Accept proposed" acts on — one source of truth, two surfaces.
3. **Thread** (`grow` — takes remaining height) — the conversation. Bubble types:
   - `agent` — model messages (proactive: "Your personal essay draft is the only thing standing between you and Friday's milestone").
   - `me` — user messages.
   - **`tool`** — visible tool-call rows, e.g. `⌁ read_file(activities-list.pdf) · 1.8k tokens`. **Render these explicitly** — surfacing what the agent read (and the token cost) is part of the trust model, not debug output.
4. **Composer + trust strip** — input ("Ask, plan, or reschedule…") + send, a row of **slash commands** (`/recover`, `/why`, `/regen week`, `/explain`), and a **trust line**: "The agent never writes to your calendar without an explicit ✓. File reads are logged, and every accept has a 60-second undo." This line restates the three hard rules — keep it.

## Capability map screen (`CapabilityMap`)
A standalone explainer (nav: "Plan") that renders the governing idea verbatim: H1 **"The model proposes. Deterministic infrastructure disposes."** Two columns of capability cards:
- **AI · proposes** (clay, "must be approved"): parse files, generate syllabus, regenerate week, recovery plan, explain "why this", weekly reflection — each tagged "preview →".
- **Deterministic · acts** (white, "no model in the loop"): accept & schedule, mark done, drift detection, calendar sync, permission gate, cost & retry caps — each tagged "direct".

This screen is both onboarding-the-concept UI **and** the canonical list of backend capabilities and which side of the gate each lives on. Use it as the capability checklist (it maps 1:1 to `DATA-MODEL.md §1` and the README table).

## Behavior to implement
- The dock is **persistent app chrome**, not a modal/popover — it co-exists with the week view.
- Approvals in the dock and "Accept proposed" in the calendar act on the **same `Proposal` records**; accepting in one updates the other.
- Tool-call rows come from the agent's actual tool invocations (file reads, etc.) and show real token counts.
- Slash commands map to backend capabilities and **return `Proposal`s into the approval queue** — they never act directly: `/recover` → recovery plan, `/why` → explain, `/regen week` → week_regen, `/explain` → explain.
- Every accept honors the **60-second undo**; every file read is **logged**.
