import { describe, expect, it } from 'vitest'

import type {
  DraftScheduleEntry,
  DraftView,
  TodayResult,
  TodayTask,
  UserProfile,
} from '../api/types'
import { DAY_MS } from './datetime'
import type { ReviewMode } from './review'
import {
  type PlanItem,
  buildWeekPlan,
  dayMeta,
  fmtDur,
  milestoneGroups,
  railAction,
  railCounts,
  railMeta,
  railStatus,
  targetLine,
  taskState,
  todayFacts,
  weekRangeLabel,
} from './weekplan'

// Window anchored on Mon 2026-04-27 (matches the rolling today-first grid).
const WINDOW = Date.UTC(2026, 3, 27)

const entry = (taskId: string, start: string, end: string): DraftScheduleEntry => ({
  task_id: taskId,
  start,
  end,
  calendar_event_status: 'draft_only',
})

const draftView = (
  over: Partial<Pick<DraftView, 'free_busy' | 'task_titles' | 'deleted_task_ids'>> & {
    entries?: DraftScheduleEntry[]
  } = {},
): DraftView => ({
  draft: { draft_schedule_id: 'd1', plan_version: 'pv1', entries: over.entries ?? [] },
  payload_hash: 'hash',
  hash_canonicalization_version: 'v1',
  free_busy: over.free_busy ?? [],
  task_titles: over.task_titles ?? {},
  deleted_task_ids: over.deleted_task_ids ?? [],
  plan_diff: null,
})

const todayRow = (taskId: string, over: Partial<TodayTask> = {}): TodayTask => ({
  task_id: taskId,
  title: taskId,
  category: 'study',
  required_focus_level: 'medium',
  start: '2026-04-27T09:00:00+02:00',
  end: '2026-04-27T10:00:00+02:00',
  due: false,
  reported: false,
  deleted: false,
  ...over,
})

const todayResult = (tasks: TodayTask[]): TodayResult => ({ timezone: 'Europe/Berlin', tasks })

const profileFixture = (): UserProfile => ({
  user_id: 'u1',
  profile_version: 'v1',
  goal: 'Land a backend role',
  target_role: 'Backend SWE',
  target_companies: [],
  target_level: null,
  timeline_weeks: 12,
  weekly_hours: 10,
  experience_level: 'intermediate',
  known_strengths: [],
  known_weaknesses: [],
  experience: [],
  skills: [],
  preferred_session_length_min: 60,
  max_session_length_min: 120,
  deep_work_windows: [],
  hard_constraints: {
    no_events_before: '08:00',
    no_events_after: '22:00',
    allow_weekends: true,
    max_daily_study_min: 240,
    min_break_between_deep_blocks_min: 30,
  },
  preferences: {
    prefer_evening_sessions: false,
    prefer_weekend_long_blocks: false,
    avoid_back_to_back_deep_work: true,
  },
  motivation_profile_id: null,
  pathway_selection: null,
  resume_text: null,
  plan_direction: null,
  created_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
})

const NO_FACTS = todayFacts(null)

const pitem = (over: Partial<PlanItem> = {}): PlanItem => ({
  key: 't1',
  taskId: 't1',
  title: 'Task 1',
  dayMs: WINDOW,
  startMin: 540,
  endMin: 600,
  state: 'accepted',
  pastDue: false,
  category: null,
  focusLevel: null,
  ...over,
})

describe('taskState', () => {
  it('maps everything to proposed while the draft is editable (nothing written yet)', () => {
    expect(taskState('editable', false, false)).toBe('proposed')
    expect(taskState('editable', true, true)).toBe('proposed')
  })

  it('maps written-mode entries by reported/deleted facts', () => {
    expect(taskState('written', false, false)).toBe('accepted')
    expect(taskState('written', false, true)).toBe('done')
    expect(taskState('written', true, false)).toBe('deleted')
  })

  it('never lets a deleted event read as done (deleted beats reported)', () => {
    expect(taskState('written', true, true)).toBe('deleted')
    expect(taskState('replan', true, true)).toBe('deleted')
  })

  it('treats a parked replan like written (the active plan is unchanged)', () => {
    expect(taskState('replan', false, true)).toBe('done')
    expect(taskState('replan', false, false)).toBe('accepted')
  })

  it('collapses writing/failed/closed to unconfirmed — never on-calendar', () => {
    for (const mode of ['writing', 'failed', 'closed'] as ReviewMode[]) {
      expect(taskState(mode, false, false)).toBe('unconfirmed')
      expect(taskState(mode, false, true)).toBe('unconfirmed')
      expect(taskState(mode, true, false)).toBe('unconfirmed')
    }
  })
})

describe('todayFacts', () => {
  it('returns empty sets for a missing result', () => {
    expect(NO_FACTS.reported.size).toBe(0)
    expect(NO_FACTS.due.size).toBe(0)
  })

  it('partitions reported and due by task', () => {
    const facts = todayFacts(
      todayResult([
        todayRow('a', { reported: true }),
        todayRow('b', { due: true }),
        todayRow('c', { due: true, reported: true }),
      ]),
    )
    expect([...facts.reported].sort()).toEqual(['a', 'c'])
    expect([...facts.due].sort()).toEqual(['b', 'c'])
  })
})

describe('buildWeekPlan', () => {
  it('always returns 7 days, rest-marked when empty', () => {
    const days = buildWeekPlan(draftView(), 'editable', NO_FACTS, WINDOW, WINDOW)
    expect(days).toHaveLength(7)
    expect(days.every((d) => d.items.length === 0)).toBe(true)
    expect(days.every((d) => d.meta === 'rest')).toBe(true)
  })

  it('places entries on their wall-clock day and sorts by start time', () => {
    const view = draftView({
      entries: [
        entry('late', '2026-04-28T15:00:00+02:00', '2026-04-28T16:00:00+02:00'),
        entry('early', '2026-04-28T09:30:00+02:00', '2026-04-28T10:15:00+02:00'),
      ],
      task_titles: { early: 'Early task' },
    })
    const days = buildWeekPlan(view, 'editable', NO_FACTS, WINDOW, WINDOW)
    const tue = days[1]
    expect(tue.items.map((i) => i.key)).toEqual(['early', 'late'])
    // Wall-clock gridding: 09:30+02:00 is 570 minutes as written, regardless
    // of the browser's timezone.
    expect(tue.items[0].startMin).toBe(570)
    expect(tue.items[0].endMin).toBe(615)
    expect(tue.items[0].title).toBe('Early task')
    // Missing title falls back to the task id.
    expect(tue.items[1].title).toBe('late')
  })

  it('excludes entries outside the 7-day window', () => {
    const view = draftView({
      entries: [entry('next-week', '2026-05-04T09:00:00+02:00', '2026-05-04T10:00:00+02:00')],
    })
    const days = buildWeekPlan(view, 'editable', NO_FACTS, WINDOW, WINDOW)
    expect(days.every((d) => d.items.length === 0)).toBe(true)
  })

  it('turns free/busy intervals into locked items without a task id', () => {
    const view = draftView({
      free_busy: [{ start: '2026-04-27T12:00:00+02:00', end: '2026-04-27T13:30:00+02:00' }],
    })
    const days = buildWeekPlan(view, 'written', NO_FACTS, WINDOW, WINDOW)
    expect(days[0].items).toHaveLength(1)
    const busy = days[0].items[0]
    expect(busy.taskId).toBeNull()
    expect(busy.key).toBe('busy0')
    expect(busy.state).toBe('locked')
    expect(busy.startMin).toBe(720)
    expect(busy.endMin).toBe(810)
    expect(days[0].meta).toBe('busy day')
  })

  it('marks only the anchor column as today, and no column in a past window', () => {
    const current = buildWeekPlan(draftView(), 'written', NO_FACTS, WINDOW, WINDOW)
    expect(current.map((d) => d.isToday)).toEqual([true, false, false, false, false, false, false])
    const past = buildWeekPlan(draftView(), 'written', NO_FACTS, WINDOW - 7 * DAY_MS, WINDOW)
    expect(past.every((d) => !d.isToday)).toBe(true)
  })

  it('labels days across a month boundary (Apr 27 window runs into May)', () => {
    const days = buildWeekPlan(draftView(), 'editable', NO_FACTS, WINDOW, WINDOW)
    expect(days.map((d) => d.num)).toEqual([27, 28, 29, 30, 1, 2, 3])
    expect(days[0].dow).toBe('Mon')
    expect(days[4].label).toBe('May 1')
  })

  it('joins today-facts onto written entries: reported→done, due→pastDue', () => {
    const view = draftView({
      entries: [
        entry('logged', '2026-04-27T09:00:00+02:00', '2026-04-27T10:00:00+02:00'),
        entry('overdue', '2026-04-27T10:00:00+02:00', '2026-04-27T11:00:00+02:00'),
        entry('gone', '2026-04-27T11:00:00+02:00', '2026-04-27T12:00:00+02:00'),
      ],
      deleted_task_ids: ['gone'],
    })
    const facts = todayFacts(
      todayResult([
        todayRow('logged', { reported: true, due: true }),
        todayRow('overdue', { due: true }),
      ]),
    )
    const [mon] = buildWeekPlan(view, 'written', facts, WINDOW, WINDOW)
    const byKey = new Map(mon.items.map((i) => [i.key, i]))
    expect(byKey.get('logged')).toMatchObject({ state: 'done', pastDue: false })
    expect(byKey.get('overdue')).toMatchObject({ state: 'accepted', pastDue: true })
    expect(byKey.get('gone')).toMatchObject({ state: 'deleted' })
    expect(mon.meta).toBe('1 done · 2 to go')
  })

  it('carries category and focus level from today onto items', () => {
    const view = draftView({
      entries: [entry('a', '2026-04-27T09:00:00+02:00', '2026-04-27T10:00:00+02:00')],
    })
    const facts = todayFacts(
      todayResult([todayRow('a', { category: 'system_design', required_focus_level: 'deep' })]),
    )
    const [mon] = buildWeekPlan(view, 'written', facts, WINDOW, WINDOW)
    expect(mon.items[0]).toMatchObject({ category: 'system_design', focusLevel: 'deep' })
  })
})

describe('weekRangeLabel', () => {
  it('renders a same-month window compactly', () => {
    expect(weekRangeLabel(Date.UTC(2026, 6, 6))).toBe('Jul 6 — 12')
  })

  it('spells out both months across a boundary', () => {
    expect(weekRangeLabel(WINDOW)).toBe('Apr 27 — May 3')
  })
})

describe('milestoneGroups', () => {
  it('is empty without today data (editable and unconfirmed modes)', () => {
    expect(milestoneGroups(null)).toEqual([])
    expect(milestoneGroups(todayResult([]))).toEqual([])
  })

  it('groups by category in first-appearance order with check-in progress', () => {
    const groups = milestoneGroups(
      todayResult([
        todayRow('a', { category: 'dsa', reported: true }),
        todayRow('b', { category: 'dsa' }),
        todayRow('c', { category: 'system_design', reported: true }),
        todayRow('d', { category: 'behavioral' }),
      ]),
    )
    expect(groups).toEqual([
      { label: 'Dsa', done: 1, total: 2, state: 'active' },
      { label: 'System design', done: 1, total: 1, state: 'done' },
      { label: 'Behavioral', done: 0, total: 1, state: 'todo' },
    ])
  })
})

describe('targetLine', () => {
  it('is null without a profile', () => {
    expect(targetLine(null)).toBeNull()
  })

  it('renders role and committed timeline from the real profile', () => {
    expect(targetLine(profileFixture())).toBe('Backend SWE · ~12 wks')
  })
})

describe('railStatus', () => {
  it('maps every mode to an honest badge', () => {
    expect(railStatus('written')).toEqual({ label: 'on track', tone: 'sage' })
    expect(railStatus('replan')).toEqual({ label: 'needs update', tone: 'clay' })
    expect(railStatus('editable')).toEqual({ label: 'awaiting approval', tone: 'clay' })
    expect(railStatus('failed')).toEqual({ label: 'write not verified', tone: 'clay' })
    expect(railStatus('writing')).toEqual({ label: 'writing…', tone: 'muted' })
    expect(railStatus('closed')).toEqual({ label: 'closed', tone: 'muted' })
  })
})

describe('dayMeta', () => {
  it('distinguishes rest from busy-only days', () => {
    expect(dayMeta('written', [])).toBe('rest')
    expect(dayMeta('written', [pitem({ taskId: null, key: 'busy0', state: 'locked' })])).toBe(
      'busy day',
    )
  })

  it('counts proposed in editable mode and planned in unconfirmed modes', () => {
    expect(dayMeta('editable', [pitem({ state: 'proposed' })])).toBe('1 proposed')
    expect(dayMeta('writing', [pitem({ state: 'unconfirmed' })])).toBe('1 planned')
    expect(dayMeta('closed', [pitem({ state: 'unconfirmed' })])).toBe('1 planned')
  })

  it('reports progress only for a written plan', () => {
    const done = pitem({ key: 'a', taskId: 'a', state: 'done' })
    const open = pitem({ key: 'b', taskId: 'b', state: 'accepted' })
    expect(dayMeta('written', [done])).toBe('all done')
    expect(dayMeta('written', [done, open])).toBe('1 done · 1 to go')
    expect(dayMeta('written', [open])).toBe('1 to go')
  })
})

describe('railAction / railMeta', () => {
  it('proposed → switch to the grid (drag is the edit surface)', () => {
    const item = pitem({ state: 'proposed' })
    expect(railAction(item)).toEqual({ kind: 'grid', label: 'Adjust →' })
    expect(railMeta(item)).toBe('proposed · 1h')
  })

  it('accepted → on-calendar chip, or a Today link when past due', () => {
    expect(railAction(pitem({ state: 'accepted' }))).toEqual({ kind: 'chip', label: 'on calendar' })
    expect(railAction(pitem({ state: 'accepted', pastDue: true }))).toEqual({
      kind: 'link',
      label: 'Check in →',
      to: '/today',
    })
    expect(railMeta(pitem({ state: 'accepted', pastDue: true, endMin: 585 }))).toBe(
      'on your Google Calendar · 45m · past due — check in',
    )
  })

  it('done → logged chip with planned duration', () => {
    expect(railAction(pitem({ state: 'done' }))).toEqual({ kind: 'chip', label: 'logged ✓' })
    expect(railMeta(pitem({ state: 'done', endMin: 630 }))).toBe('logged · 1h 30m planned')
  })

  it('locked → gcal chip, no invented details', () => {
    const item = pitem({ taskId: null, key: 'busy0', state: 'locked' })
    expect(railAction(item)).toEqual({ kind: 'chip', label: 'gcal' })
    expect(railMeta(item)).toBe('from Google Calendar · fixed')
  })

  it('deleted → still-planned wording and a Today link, never done', () => {
    const item = pitem({ state: 'deleted' })
    expect(railAction(item)).toEqual({ kind: 'link', label: 'Check in →', to: '/today' })
    expect(railMeta(item)).toBe('deleted from your calendar · still planned')
  })

  it('unconfirmed → explicit not-on-calendar wording', () => {
    const item = pitem({ state: 'unconfirmed' })
    expect(railAction(item)).toEqual({ kind: 'chip', label: 'not confirmed' })
    expect(railMeta(item)).toBe('planned · 1h · not confirmed on your calendar')
  })

  it('appends category and focus level when today supplies them', () => {
    expect(
      railMeta(pitem({ state: 'accepted', category: 'system_design', focusLevel: 'deep' })),
    ).toBe('on your Google Calendar · 1h · System design · deep focus')
    expect(railMeta(pitem({ state: 'done', category: 'dsa' }))).toBe(
      'logged · 1h planned · Dsa',
    )
  })
})

describe('railCounts', () => {
  const day = (items: PlanItem[]) => ({
    dayIdx: 0,
    dayMs: WINDOW,
    dow: 'Mon',
    label: 'Apr 27',
    num: 27,
    isToday: true,
    meta: '',
    items,
  })

  it('says nothing planned for an empty day', () => {
    expect(railCounts(day([]), 'written')).toBe('nothing planned')
  })

  it('counts proposed plus fixed in editable mode', () => {
    const items = [
      pitem({ state: 'proposed' }),
      pitem({ key: 'busy0', taskId: null, state: 'locked' }),
    ]
    expect(railCounts(day(items), 'editable')).toBe('1 proposed · 1 fixed')
  })

  it('summarizes written days with logged and deleted counts', () => {
    const items = [
      pitem({ key: 'a', taskId: 'a', state: 'done' }),
      pitem({ key: 'b', taskId: 'b', state: 'accepted' }),
      pitem({ key: 'c', taskId: 'c', state: 'deleted' }),
      pitem({ key: 'busy0', taskId: null, state: 'locked' }),
    ]
    expect(railCounts(day(items), 'written')).toBe(
      '3 tasks · 1 logged · 1 deleted from calendar · 1 fixed',
    )
  })

  it('never claims confirmation in unconfirmed modes', () => {
    expect(railCounts(day([pitem({ state: 'unconfirmed' })]), 'failed')).toBe(
      '1 planned · not confirmed',
    )
  })
})

describe('fmtDur', () => {
  it('renders whole hours without a minutes part', () => {
    expect(fmtDur(120)).toBe('2h')
  })

  it('renders mixed and sub-hour durations', () => {
    expect(fmtDur(105)).toBe('1h 45m')
    expect(fmtDur(45)).toBe('45m')
  })
})
