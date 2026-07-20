# G-C — Block Details Popover

Goal: clicking any block opens a small anchored card with the full title and
details; block titles are currently ellipsized (`.blk .bt`,
`tokens.css:753-758`) with no way to read the full name. Existing client
data only — no API or backend change.

## 1. Click vs drag

- **Editable (proposed) blocks**: the drag pipeline already distinguishes a
  click — `onUp`'s no-move branch (`g.day === g.origDay && g.start ===
  g.origStart`, `ScheduleReview.tsx:462-465`). Open the popover there
  instead of only clearing drag. Snap-level movement (15min or one day)
  remains a drag; sub-snap jitter resolves to a click. Drag semantics,
  server re-validation, and snap-back are untouched.
- **Read-only task blocks** (written/replan/closed modes) and **busy
  blocks**: plain `onClick`. Add `cursor: pointer` to `.blk-confirmed`,
  `.blk-readonly`, `.blk-deleted`, `.blk-busy` (busy currently shows
  `not-allowed` — it stays visually "fixed" via the popover copy instead).
- Opening a popover for one block closes any other. Dismiss on: backdrop
  click, Escape, starting a drag, paging weeks, or switching Grid/Plan.
- Keep the existing `title=` attribute tooltips; they're harmless
  alongside the popover.

## 2. State and placement

- Screen state: `const [detail, setDetail] = useState<{ kind: 'task' | 'busy'; key: string } | null>(null)`
  (`key` = `taskId` or `busy${i}`), resolved to the live block each render
  so a reconcile refetch can't show stale data.
- New pure helper `frontend/src/lib/popover.ts` (+ `popover.test.ts`):

```ts
/** Placement for a card anchored to a block in the 7-column grid.
 *  side: open toward the right unless the block sits in the last two
 *  columns; top: the block's top, clamped so an estimated card height
 *  stays inside the grid body. Returns CSS-ready values. */
export function popoverPlacement(input: {
  dayIdx: number      // 0..6
  startMin: number    // block top, minutes-of-day
  gridHeightPx: number
  cardHeightPx: number // estimate, e.g. 180
  hourPx: number
}): { leftPct: number; topPx: number; side: 'right' | 'left' }
```

  `side = dayIdx >= 5 ? 'left' : 'right'`; `leftPct` is the adjacent column
  edge (`((dayIdx + 1) / 7) * 100` for right, `(dayIdx / 7) * 100` for
  left — the card itself applies a small gap and, for `left`, a
  `translateX(-100%)`). `topPx = clamp((startMin / 60) * hourPx, 8,
  gridHeightPx - cardHeightPx - 8)`.

## 3. Component: `frontend/src/components/BlockPopover.tsx`

Presentational only (same posture as `WeekPlanView`): props in, callbacks
out, no data fetching.

```ts
interface BlockPopoverProps {
  title: string            // full, wrapped — never ellipsized
  when: string             // "Tue Jul 21 · 10:30a–11:15a · 45m"
  status: string           // honest state line, see below
  detail?: string | null   // "Coding drills · deep focus" when known
  description?: string | null // ALWAYS null today — future slot
  placement: { leftPct: number; topPx: number; side: 'right' | 'left' }
  onClose: () => void
}
```

- `when` composes existing helpers: `dayHeader` + `fmtMinutes`
  (`lib/datetime.ts`) and `fmtDur` — **export** the module-local `fmtDur`
  from `lib/weekplan.ts:199-203` (one-line change; that file is outside the
  concurrent split's blast radius).
- `status` mirrors the block's legend state exactly (no new claims):
  - proposed → `proposed · drag to adjust`
  - written → `confirmed · on your Google Calendar`
  - deleted → `deleted from your calendar · still planned`
  - other read-only → `planned · not confirmed on your calendar`
  - busy → `busy · from your Google Calendar · fixed`
- `detail` comes from `todayFacts(today).details` (`lib/weekplan.ts:63-76`),
  already fetched by the screen; it's empty in editable mode — the line is
  simply absent then. Reuse `prettyLabel` semantics via the facts values as
  the Plan rail does.
- **Busy blocks**: title `Busy`, plus one honest sentence in place of
  `detail`: *"Loop only reads busy times — event details stay in your
  calendar."* (axiom 06: raw titles/descriptions are never stored or
  relayed; this is a product guarantee, not a limitation to apologize for).
- **Description slot**: rendered only when `description` is a non-empty
  string. The screen always passes `null` today — tasks have no description
  field anywhere in `DraftView`. Adding one is explicitly out of scope; the
  slot exists so a future plan only touches data plumbing.
- Rendering: a transparent full-screen backdrop (closes on click) plus the
  card absolutely positioned inside `.sched-cols`; `role="dialog"`,
  `aria-label` = title, Escape closes (document-level listener while open).
  z-index 60 (above a dragging block's 50).

## 4. CSS (`tokens.css`, append in the grid section)

`.blk-pop` card: paper background, `--line` border, radius ~10px, soft
shadow, width ~240px, `z-index: 60`; title wraps (`white-space: normal`);
`.blk-pop-backdrop` fixed inset 0, transparent. Cursor additions from §1.

## 5. Tests

- `popover.test.ts`: side flip at columns 5–6; top clamped at both ends;
  left percentages for both sides.
- `weekplan.test.ts`: nothing new required (`fmtDur` gains `export` only);
  if the suite lacks direct `fmtDur` cases, add two (whole hours, h+m).
- Click-vs-drag and dialog behavior are covered by the G-D browser smoke
  (unit-testing pointer-capture flows headlessly is not worth the harness).

## Acceptance

- Clicking a proposed block (no movement) opens the card with the full
  title; dragging it never opens the card.
- Clicking a written block shows `confirmed · on your Google Calendar`; a
  deleted-event block shows the deleted line; a busy block shows the
  busy-privacy copy and no invented title.
- Escape, backdrop click, week paging, and view switching all close it.
- Cards near the right edge open leftward and never overflow the grid.
