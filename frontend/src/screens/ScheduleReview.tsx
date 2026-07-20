import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, api, errorMessage } from '../api/client'
import type {
  CalendarReconciliationResult,
  DraftView,
  StatusResult,
  TodayResult,
  UserProfile,
} from '../api/types'
import { BlockPopover } from '../components/BlockPopover'
import { WeekPlanView } from '../components/WeekPlanView'
import {
  DAY_MS,
  dayHeader,
  dayUtcMs,
  fmtAgo,
  fmtMinutes,
  isoAt,
  minutesOfDay,
  parseWall,
  todayDayMs,
  windowStartMs,
} from '../lib/datetime'
import {
  allowedWindowMin,
  initialScrollMin,
  nowMinutesOfDay,
  splitBusySegments,
} from '../lib/gridtime'
import { popoverPlacement } from '../lib/popover'
import {
  advisoryNote,
  flaggedReason,
  needsDraftRefetch,
  reconcileBanner,
  reconcileDismissKey,
  syncedAtMs,
} from '../lib/reconcile'
import { RECOVERY_OPTIONS, planDiffLine, reviewBanner, reviewMode } from '../lib/review'
import { stackByDay } from '../lib/stack'
import { buildWeekPlan, fmtDur, milestoneGroups, todayFacts, weekRangeLabel } from '../lib/weekplan'

// The drag-to-adjust schedule review (the signature interaction). PROPOSED
// blocks are draggable (snap 15 min, move across the week's days); imported
// Google-Calendar busy times are fixed and translucent. On drop we send the new
// start to POST /api/adjust and RE-RENDER FROM THE SERVER — it re-validates
// every move and never trusts the client (backend D-6). A rejected move keeps a
// typed reason_code and the block snaps back to the server's truth. There is no
// 60s undo; per-block control here is what makes the single plan-level approval
// (next screen) safe.
//
// The grid is a rolling 7-day window anchored on TODAY (leftmost column), not a
// Monday-to-Sunday calendar week; paging moves in whole 7-day steps. Blocks
// that overlap — including adopted external moves onto another event
// (ADR-0009) — stack side-by-side like Google Calendar, never as a collision.

// The axis spans the full day; the user's ALLOWED window (profile
// hard_constraints, fallback 8a–11p) drives the drag clamp and the off-hours
// shading instead. GRID_TOP/GRID_BOT keep their axis meaning for geometry.
const START_HOUR = 0
const END_HOUR = 24
const HOURS = END_HOUR - START_HOUR
const HOUR_PX = 46
const SNAP = 15
const GRID_TOP = START_HOUR * 60
const GRID_BOT = END_HOUR * 60

interface Block {
  taskId: string
  title: string
  dayMs: number
  startMin: number
  durMin: number
  offset: string
}

interface BusyBlock {
  dayMs: number
  startMin: number
  durMin: number
}

type DragState = { taskId: string; dayIdx: number; startMin: number }

// The Week screen renders the same server truth two ways: the hour grid
// (drag-to-adjust) and the design-reference week-plan board + day rail. The
// choice is cosmetic, so it lives client-side only.
type ReviewViewKind = 'grid' | 'plan'
const VIEW_PREF_KEY = 'loop.review.view'
// Last dismissed reconcile-banner key (lib/reconcile.ts reconcileDismissKey).
// Client-side only by design: the flagged edits themselves are already durable
// server truth (event_deleted dispositions → DraftView.deleted_task_ids, and
// the grid/rail mark each block), so dismissing the roll-up banner loses
// nothing — it just stops the same pull re-nagging on every Week mount.
const RECON_DISMISS_KEY = 'loop.review.reconcileDismissed'

function toBlocks(view: DraftView): Block[] {
  const titles = view.task_titles
  return (view.draft?.entries ?? []).map((entry) => {
    const start = parseWall(entry.start)
    return {
      taskId: entry.task_id,
      title: titles[entry.task_id] ?? entry.task_id,
      dayMs: dayUtcMs(start),
      startMin: minutesOfDay(start),
      durMin: Math.round((Date.parse(entry.end) - Date.parse(entry.start)) / 60000),
      offset: start.offset,
    }
  })
}

function toBusy(view: DraftView): BusyBlock[] {
  return view.free_busy.map((interval) => {
    const start = parseWall(interval.start)
    return {
      dayMs: dayUtcMs(start),
      startMin: minutesOfDay(start),
      durMin: Math.round((Date.parse(interval.end) - Date.parse(interval.start)) / 60000),
    }
  })
}

const topPx = (startMin: number) => ((startMin - GRID_TOP) / 60) * HOUR_PX
const heightPx = (durMin: number) => Math.max(18, (durMin / 60) * HOUR_PX - 3)
const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n))
// End-time label: a split busy segment may end exactly at midnight (1440),
// which fmtMinutes would render as "12p" — wrap it back to "12a".
const fmtEnd = (min: number) => fmtMinutes(min % 1440)

// "Tue Jul 21 · 10:30a–11:15a · 45m" for the popover's when line.
const whenLine = (windowMs: number, dayIdx: number, startMin: number, durMin: number): string => {
  const h = dayHeader(windowMs, dayIdx)
  return `${h.dow} ${h.label} · ${fmtMinutes(startMin)}–${fmtEnd(startMin + durMin)} · ${fmtDur(durMin)}`
}

// Display form of a task category — same semantics as the Plan rail's labels.
const prettyCategory = (raw: string): string => {
  const label = raw.replace(/_/g, ' ')
  return label.charAt(0).toUpperCase() + label.slice(1)
}

export function ScheduleReviewScreen() {
  const navigate = useNavigate()
  const [view, setView] = useState<DraftView | null>(null)
  const [status, setStatus] = useState<StatusResult | null>(null)
  const [today, setToday] = useState<TodayResult | null>(null)
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [viewKind, setViewKind] = useState<ReviewViewKind>(() => {
    try {
      return localStorage.getItem(VIEW_PREF_KEY) === 'plan' ? 'plan' : 'grid'
    } catch {
      return 'grid'
    }
  })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [weekIdx, setWeekIdx] = useState<number | null>(null)
  const [drag, setDrag] = useState<DragState | null>(null)
  // The open block-details popover, resolved to the LIVE block each render so
  // a reconcile refetch can never show stale data.
  const [detail, setDetail] = useState<{ kind: 'task' | 'busy'; key: string } | null>(null)
  const [saving, setSaving] = useState(false)
  const [violation, setViolation] = useState<{ taskId: string; text: string } | null>(null)
  const [replanning, setReplanning] = useState(false)
  const [replanError, setReplanError] = useState<string | null>(null)
  const [syncEnabled, setSyncEnabled] = useState(false)
  const [reconcileResult, setReconcileResult] = useState<CalendarReconciliationResult | null>(null)
  const [reconcileError, setReconcileError] = useState<string | null>(null)
  const [reconHidden, setReconHidden] = useState(false)
  const [dismissedReconKey, setDismissedReconKey] = useState<string | null>(() => {
    try {
      return localStorage.getItem(RECON_DISMISS_KEY)
    } catch {
      return null
    }
  })
  const reconciledRef = useRef(false)
  const mountedRef = useRef(true)
  const colsRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  // Initial-scroll latch (same once-per-mount pattern as reconciledRef): the
  // grid render below stores its target px; the effect fires the first time
  // the scroll container actually exists and never again — week paging and
  // Plan→Grid round-trips must not yank the user's scroll.
  const scrolledRef = useRef(false)
  const initialScrollPxRef = useRef(0)
  const geo = useRef<
    | {
        taskId: string
        dayW: number
        hourH: number
        x0: number
        y0: number
        origDay: number
        origStart: number
        dur: number
        offset: string
        day: number
        start: number
      }
    | null
  >(null)

  useEffect(() => {
    let active = true
    // Both come from server truth: the draft is what we render; the run state
    // decides whether it is still an editable draft (awaiting approval) or an
    // already-written schedule we must show read-only. `me` carries the
    // inbound-calendar-sync opt-in that gates the reconcile pull below.
    // `today` supplies the plan view's reported/due facts (it covers the whole
    // active draft, not just today); it is auxiliary, so a failure degrades the
    // plan view to accepted-only instead of breaking the screen.
    Promise.all([api.status(), api.draft(), api.me(), api.today().catch(() => null)])
      .then(([s, v, m, t]) => {
        if (!active) return
        setStatus(s)
        setView(v)
        setSyncEnabled(m.inbound_calendar_sync_enabled)
        setProfile(m.profile)
        setToday(t)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) return
        if (active) {
          setError(errorMessage(err))
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [])

  // Real mount state for the single-fire reconcile below. The read effects use a
  // per-run `active` flag, but that pattern would drop this effect's one result:
  // `reconciledRef` correctly limits reconcile to a single call across
  // StrictMode's dev remount, yet that remount's cleanup would flip a per-run
  // flag to false before the call resolves. A mount-scoped ref is true again
  // once the remount settles, so the outcome still shows; it only suppresses a
  // real unmount mid-flight.
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
    }
  }, [])

  // Inbound reconciliation (opt-in, off by default). Once status + me have
  // loaded and a plan is active — the exact precondition the endpoint enforces,
  // so no 409 — pull the user's own edits to Loop's events and adopt the valid
  // ones. It is read-only against the calendar and only adopts edits that still
  // fit the plan, so running it on mount is safe. An adopted/mixed outcome means
  // the draft changed, so refetch it; the outcome is surfaced as a banner. The
  // ref guard only dedupes StrictMode's in-place double-invoke — a genuine
  // remount (navigating back to the week later) is a fresh instance and re-pulls,
  // which is what we want.
  useEffect(() => {
    if (reconciledRef.current) return
    if (!syncEnabled || !status || status.active_plan_version == null) return
    reconciledRef.current = true
    api
      .reconcile()
      .then(async (res) => {
        if (!mountedRef.current) return
        setReconcileResult(res)
        // Adopted times AND freshly-recorded deletions both live server-side in
        // the DraftView (entries / deleted_task_ids), so refetch for either.
        if (needsDraftRefetch(res)) {
          const refreshed = await api.draft()
          if (mountedRef.current) setView(refreshed)
        }
      })
      .catch((err: unknown) => {
        // Surfacing-only: a transient reconcile fault must not break the
        // read-only week, and we never claim a success we don't have — show a
        // low-key note instead of a fake "all synced".
        if (mountedRef.current && !(err instanceof ApiError && err.status === 401)) {
          setReconcileError(errorMessage(err))
        }
      })
  }, [syncEnabled, status])

  // One mount-scoped 30s tick serves both the "synced X ago" banner age and
  // the grid's now line. Side benefit: a tick after midnight re-renders,
  // anchorMs is recomputed from Date.now() per render, and the window
  // re-anchors on the new day without a reload.
  const syncedAt = reconcileResult ? syncedAtMs(reconcileResult) : null
  const [nowMs, setNowMs] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setNowMs(Date.now()), 30_000)
    return () => clearInterval(id)
  }, [])

  // Fires once per screen mount, as soon as the grid is actually rendered
  // (grid view, non-empty draft) — see the scrolledRef note above.
  useEffect(() => {
    if (scrolledRef.current) return
    const el = scrollRef.current
    if (!el) return
    scrolledRef.current = true
    el.scrollTop = initialScrollPxRef.current
  })

  if (loading) return <div className="screen-center muted">Loading your draft…</div>
  if (error) return <div className="screen-center">Couldn’t load the draft — {error}</div>

  const blocks = view ? toBlocks(view) : []
  // Split BEFORE the per-window filter, so a midnight-crossing busy interval
  // lands each clipped segment in its own day column.
  const busy = view ? splitBusySegments(toBusy(view)) : []
  if (!view || blocks.length === 0) {
    return (
      <div className="screen-center col" style={{ gap: 12 }}>
        <h2 className="t-h2">No draft to review yet</h2>
        <button className="btn btn-primary" type="button" onClick={() => navigate('/plan')}>
          Build a plan →
        </button>
      </div>
    )
  }

  // Rolling 7-day windows anchored on TODAY (the user's wall-clock date, read
  // from the draft's own offset): the leftmost column of the current window is
  // always today. Past blocks fall into earlier windows, reachable with ←.
  const anchorMs = todayDayMs(Date.now(), blocks[0]?.offset ?? 'Z')
  const weeks = [...new Set(blocks.map((b) => windowStartMs(b.dayMs, anchorMs)))].sort(
    (a, b) => a - b,
  )
  // Default to the window containing today, else the next upcoming one, else
  // the most recent past one — not blindly the earliest.
  const upcoming = weeks.findIndex((w) => w >= anchorMs)
  const defaultWeek = upcoming === -1 ? weeks.length - 1 : upcoming
  const safeWeek = clamp(weekIdx ?? defaultWeek, 0, weeks.length - 1)
  const windowMs = weeks[safeWeek]
  const dayIdxOf = (dayMs: number) => (dayMs - windowMs) / DAY_MS
  const weekBlocks = blocks
    .filter((b) => windowStartMs(b.dayMs, anchorMs) === windowMs)
    .map((b) => ({ ...b, dayIdx: dayIdxOf(b.dayMs) }))
  const weekBusy = busy
    .filter((b) => windowStartMs(b.dayMs, anchorMs) === windowMs)
    .map((b) => ({ ...b, dayIdx: dayIdxOf(b.dayMs) }))

  // The user's allowed scheduling window (profile hard_constraints, fallback
  // 8a–11p): drives the drag clamp and the off-hours shading. The now line
  // renders only when today's column is on screen — by the rolling-window
  // construction, exactly when the current window IS the anchor window. "Now"
  // is the user's wall clock (the draft's own offset), never the browser tz.
  const allowed = allowedWindowMin(profile)
  const todayVisible = windowMs === anchorMs
  const nowMin = nowMinutesOfDay(nowMs, blocks[0].offset)
  initialScrollPxRef.current =
    (initialScrollMin(allowed.start, todayVisible ? nowMin : null) / 60) * HOUR_PX

  // Drag + approval are valid only while the run awaits approval; once it's been
  // written/active the same draft comes back from /draft, so we render it
  // read-only instead of the (now-consumed) approval UI. The server enforces
  // the same guard, so this is a UI mirror of its truth, not a new gate.
  const mode = reviewMode(status)
  const editable = mode === 'editable'
  const banner = reviewBanner(mode, status)
  const pendingChoice = mode === 'replan' && (status?.recovery_mode_pending_user_choice ?? false)
  const recon = reconcileResult ? reconcileBanner(reconcileResult) : null
  // Dismissal: hidden for this visit once ×'d, and — for warning banners, whose
  // flagged edits are re-detected by every pull — persistently, until the
  // flagged content changes (new deletion, different move, new plan version).
  const reconKey = reconcileResult ? reconcileDismissKey(reconcileResult) : null
  const reconDismissed = reconHidden || (reconKey != null && reconKey === dismissedReconKey)
  const dismissRecon = () => {
    setReconHidden(true)
    if (reconKey != null) {
      setDismissedReconKey(reconKey)
      try {
        localStorage.setItem(RECON_DISMISS_KEY, reconKey)
      } catch {
        // Storage unavailable → the dismissal still holds for this visit.
      }
    }
  }
  // The "Google Calendar synced" indicator (banner, both Grid and Plan views).
  // Rendered only when the mount reconcile actually runs (its exact
  // precondition: opted in + an active plan), and each state says only what is
  // true — the green "synced · X ago" appears solely after a pull genuinely
  // compared this plan against the calendar (server-stamped reconciled_at).
  const syncNote = (() => {
    if (!syncEnabled || !status || status.active_plan_version == null) return null
    const noteStyle: React.CSSProperties = {
      gap: 6,
      fontSize: 12.5,
      color: 'var(--muted)',
      whiteSpace: 'nowrap',
    }
    if (syncedAt != null) {
      return (
        <span
          className="row"
          style={noteStyle}
          title="Loop pulls the edits you made on your Google Calendar each time you open this page"
        >
          <span
            style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--sage)', flex: 'none' }}
          />
          Google Calendar synced · {fmtAgo(syncedAt, nowMs)}
        </span>
      )
    }
    if (reconcileResult) {
      // A pull that compared nothing must not claim "synced". `deferred` gets
      // an honest note; `sync_disabled` (toggle raced off elsewhere) gets none.
      return reconcileResult.outcome === 'deferred' ? (
        <span
          className="row"
          style={noteStyle}
          title="A calendar write was in progress, so this visit didn’t compare against your calendar — reopen the page to sync"
        >
          Google Calendar sync deferred
        </span>
      ) : null
    }
    if (reconcileError) {
      return (
        <span className="row" style={noteStyle}>
          Google Calendar sync failed
        </span>
      )
    }
    return (
      <span className="row" style={noteStyle}>
        <span className="spin" style={{ width: 11, height: 11 }} />
        Syncing Google Calendar…
      </span>
    )
  })()
  const titleOf = (taskId: string): string => view?.task_titles[taskId] ?? taskId
  // Durable event_deleted memory (server truth, not the transient banner): these
  // blocks must never carry the written "✓" — the event is gone from the
  // calendar, but the task is still planned.
  const deletedIds = new Set(view?.deleted_task_ids ?? [])
  const facts = todayFacts(today)

  // Resolve the open popover against the live week data. Existing client data
  // only: the status line mirrors the block's legend state, the busy card
  // honestly explains why there is no event name (axiom 06 — free/busy is
  // opaque ranges, titles never leave the user's calendar), and description is
  // ALWAYS null today (no task description field exists anywhere).
  const placementBase = { gridHeightPx: HOURS * HOUR_PX, cardHeightPx: 180, hourPx: HOUR_PX }
  const detailCard = (() => {
    if (!detail) return null
    if (detail.kind === 'busy') {
      const b = weekBusy[Number(detail.key.slice('busy'.length))]
      if (!b) return null
      return {
        title: 'Busy',
        when: whenLine(windowMs, b.dayIdx, b.startMin, b.durMin),
        status: 'busy · from your Google Calendar · fixed',
        detail: 'Loop only reads busy times — event details stay in your calendar.',
        placement: popoverPlacement({ dayIdx: b.dayIdx, startMin: b.startMin, ...placementBase }),
      }
    }
    const b = weekBlocks.find((blk) => blk.taskId === detail.key)
    if (!b) return null
    const fact = facts.details.get(b.taskId)
    return {
      title: b.title,
      when: whenLine(windowMs, b.dayIdx, b.startMin, b.durMin),
      status: editable
        ? 'proposed · drag to adjust'
        : deletedIds.has(b.taskId)
          ? 'deleted from your calendar · still planned'
          : mode === 'written'
            ? 'confirmed · on your Google Calendar'
            : 'planned · not confirmed on your calendar',
      detail: fact ? `${prettyCategory(fact.category)} · ${fact.focusLevel} focus` : null,
      placement: popoverPlacement({ dayIdx: b.dayIdx, startMin: b.startMin, ...placementBase }),
    }
  })()

  type WeekBlock = Block & { dayIdx: number }
  const posOf = (b: WeekBlock): { dayIdx: number; startMin: number } =>
    drag && drag.taskId === b.taskId ? { dayIdx: drag.dayIdx, startMin: drag.startMin } : b

  // GCal-style stacking: blocks that overlap in a day column — busy intervals,
  // proposed blocks, adopted external moves onto another event (ADR-0009) —
  // split the column side-by-side instead of drawing on top of each other.
  // Recomputed with the live drag position so a dragged block restacks as it
  // crosses other blocks.
  const slotOf = stackByDay([
    ...weekBusy.map((b, i) => ({
      key: `busy${i}`,
      dayIdx: b.dayIdx,
      startMin: b.startMin,
      endMin: b.startMin + b.durMin,
    })),
    ...weekBlocks.map((b) => {
      const pos = posOf(b)
      return {
        key: b.taskId,
        dayIdx: pos.dayIdx,
        startMin: pos.startMin,
        endMin: pos.startMin + b.durMin,
      }
    }),
  ])
  const stackGeom = (key: string, dayIdx: number): { left: string; width: string } => {
    const slot = slotOf.get(key) ?? { col: 0, cols: 1 }
    return {
      left: `${((dayIdx + slot.col / slot.cols) / 7) * 100}%`,
      width: `${100 / (7 * slot.cols)}%`,
    }
  }

  function onDown(event: React.PointerEvent, b: WeekBlock) {
    if (saving) return
    event.preventDefault()
    const rect = colsRef.current?.getBoundingClientRect()
    if (!rect) return
    event.currentTarget.setPointerCapture(event.pointerId)
    geo.current = {
      taskId: b.taskId,
      dayW: rect.width / 7,
      hourH: rect.height / HOURS,
      x0: event.clientX,
      y0: event.clientY,
      origDay: b.dayIdx,
      origStart: b.startMin,
      dur: b.durMin,
      offset: b.offset,
      day: b.dayIdx,
      start: b.startMin,
    }
    setViolation(null)
    setDetail(null)
    setDrag({ taskId: b.taskId, dayIdx: b.dayIdx, startMin: b.startMin })
  }

  function onMove(event: React.PointerEvent) {
    const g = geo.current
    if (!g) return
    const dDay = Math.round((event.clientX - g.x0) / g.dayW)
    const dMin = Math.round(((event.clientY - g.y0) / g.hourH) * 60) / SNAP
    const day = clamp(g.origDay + dDay, 0, 6)
    // Clamp to the PROFILE's allowed window, not the axis: valid early/late
    // slots stay reachable, and the server remains the only authority — every
    // drop is still re-validated (OUTSIDE_ALLOWED_HOURS on rejection).
    const start = clamp(g.origStart + Math.round(dMin) * SNAP, allowed.start, allowed.end - g.dur)
    g.day = day
    g.start = start
    setDrag({ taskId: g.taskId, dayIdx: day, startMin: start })
  }

  async function onUp(event: React.PointerEvent) {
    const g = geo.current
    geo.current = null
    try {
      event.currentTarget.releasePointerCapture(event.pointerId)
    } catch {
      /* capture may already be gone */
    }
    if (!g) return
    if (g.day === g.origDay && g.start === g.origStart) {
      // No effective move → this was a click: open the details popover.
      // Snap-level movement stays a drag; sub-snap jitter resolves here.
      setDrag(null)
      setDetail({ kind: 'task', key: g.taskId })
      return
    }
    setSaving(true)
    const iso = isoAt(windowMs, g.day, g.start, g.offset)
    try {
      const result = await api.adjust([{ task_id: g.taskId, start: iso }])
      if (!result.applied) {
        const first = result.violations[0]
        setViolation({
          taskId: g.taskId,
          text: first ? `${first.reason_code}: ${first.detail}` : (result.reason_code ?? 'Move rejected'),
        })
      }
      // Re-render from the server's truth either way: accepted -> new positions,
      // rejected -> snap back (the rejected move was never persisted).
      const refreshed = await api.draft()
      setView(refreshed)
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) {
        setViolation({ taskId: g.taskId, text: errorMessage(err) })
      }
    } finally {
      setSaving(false)
      setDrag(null)
    }
  }

  const pickView = (kind: ReviewViewKind) => {
    setDetail(null) // switching Grid/Plan closes any open popover
    setViewKind(kind)
    try {
      localStorage.setItem(VIEW_PREF_KEY, kind)
    } catch {
      /* private mode — the toggle still works, just doesn't persist */
    }
  }

  // Week paging closes any open popover (its block leaves the screen).
  const pageWeek = (idx: number) => {
    setDetail(null)
    setWeekIdx(idx)
  }

  async function runReplan(recoveryMode?: string) {
    setReplanning(true)
    setReplanError(null)
    try {
      // Continues the parked run: REPLAN_STARTED re-enters the planner →
      // validation → scheduler → approval pipeline. On success the run is
      // awaiting approval again, so re-fetching flips this screen editable
      // with the new draft — the user reviews and approves as always.
      const result = await api.propose(recoveryMode ? { recovery_mode: recoveryMode } : {})
      if (result.reason_code) {
        setReplanError(`the replan didn’t produce a schedulable draft (${result.reason_code})`)
      } else {
        // Refetch today-facts too: the run is editable again, so /today goes
        // empty and stale reported/due sets from the old plan can't leak.
        const [s, v, t] = await Promise.all([
          api.status(),
          api.draft(),
          api.today().catch(() => null),
        ])
        setStatus(s)
        setView(v)
        setToday(t)
      }
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) {
        setReplanError(errorMessage(err))
      }
    } finally {
      setReplanning(false)
    }
  }

  return (
    <div className="sched">
      <div className="sched-banner">
        <span className="agent-mark">✦</span>
        {editable ? (
          <div style={{ flex: 1 }}>
            <div className="t-h3">Review your proposed week</div>
            <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
              {viewKind === 'grid' ? (
                <>
                  Drag any <b style={{ color: 'var(--clay-deep)' }}>proposed</b> block to a new time
                  or day. Your existing calendar events are fixed. Every move is re-checked on the
                  server.
                </>
              ) : (
                <>Click a day to see its detail. Switch to Grid to drag blocks to new times.</>
              )}
            </div>
            {view?.plan_diff &&
              // The deterministic plan diff (D4): a replanned draft is
              // reviewed as a delta against the plan the user already
              // approved, not re-read from scratch. Server-computed counts;
              // the disclosure lists the per-task change lines.
              (view.plan_diff.changes.length > 0 ? (
                <details style={{ marginTop: 6 }}>
                  <summary className="muted" style={{ fontSize: 12.5, cursor: 'pointer' }}>
                    {planDiffLine(view.plan_diff)}
                  </summary>
                  <ul className="fit-specifics" style={{ marginTop: 4 }}>
                    {view.plan_diff.changes.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </details>
              ) : (
                <div className="muted" style={{ fontSize: 12.5, marginTop: 6 }}>
                  {planDiffLine(view.plan_diff)}
                </div>
              ))}
          </div>
        ) : (
          <div style={{ flex: 1 }}>
            <div className="t-h3">{banner.title}</div>
            <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
              {banner.sub}
            </div>
            {mode === 'replan' && status?.reflection && (
              // The persisted reflection prose (advisory, never control-plane):
              // one line + a quiet disclosure, per the "friendly but not noisy"
              // banner recommendation.
              <details style={{ marginTop: 6 }}>
                <summary className="muted" style={{ fontSize: 12.5, cursor: 'pointer' }}>
                  Why? {status.reflection.summary}
                </summary>
                {status.reflection.detail.length > 0 && (
                  <ul className="fit-specifics" style={{ marginTop: 4 }}>
                    {status.reflection.detail.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                )}
              </details>
            )}
          </div>
        )}
        {syncNote}
        <div className="row" style={{ gap: 6 }}>
          <button
            className={viewKind === 'grid' ? 'chip on' : 'chip'}
            type="button"
            onClick={() => pickView('grid')}
          >
            Grid
          </button>
          <button
            className={viewKind === 'plan' ? 'chip on' : 'chip'}
            type="button"
            onClick={() => pickView('plan')}
          >
            Plan
          </button>
        </div>
        {viewKind === 'grid' && weeks.length > 1 && (
          <div className="row" style={{ gap: 6 }}>
            <button
              className="btn btn-soft sm"
              type="button"
              disabled={safeWeek === 0}
              onClick={() => pageWeek(safeWeek - 1)}
            >
              ←
            </button>
            <span className="mono" style={{ fontSize: 12 }}>
              week {safeWeek + 1} / {weeks.length}
            </span>
            <button
              className="btn btn-soft sm"
              type="button"
              disabled={safeWeek === weeks.length - 1}
              onClick={() => pageWeek(safeWeek + 1)}
            >
              →
            </button>
          </div>
        )}
        {editable ? (
          <button className="btn btn-primary lg" type="button" onClick={() => navigate('/approve')}>
            Continue to approval →
          </button>
        ) : mode === 'failed' ? (
          <button className="btn btn-primary lg" type="button" onClick={() => navigate('/approve')}>
            Recover this write →
          </button>
        ) : mode === 'replan' ? (
          pendingChoice ? null : (
            <button
              className="btn btn-primary lg"
              type="button"
              disabled={replanning}
              onClick={() => void runReplan()}
            >
              {replanning ? 'Updating your plan…' : 'Build the updated plan →'}
            </button>
          )
        ) : mode === 'closed' ? (
          <button className="btn btn-primary lg" type="button" onClick={() => navigate('/plan')}>
            Build a new plan →
          </button>
        ) : (
          <button className="btn btn-primary lg" type="button" onClick={() => navigate('/today')}>
            Go to Today →
          </button>
        )}
      </div>

      {pendingChoice && (
        <div className="card" style={{ margin: '12px clamp(16px,4vw,26px) 0', padding: '14px 16px' }}>
          <div className="label" style={{ marginBottom: 4 }}>
            How should Loop adjust?
          </div>
          <p className="muted" style={{ fontSize: 13, marginBottom: 10 }}>
            You asked to be asked each time. Pick one — the updated plan still comes back as a
            draft for your review and approval.
          </p>
          <div className="row" style={{ gap: 10, flexWrap: 'wrap', alignItems: 'stretch' }}>
            {RECOVERY_OPTIONS.map((opt) => (
              <button
                key={opt.mode}
                type="button"
                className="card"
                disabled={replanning}
                style={{ flex: '1 1 180px', padding: '12px 14px', textAlign: 'left', cursor: 'pointer' }}
                onClick={() => void runReplan(opt.mode)}
              >
                <div style={{ fontWeight: 600, fontSize: 14 }}>{opt.title}</div>
                <div className="muted" style={{ fontSize: 12.5, marginTop: 4, lineHeight: 1.45 }}>
                  {opt.description}
                </div>
              </button>
            ))}
          </div>
          {replanning && (
            <div className="muted" style={{ fontSize: 13, marginTop: 10 }}>
              <span className="spin" style={{ width: 11, height: 11, marginRight: 6 }} />
              Updating your plan…
            </div>
          )}
        </div>
      )}

      {replanError && (
        <div className="banner-error" style={{ margin: '12px clamp(16px,4vw,26px) 0' }}>
          Couldn’t update the plan — {replanError}
        </div>
      )}

      {violation && (
        <div className="banner-error" style={{ margin: '12px clamp(16px,4vw,26px) 0' }}>
          That move was rejected by the server — {violation.text}
        </div>
      )}

      {recon && !reconDismissed && (
        <div
          className={`recon-banner ${recon.tone === 'adopted' ? 'recon-ok' : 'recon-warn'}`}
          style={{ margin: '12px clamp(16px,4vw,26px) 0' }}
          role="status"
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
            <div style={{ fontWeight: 600, fontSize: 14, flex: 1 }}>{recon.title}</div>
            <button
              className="recon-dismiss"
              type="button"
              aria-label="Dismiss calendar sync notice"
              onClick={dismissRecon}
            >
              ×
            </button>
          </div>
          <div style={{ fontSize: 13, marginTop: 2, opacity: 0.85 }}>{recon.sub}</div>
          {recon.adopted.some((d) => advisoryNote(d) != null) && (
            // Non-blocking heads-ups on ADOPTED edits (ADR-0008/0009): the move
            // was applied — e.g. it now overlaps another event and stacks on
            // the grid — so this is information, never an error.
            <ul className="recon-list">
              {recon.adopted.map((d) => {
                const note = advisoryNote(d)
                return note == null ? null : (
                  <li key={d.task_id}>
                    <b>{titleOf(d.task_id)}</b> — {note}
                  </li>
                )
              })}
            </ul>
          )}
          {recon.flagged.length > 0 && (
            <ul className="recon-list">
              {recon.flagged.map((d) => (
                <li key={d.task_id}>
                  <b>{titleOf(d.task_id)}</b> — {flaggedReason(d)}
                </li>
              ))}
            </ul>
          )}
          {recon.tone !== 'adopted' && (
            <button
              className="btn btn-soft sm"
              type="button"
              style={{ marginTop: 10 }}
              onClick={() => navigate('/plan')}
            >
              Build a new plan →
            </button>
          )}
        </div>
      )}

      {reconcileError && (
        <div className="muted" style={{ margin: '8px clamp(16px,4vw,26px) 0', fontSize: 12.5 }}>
          Couldn’t check for calendar edits — {reconcileError}
        </div>
      )}

      {viewKind === 'plan' ? (
        <WeekPlanView
          key={windowMs}
          days={buildWeekPlan(view, mode, facts, windowMs, anchorMs)}
          mode={mode}
          profile={profile}
          milestones={milestoneGroups(today)}
          range={{
            label: weekRangeLabel(windowMs),
            canPrev: safeWeek > 0,
            canNext: safeWeek < weeks.length - 1,
            atToday: safeWeek === defaultWeek,
          }}
          onPrev={() => pageWeek(safeWeek - 1)}
          onNext={() => pageWeek(safeWeek + 1)}
          onToday={() => pageWeek(defaultWeek)}
          onSwitchToGrid={() => pickView('grid')}
        />
      ) : (
        <>
          <div ref={scrollRef} className="sched-scroll">
            <div className="sched-head">
              <div className="gutter" />
              {Array.from({ length: 7 }).map((_, i) => {
                const h = dayHeader(windowMs, i)
                const isToday = windowMs + i * DAY_MS === anchorMs
                return (
                  <div key={i} className={isToday ? 'dcol dcol-today' : 'dcol'}>
                    <div className="label" style={{ fontSize: 11 }}>
                      {isToday ? 'Today' : h.dow}
                    </div>
                    <div style={{ fontFamily: 'var(--serif)', fontSize: 17 }}>{h.label}</div>
                  </div>
                )
              })}
            </div>

            <div className="sched-body">
              <div className="sched-gutter">
                {Array.from({ length: HOURS }).map((_, i) => (
                  <div key={i} className="hr">
                    <span>{fmtMinutes((START_HOUR + i) * 60)}</span>
                  </div>
                ))}
              </div>

              <div ref={colsRef} className="sched-cols" style={{ height: HOURS * HOUR_PX }}>
                {/* Off-hours tint bands (outside the allowed window). First in
                    DOM order and z-free so every block renders above them. */}
                {allowed.start > GRID_TOP && (
                  <div
                    className="sched-offhours"
                    style={{ top: 0, height: topPx(allowed.start) }}
                  />
                )}
                {allowed.end < GRID_BOT && (
                  <div
                    className="sched-offhours"
                    style={{
                      top: topPx(allowed.end),
                      height: ((GRID_BOT - allowed.end) / 60) * HOUR_PX,
                    }}
                  />
                )}
                {Array.from({ length: HOURS + 1 }).map((_, i) => (
                  <div key={`h${i}`} className="sched-hline" style={{ top: i * HOUR_PX }} />
                ))}
                {Array.from({ length: 6 }).map((_, i) => (
                  <div key={`v${i}`} className="sched-vline" style={{ left: `${((i + 1) / 7) * 100}%` }} />
                ))}

                {weekBusy.map((b, i) => (
                  <div
                    key={`busy${i}`}
                    className="blk blk-busy"
                    title="From Google Calendar · fixed"
                    onClick={() => setDetail({ kind: 'busy', key: `busy${i}` })}
                    style={{
                      ...stackGeom(`busy${i}`, b.dayIdx),
                      top: topPx(b.startMin),
                      height: heightPx(b.durMin),
                    }}
                  >
                    <div className="bt">🔒 Busy</div>
                    <div className="bm">
                      {fmtMinutes(b.startMin)}–{fmtEnd(b.startMin + b.durMin)}
                    </div>
                  </div>
                ))}

                {weekBlocks.map((b) => {
                  const pos = posOf(b)
                  const dragging = drag?.taskId === b.taskId
                  const bad = violation?.taskId === b.taskId
                  const gone = !editable && deletedIds.has(b.taskId)
                  return (
                    <div
                      key={b.taskId}
                      className={
                        editable
                          ? `blk blk-proposed${dragging ? ' dragging' : ''}${bad ? ' bad' : ''}`
                          : `blk ${gone ? 'blk-deleted' : mode === 'written' ? 'blk-confirmed' : 'blk-readonly'}`
                      }
                      title={
                        gone
                          ? 'You deleted this event from your Google Calendar — the task is still in your plan'
                          : mode === 'written'
                            ? 'On your Google Calendar · fixed'
                            : undefined
                      }
                      onPointerDown={editable ? (e) => onDown(e, b) : undefined}
                      onPointerMove={editable ? onMove : undefined}
                      onPointerUp={editable ? (e) => void onUp(e) : undefined}
                      onClick={
                        editable ? undefined : () => setDetail({ kind: 'task', key: b.taskId })
                      }
                      style={{
                        ...stackGeom(b.taskId, pos.dayIdx),
                        top: topPx(pos.startMin),
                        height: heightPx(b.durMin),
                      }}
                    >
                      <div className="bt">
                        {editable ? '⠿ ' : gone ? '✕ ' : mode === 'written' ? '✓ ' : ''}
                        {b.title}
                      </div>
                      <div className="bm">
                        {fmtMinutes(pos.startMin)}–{fmtEnd(pos.startMin + b.durMin)}
                      </div>
                    </div>
                  )
                })}

                {/* Now line: today's column only (column 0 of the anchor
                    window), ticking with the shared 30s interval. */}
                {todayVisible && (
                  <div className="sched-now" style={{ top: topPx(nowMin) }}>
                    <span className="sched-now-dot" />
                  </div>
                )}

                {detailCard && (
                  <BlockPopover
                    title={detailCard.title}
                    when={detailCard.when}
                    status={detailCard.status}
                    detail={detailCard.detail}
                    description={null}
                    placement={detailCard.placement}
                    onClose={() => setDetail(null)}
                  />
                )}
              </div>
            </div>
          </div>

          <div className="sched-legend">
            {editable ? (
              <span>
                <span className="sw" style={{ border: '1.5px dashed var(--clay)', background: 'var(--clay-tint)' }} />
                proposed · drag to adjust
              </span>
            ) : (
              <span>
                <span
                  className="sw"
                  style={
                    mode === 'written'
                      ? { border: '1px solid var(--sage)', background: 'var(--sage-soft)' }
                      : { border: '1px solid rgba(108,120,134,0.4)', background: 'rgba(108,120,134,0.12)' }
                  }
                />
                {mode === 'written'
                  ? 'confirmed · on your Google Calendar'
                  : mode === 'writing'
                    ? 'writing…'
                    : 'not confirmed'}
              </span>
            )}
            <span>
              <span
                className="sw"
                style={{
                  border: '1px solid rgba(108,120,134,0.4)',
                  background:
                    'repeating-linear-gradient(135deg, rgba(108,120,134,0.2) 0 4px, rgba(108,120,134,0.07) 4px 8px)',
                }}
              />
              imported · fixed
            </span>
            {!editable && weekBlocks.some((b) => deletedIds.has(b.taskId)) && (
              <span>
                <span
                  className="sw"
                  style={{ border: '1px dashed #c0492f', background: 'rgba(192,73,47,0.08)' }}
                />
                ✕ deleted from your calendar · still planned
              </span>
            )}
            <span className="spacer" />
            <span>{editable ? (saving ? 'saving…' : 'snaps to 15 min · drag across days') : 'read-only'}</span>
          </div>
        </>
      )}
    </div>
  )
}
