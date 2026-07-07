import { describe, expect, it } from 'vitest'

import type {
  CalendarEventDelta,
  CalendarReconciliationResult,
  ReconciliationOutcome,
} from '../api/types'
import {
  advisoryNote,
  flaggedReason,
  needsDraftRefetch,
  reconcileBanner,
  reconcileDismissKey,
  syncedAtMs,
} from './reconcile'

function delta(over: Partial<CalendarEventDelta>): CalendarEventDelta {
  return {
    task_id: 'dp_001',
    calendar_event_id: 'gcal_evt_1',
    change_type: 'moved',
    recorded_start: '2026-06-23T19:00:00-07:00',
    recorded_end: '2026-06-23T20:30:00-07:00',
    observed_start: '2026-06-24T19:00:00-07:00',
    observed_end: '2026-06-24T20:30:00-07:00',
    disposition: 'adopted',
    reason_code: null,
    ...over,
  }
}

function result(
  outcome: ReconciliationOutcome,
  deltas: CalendarEventDelta[],
): CalendarReconciliationResult {
  return {
    run_id: 'run_1',
    plan_version: 'plan_004',
    reconciled_at: '2026-06-23T09:05:00-07:00',
    target_calendar_id: 'gcal_dedicated_abc',
    outcome,
    adopted_draft_schedule_id: deltas.some((d) => d.disposition === 'adopted') ? 'draft_17' : null,
    deltas,
  }
}

const adoptedDelta = delta({ task_id: 'dp_a', disposition: 'adopted', reason_code: null })
const rejectedDelta = delta({
  task_id: 'dp_r',
  disposition: 'rejected',
  reason_code: 'OUTSIDE_ALLOWED_HOURS',
})
const deletedDelta = delta({
  task_id: 'dp_d',
  change_type: 'deleted',
  observed_start: null,
  observed_end: null,
  disposition: 'flagged_deleted',
  reason_code: 'EXTERNAL_EVENT_DELETED',
})

describe('reconcileBanner', () => {
  it('renders nothing for the no-op outcomes (disabled / deferred / no change)', () => {
    expect(reconcileBanner(result('sync_disabled', []))).toBeNull()
    expect(reconcileBanner(result('deferred', []))).toBeNull()
    expect(reconcileBanner(result('no_change', [delta({ change_type: 'unchanged', disposition: 'unchanged' })]))).toBeNull()
  })

  it('adopted-only is the positive tone and points at the calendar match', () => {
    const banner = reconcileBanner(result('adopted', [adoptedDelta]))
    expect(banner?.tone).toBe('adopted')
    expect(banner?.title).toBe('1 calendar edit adopted')
    expect(banner?.sub).toContain('Google Calendar')
    expect(banner?.adopted).toHaveLength(1)
    expect(banner?.flagged).toHaveLength(0)
  })

  it('flagged-only is honest: plan out of sync, Loop did not touch the calendar, rebuild catches up', () => {
    const banner = reconcileBanner(result('flagged', [rejectedDelta, deletedDelta]))
    expect(banner?.tone).toBe('flagged')
    expect(banner?.title).toBe('2 calendar edits couldn’t be applied')
    expect(banner?.sub.toLowerCase()).toContain('out of sync')
    expect(banner?.sub.toLowerCase()).toContain('rebuild')
    expect(banner?.flagged).toHaveLength(2)
  })

  it('never claims a deleted event is still on the calendar', () => {
    // A flagged_deleted edit means the event is GONE — the banner must not
    // assert it was "left on your calendar" (a false presence claim).
    for (const banner of [
      reconcileBanner(result('flagged', [deletedDelta])),
      reconcileBanner(result('mixed', [adoptedDelta, deletedDelta])),
    ]) {
      expect(banner?.sub.toLowerCase()).not.toContain('on your calendar')
      expect(banner?.sub.toLowerCase()).not.toContain('left it')
      expect(banner?.sub.toLowerCase()).not.toContain('left them')
    }
  })

  it('mixed carries both lists and a combined title', () => {
    const banner = reconcileBanner(result('mixed', [adoptedDelta, rejectedDelta]))
    expect(banner?.tone).toBe('mixed')
    expect(banner?.title).toBe('1 adopted · 1 couldn’t be applied')
    expect(banner?.adopted).toHaveLength(1)
    expect(banner?.flagged).toHaveLength(1)
  })

  it('never claims an edit was reverted, undone, rolled back, or restored', () => {
    const banners = [
      reconcileBanner(result('adopted', [adoptedDelta])),
      reconcileBanner(result('flagged', [rejectedDelta, deletedDelta])),
      reconcileBanner(result('mixed', [adoptedDelta, deletedDelta])),
    ]
    for (const banner of banners) {
      const text = `${banner?.title} ${banner?.sub}`.toLowerCase()
      for (const forbidden of ['rolled back', 'roll back', 'reverted', 'revert', 'undone', 'undid', 'restored', 'changed back']) {
        expect(text).not.toContain(forbidden)
      }
    }
  })
})

describe('needsDraftRefetch', () => {
  it('refetches after an adopted draft (new times live server-side)', () => {
    expect(needsDraftRefetch(result('adopted', [adoptedDelta]))).toBe(true)
  })

  it('refetches after a deletion — the pull just recorded the event_deleted memory that feeds DraftView.deleted_task_ids', () => {
    expect(needsDraftRefetch(result('flagged', [deletedDelta]))).toBe(true)
    expect(needsDraftRefetch(result('mixed', [adoptedDelta, deletedDelta]))).toBe(true)
  })

  it('does not refetch when nothing server-side changed (no-op or rejected-only)', () => {
    expect(needsDraftRefetch(result('no_change', []))).toBe(false)
    expect(needsDraftRefetch(result('flagged', [rejectedDelta]))).toBe(false)
  })
})

describe('flaggedReason', () => {
  it('explains a deletion without implying Loop touched the calendar', () => {
    expect(flaggedReason(deletedDelta)).toBe('you deleted this event from your calendar')
  })

  it('humanizes each drag-to-adjust placement code', () => {
    const codes = {
      NO_VALID_CONTIGUOUS_BLOCK: 'no open block long enough at the new time',
      OUTSIDE_ALLOWED_HOURS: 'the new time is outside your allowed hours',
      DAILY_LOAD_EXCEEDED: 'that day would go over your daily study limit',
      DEPENDENCY_BLOCKED: 'it would start before a task it depends on',
    }
    for (const [code, text] of Object.entries(codes)) {
      expect(flaggedReason(delta({ disposition: 'rejected', reason_code: code }))).toBe(text)
    }
  })

  it('falls back to the raw code rather than inventing an explanation', () => {
    expect(flaggedReason(delta({ disposition: 'rejected', reason_code: 'SOME_NEW_CODE' }))).toBe('SOME_NEW_CODE')
  })
})

describe('advisoryNote', () => {
  it('phrases an adopted overlap as kept, never as an error (ADR-0009)', () => {
    const note = advisoryNote(delta({ disposition: 'adopted', reason_code: 'OVERLAP_ADVISORY' }))
    expect(note).toBe('now overlaps another event — kept where you put it')
    expect(note?.toLowerCase()).not.toContain('rejected')
    expect(note?.toLowerCase()).not.toContain('couldn’t')
  })

  it('phrases an adopted before-prerequisite move as kept (ADR-0008)', () => {
    expect(advisoryNote(delta({ disposition: 'adopted', reason_code: 'DEPENDENCY_ADVISORY' }))).toBe(
      'now starts before a task it depends on — kept where you put it',
    )
  })

  it('phrases an adopted over-cap day as kept, never as an error (ADR-0010)', () => {
    const note = advisoryNote(delta({ disposition: 'adopted', reason_code: 'DAILY_LOAD_ADVISORY' }))
    expect(note).toBe('that day now goes over your daily study limit — kept where you put it')
    expect(note?.toLowerCase()).not.toContain('rejected')
    expect(note?.toLowerCase()).not.toContain('couldn’t')
  })

  it('is null for a plain adopted edit and for non-adopted dispositions', () => {
    expect(advisoryNote(adoptedDelta)).toBeNull()
    expect(advisoryNote(rejectedDelta)).toBeNull()
    expect(advisoryNote(deletedDelta)).toBeNull()
    // An unknown advisory code says nothing rather than inventing a note.
    expect(advisoryNote(delta({ disposition: 'adopted', reason_code: 'SOME_NEW_CODE' }))).toBeNull()
  })
})

describe('reconcileDismissKey', () => {
  it('is null when there is nothing recurring to dismiss — no banner, or adopted-only (which self-heals off the next pull)', () => {
    expect(reconcileDismissKey(result('no_change', []))).toBeNull()
    expect(reconcileDismissKey(result('sync_disabled', []))).toBeNull()
    expect(reconcileDismissKey(result('adopted', [adoptedDelta]))).toBeNull()
  })

  it('is stable across pulls that re-detect the same flagged edits (different run/timestamp)', () => {
    // Deleted events stay gone, so every Week-mount pull re-produces the same
    // flagged deltas — the whole reason a dismissal must key on content.
    const first = result('flagged', [rejectedDelta, deletedDelta])
    const later: CalendarReconciliationResult = {
      ...result('flagged', [deletedDelta, rejectedDelta]), // order-independent too
      run_id: 'run_2',
      reconciled_at: '2026-06-24T08:00:00-07:00',
    }
    expect(reconcileDismissKey(first)).not.toBeNull()
    expect(reconcileDismissKey(later)).toBe(reconcileDismissKey(first))
  })

  it('keeps its key when a mixed banner collapses to flagged-only with the same flagged set', () => {
    // The adopted half self-heals (next pull sees it unchanged); the surviving
    // deletion is the same nag, so it must stay dismissed.
    const mixed = result('mixed', [adoptedDelta, deletedDelta])
    const flaggedOnly = result('flagged', [deletedDelta])
    expect(reconcileDismissKey(mixed)).toBe(reconcileDismissKey(flaggedOnly))
  })

  it('changes when the flagged content changes — new deletion, re-moved edit, or new plan version', () => {
    const base = result('flagged', [deletedDelta])
    const extraDeletion = result('flagged', [
      deletedDelta,
      delta({ ...deletedDelta, task_id: 'dp_d2' }),
    ])
    const movedAgain = result('flagged', [
      delta({ ...rejectedDelta, observed_start: '2026-06-25T23:00:00-07:00', observed_end: '2026-06-26T00:30:00-07:00' }),
    ])
    const newPlan: CalendarReconciliationResult = { ...base, plan_version: 'plan_005' }
    const keys = [base, extraDeletion, movedAgain, newPlan].map(reconcileDismissKey)
    expect(new Set(keys).size).toBe(keys.length)
  })
})

describe('syncedAtMs', () => {
  const atMs = Date.parse('2026-06-23T09:05:00-07:00')

  it('returns the server-stamped instant whenever a comparison actually ran', () => {
    expect(syncedAtMs(result('no_change', []))).toBe(atMs)
    expect(syncedAtMs(result('adopted', [adoptedDelta]))).toBe(atMs)
    expect(syncedAtMs(result('flagged', [rejectedDelta]))).toBe(atMs)
    expect(syncedAtMs(result('mixed', [adoptedDelta, rejectedDelta]))).toBe(atMs)
  })

  it('is null when no comparison ran — those pulls must not claim "synced"', () => {
    expect(syncedAtMs(result('sync_disabled', []))).toBeNull()
    expect(syncedAtMs(result('deferred', []))).toBeNull()
  })
})
