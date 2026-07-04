// Pure logic for surfacing an inbound-reconciliation pull on the Week screen:
// from a CalendarReconciliationResult, decide whether there is anything to show
// and produce honest banner copy + the per-edit explanation for what could not
// be applied. React-free and unit-tested, the same split as lib/review.ts and
// lib/approval.ts, so the screen stays a thin view over server truth.
//
// Honesty (a hard project axiom): reconciliation is READ-ONLY against the
// calendar — Loop never rewrites the user's calendar. So a rejected or deleted
// edit is left exactly as the user made it; only the in-app plan is out of sync,
// which a rebuild fixes. The copy here never claims an edit was reverted,
// undone, rolled back, or restored.

import type { CalendarEventDelta, CalendarReconciliationResult } from '../api/types'

export type ReconcileTone = 'adopted' | 'flagged' | 'mixed'

export interface ReconcileBanner {
  tone: ReconcileTone
  title: string
  sub: string
  /** Adopted moves/resizes — the plan was updated to match these. */
  adopted: CalendarEventDelta[]
  /** Edits Loop could not apply (rejected placements + deletions), each kept on
   *  the calendar exactly as the user made it. */
  flagged: CalendarEventDelta[]
}

const plural = (n: number, one: string, many: string): string => (n === 1 ? one : many)

/** The banner to show for a reconcile pull, or null when there is nothing to
 *  surface. Driven off the per-edit dispositions (not the roll-up outcome) so
 *  the banner counts can never disagree with the lists rendered beside them:
 *  `sync_disabled` / `deferred` / `no_change` all carry zero adopted-or-flagged
 *  deltas and so collapse to null here. */
export function reconcileBanner(result: CalendarReconciliationResult): ReconcileBanner | null {
  const adopted = result.deltas.filter((d) => d.disposition === 'adopted')
  const flagged = result.deltas.filter(
    (d) => d.disposition === 'rejected' || d.disposition === 'flagged_deleted',
  )
  const a = adopted.length
  const f = flagged.length
  if (a === 0 && f === 0) return null

  if (a > 0 && f === 0) {
    return {
      tone: 'adopted',
      title: `${a} calendar ${plural(a, 'edit', 'edits')} adopted`,
      sub: `Loop updated your plan to match the ${plural(a, 'time', 'times')} you set on your Google Calendar.`,
      adopted,
      flagged,
    }
  }
  if (a === 0 && f > 0) {
    return {
      tone: 'flagged',
      // Don't assert where the events are: a rejected edit sits at the user's
      // new (plan-invalid) time, but a deleted one is gone — so state only what
      // is true for both, that Loop never touched the calendar and the plan now
      // diverges. The per-edit list below says what happened to each.
      title: `${f} calendar ${plural(f, 'edit', 'edits')} couldn’t be applied`,
      sub:
        `Loop never changes your calendar, so ${plural(f, 'this edit is', 'these edits are')} only out of ` +
        `sync with your plan. Rebuild your plan to catch up.`,
      adopted,
      flagged,
    }
  }
  return {
    tone: 'mixed',
    title: `${a} adopted · ${f} couldn’t be applied`,
    sub:
      `Loop updated your plan to match the valid ${plural(a, 'edit', 'edits')} and never changes your ` +
      `calendar, so the rest ${plural(f, 'is', 'are')} just out of sync with your plan. Rebuild your plan to catch up.`,
    adopted,
    flagged,
  }
}

/** True when the pull changed server-side truth an already-fetched DraftView
 *  cannot reflect: an adopted draft (new times) or a deletion (the pull just
 *  recorded the durable `event_deleted` memory that feeds
 *  `DraftView.deleted_task_ids`, so the grid must refetch to mark the block). */
export function needsDraftRefetch(result: CalendarReconciliationResult): boolean {
  return (
    result.adopted_draft_schedule_id != null ||
    result.deltas.some((d) => d.disposition === 'flagged_deleted')
  )
}

/** A short, honest reason a single flagged edit could not be applied. Deletions
 *  and the four drag-to-adjust placement codes (the shared refusal vocabulary)
 *  get human phrasing; any other code falls back to the raw value rather than
 *  inventing an explanation. */
export function flaggedReason(delta: CalendarEventDelta): string {
  if (delta.disposition === 'flagged_deleted' || delta.change_type === 'deleted') {
    return 'you deleted this event from your calendar'
  }
  switch (delta.reason_code) {
    case 'NO_VALID_CONTIGUOUS_BLOCK':
      return 'no open block long enough at the new time'
    case 'OUTSIDE_ALLOWED_HOURS':
      return 'the new time is outside your allowed hours'
    case 'DAILY_LOAD_EXCEEDED':
      return 'that day would go over your daily study limit'
    case 'DEPENDENCY_BLOCKED':
      return 'it would start before a task it depends on'
    default:
      return delta.reason_code ?? 'it couldn’t be placed'
  }
}
