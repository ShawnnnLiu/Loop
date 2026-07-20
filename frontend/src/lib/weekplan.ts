// Pure projection for the Week Plan board+rail view (the design-reference
// "week plan": a 7-column stacked-block board with a selected-day agenda
// rail). Projects the same server truth the hour grid renders — DraftView +
// reviewMode — plus /api/today's whole-plan reported/due facts, into display
// rows. React-free and unit-tested, same split as lib/stack.ts.
//
// Honesty invariants (mirroring the grid's block classes):
// - a deleted-event task must NEVER read as done — the event is gone from the
//   calendar but the task is still planned (deleted beats reported);
// - nothing may read as on-calendar unless the write verified (writing /
//   failed / closed all collapse to 'unconfirmed');
// - "done" means the user reported a check-in (complete OR missed — the same
//   collapse Today's "✓ reported" tag makes), so the rail says "logged", not
//   "completed".

import type { DraftView, TodayResult, UserProfile } from '../api/types'
import { DAY_MS, dayHeader, dayUtcMs, minutesOfDay, parseWall } from './datetime'
import type { ReviewMode } from './review'

/** Design block states plus two honest extras the design mock lacks:
 *  'deleted' (event removed externally, task still planned) and 'unconfirmed'
 *  (no verified write — must never render as on-calendar). */
export type PlanState = 'proposed' | 'accepted' | 'done' | 'locked' | 'deleted' | 'unconfirmed'

export interface PlanItem {
  key: string // task_id, or `busy${i}` for an imported free/busy interval
  taskId: string | null // null => imported busy (we never store external titles)
  title: string
  dayMs: number // UTC-midnight key of the wall-clock date (grid convention)
  startMin: number
  endMin: number
  state: PlanState
  /** Draft-entry end elapsed and no check-in yet (from /api/today). */
  pastDue: boolean
  /** Task category / focus level (from /api/today; null when unavailable —
   *  e.g. editable mode, or an imported busy interval). */
  category: string | null
  focusLevel: string | null
}

export interface PlanDay {
  dayIdx: number // 0..6 within the rolling today-first window
  dayMs: number
  dow: string // 'Mon'
  label: string // 'Jul 8' — for the rail header
  num: number // day of month, the board's serif date
  isToday: boolean
  meta: string // per-day summary line, see dayMeta()
  items: PlanItem[] // sorted by start; the board has no time axis
}

/** Join surface from /api/today. The endpoint covers the ACTIVE plan's whole
 *  draft (not just today), and returns no tasks in editable/writing/failed/
 *  closed modes — exactly the modes where reported/due are meaningless. */
export interface TodayFacts {
  reported: ReadonlySet<string>
  due: ReadonlySet<string>
  /** Per-task category / focus level, for richer rail meta and the
   *  milestone track. */
  details: ReadonlyMap<string, { category: string; focusLevel: string }>
}

export function todayFacts(today: TodayResult | null): TodayFacts {
  const reported = new Set<string>()
  const due = new Set<string>()
  const details = new Map<string, { category: string; focusLevel: string }>()
  for (const task of today?.tasks ?? []) {
    if (task.reported) reported.add(task.task_id)
    if (task.due) due.add(task.task_id)
    details.set(task.task_id, {
      category: task.category,
      focusLevel: task.required_focus_level,
    })
  }
  return { reported, due, details }
}

/** The state cell for one draft entry: mode × deleted × reported. Editable
 *  drafts are all-proposed (nothing is written yet, so deleted/reported facts
 *  from a previous plan version don't apply — same as the grid's
 *  `!editable && deletedIds.has(...)` guard). */
export function taskState(mode: ReviewMode, deleted: boolean, reported: boolean): PlanState {
  if (mode === 'editable') return 'proposed'
  if (mode === 'writing' || mode === 'failed' || mode === 'closed') return 'unconfirmed'
  // written / replan: the draft is the active plan's schedule.
  if (deleted) return 'deleted'
  if (reported) return 'done'
  return 'accepted'
}

const byStart = (a: PlanItem, b: PlanItem): number =>
  a.startMin - b.startMin || a.endMin - b.endMin || (a.key < b.key ? -1 : a.key > b.key ? 1 : 0)

/** Always returns exactly 7 PlanDays for [windowMs, windowMs + 7d) — the same
 *  rolling today-first window the grid pages through. Entries outside the
 *  window simply don't appear; busy intervals become locked items. */
export function buildWeekPlan(
  view: DraftView,
  mode: ReviewMode,
  facts: TodayFacts,
  windowMs: number,
  anchorMs: number,
): PlanDay[] {
  const deleted = new Set(view.deleted_task_ids)
  const items: PlanItem[] = (view.draft?.entries ?? []).map((entry) => {
    const start = parseWall(entry.start)
    const startMin = minutesOfDay(start)
    const reported = facts.reported.has(entry.task_id)
    const detail = facts.details.get(entry.task_id)
    return {
      key: entry.task_id,
      taskId: entry.task_id,
      title: view.task_titles[entry.task_id] ?? entry.task_id,
      dayMs: dayUtcMs(start),
      startMin,
      endMin: startMin + Math.round((Date.parse(entry.end) - Date.parse(entry.start)) / 60000),
      state: taskState(mode, deleted.has(entry.task_id), reported),
      pastDue: facts.due.has(entry.task_id) && !reported,
      category: detail?.category ?? null,
      focusLevel: detail?.focusLevel ?? null,
    }
  })
  view.free_busy.forEach((interval, i) => {
    const start = parseWall(interval.start)
    const startMin = minutesOfDay(start)
    items.push({
      key: `busy${i}`,
      taskId: null,
      title: 'Busy',
      dayMs: dayUtcMs(start),
      startMin,
      endMin:
        startMin + Math.round((Date.parse(interval.end) - Date.parse(interval.start)) / 60000),
      state: 'locked',
      pastDue: false,
      category: null,
      focusLevel: null,
    })
  })
  return Array.from({ length: 7 }, (_, dayIdx) => {
    const dayMs = windowMs + dayIdx * DAY_MS
    const dayItems = items.filter((item) => item.dayMs === dayMs).sort(byStart)
    const head = dayHeader(windowMs, dayIdx)
    return {
      dayIdx,
      dayMs,
      dow: head.dow,
      label: head.label,
      num: new Date(dayMs).getUTCDate(),
      isToday: dayMs === anchorMs,
      meta: dayMeta(mode, dayItems),
      items: dayItems,
    }
  })
}

/** The board's per-day summary line. Only written/replan may claim done/to-go
 *  progress; an unwritten draft counts "proposed"/"planned" instead. A day
 *  with no tasks is 'rest' only when it has no imported events either. */
export function dayMeta(mode: ReviewMode, items: PlanItem[]): string {
  const tasks = items.filter((item) => item.taskId !== null)
  if (tasks.length === 0) return items.length > 0 ? 'busy day' : 'rest'
  if (mode === 'editable') return `${tasks.length} proposed`
  if (mode === 'writing' || mode === 'failed' || mode === 'closed') return `${tasks.length} planned`
  const done = tasks.filter((item) => item.state === 'done').length
  if (done === tasks.length) return 'all done'
  if (done > 0) return `${done} done · ${tasks.length - done} to go`
  return `${tasks.length} to go`
}

/** Typed CTA descriptor for a rail item, so navigation decisions stay
 *  testable. There are NO per-item mutations here by design: approval is
 *  whole-draft (/approve), per-block editing is the grid's drag, and check-in
 *  lives on Today — the rail only points at those surfaces. */
export type RailAction =
  | { kind: 'chip'; label: string }
  | { kind: 'link'; label: string; to: string }
  | { kind: 'grid'; label: string } // switch to the drag grid

export function railAction(item: PlanItem): RailAction {
  switch (item.state) {
    case 'proposed':
      return { kind: 'grid', label: 'Adjust →' }
    case 'accepted':
      return item.pastDue
        ? { kind: 'link', label: 'Check in →', to: '/today' }
        : { kind: 'chip', label: 'on calendar' }
    case 'done':
      return { kind: 'chip', label: 'logged ✓' }
    case 'locked':
      return { kind: 'chip', label: 'gcal' }
    case 'deleted':
      return { kind: 'link', label: 'Check in →', to: '/today' }
    case 'unconfirmed':
      return { kind: 'chip', label: 'not confirmed' }
  }
}

export const fmtDur = (minutes: number): string => {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  if (h === 0) return `${m}m`
  return m === 0 ? `${h}h` : `${h}h ${m}m`
}

/** Display form of a task category: underscores to spaces, first letter
 *  capitalized — no invented naming. */
const prettyLabel = (raw: string): string => {
  const label = raw.replace(/_/g, ' ')
  return label.charAt(0).toUpperCase() + label.slice(1)
}

/** Deterministic per-item meta line. No fabricated data: there is no
 *  actual-minutes telemetry surfaced here, and imported events keep only
 *  their times (we never store external titles/descriptions). Category and
 *  focus level come from /api/today when available. */
export function railMeta(item: PlanItem): string {
  const dur = fmtDur(item.endMin - item.startMin)
  const detail =
    (item.category ? ` · ${prettyLabel(item.category)}` : '') +
    (item.focusLevel ? ` · ${item.focusLevel} focus` : '')
  switch (item.state) {
    case 'proposed':
      return `proposed · ${dur}${detail}`
    case 'accepted':
      return `on your Google Calendar · ${dur}${detail}${
        item.pastDue ? ' · past due — check in' : ''
      }`
    case 'done':
      return `logged · ${dur} planned${detail}`
    case 'locked':
      return 'from Google Calendar · fixed'
    case 'deleted':
      return 'deleted from your calendar · still planned'
    case 'unconfirmed':
      return `planned · ${dur} · not confirmed on your calendar`
  }
}

/** "Jul 6 — 12" (or "Apr 27 — May 3" across a month boundary) for the
 *  board's week-nav heading. */
export function weekRangeLabel(windowMs: number): string {
  const start = dayHeader(windowMs, 0)
  const end = dayHeader(windowMs, 6)
  const sameMonth = start.label.split(' ')[0] === end.label.split(' ')[0]
  return sameMonth ? `${start.label} — ${end.label.split(' ')[1]}` : `${start.label} — ${end.label}`
}

/** One milestone-track chip per task category of the ACTIVE plan, in the
 *  plan's own task order, with deterministic progress from check-ins. Empty
 *  when /api/today has no tasks (editable/writing/failed/closed) — the track
 *  simply doesn't render then; progress on an unwritten draft would be a lie. */
export interface MilestoneGroup {
  label: string
  done: number
  total: number
  state: 'done' | 'active' | 'todo'
}

export function milestoneGroups(today: TodayResult | null): MilestoneGroup[] {
  const order: string[] = []
  const byCategory = new Map<string, { done: number; total: number }>()
  for (const task of today?.tasks ?? []) {
    let group = byCategory.get(task.category)
    if (!group) {
      group = { done: 0, total: 0 }
      byCategory.set(task.category, group)
      order.push(task.category)
    }
    group.total += 1
    if (task.reported) group.done += 1
  }
  return order.map((category) => {
    const { done, total } = byCategory.get(category) as { done: number; total: number }
    return {
      label: prettyLabel(category),
      done,
      total,
      state: done === total ? 'done' : done > 0 ? 'active' : 'todo',
    }
  })
}

/** The design's "Nov 1, 2026 · EA · ~21 wks" target pill, from the real
 *  profile: role and committed timeline (there is no stored target date). */
export function targetLine(profile: UserProfile | null): string | null {
  if (!profile) return null
  return `${profile.target_role} · ~${profile.timeline_weeks} wks`
}

/** The rail header's deterministic status badge (the design's "on track").
 *  Derived from the run mode only: a written plan with no parked drift IS on
 *  track — drift would have parked the run in replan_required. */
export function railStatus(mode: ReviewMode): { label: string; tone: 'sage' | 'clay' | 'muted' } {
  switch (mode) {
    case 'written':
      return { label: 'on track', tone: 'sage' }
    case 'replan':
      return { label: 'needs update', tone: 'clay' }
    case 'editable':
      return { label: 'awaiting approval', tone: 'clay' }
    case 'failed':
      return { label: 'write not verified', tone: 'clay' }
    case 'writing':
      return { label: 'writing…', tone: 'muted' }
    case 'closed':
      return { label: 'closed', tone: 'muted' }
  }
}

/** The rail header's counts line for the selected day. */
export function railCounts(day: PlanDay, mode: ReviewMode): string {
  const tasks = day.items.filter((item) => item.taskId !== null)
  const busy = day.items.length - tasks.length
  if (tasks.length === 0 && busy === 0) return 'nothing planned'
  const parts: string[] = []
  if (tasks.length > 0) {
    if (mode === 'editable') {
      parts.push(`${tasks.length} proposed`)
    } else if (mode === 'writing' || mode === 'failed' || mode === 'closed') {
      parts.push(`${tasks.length} planned · not confirmed`)
    } else {
      parts.push(`${tasks.length} ${tasks.length === 1 ? 'task' : 'tasks'}`)
      const done = tasks.filter((item) => item.state === 'done').length
      if (done > 0) parts.push(`${done} logged`)
      const gone = tasks.filter((item) => item.state === 'deleted').length
      if (gone > 0) parts.push(`${gone} deleted from calendar`)
    }
  }
  if (busy > 0) parts.push(`${busy} fixed`)
  return parts.join(' · ')
}
