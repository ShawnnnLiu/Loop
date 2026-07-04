// Pure logic for the Week (schedule-review) screen: from the latest run's
// state, decide whether its draft is still an editable awaiting-approval draft
// or an already-written / active schedule that must render read-only — plus the
// honest banner copy for each read-only case. React-free and unit-tested, the
// same split as lib/approval.ts, so the screen stays a thin view over server
// truth (the server, not the client, owns which transitions are legal).

import type { StatusResult } from '../api/types'

export type ReviewMode = 'editable' | 'written' | 'writing' | 'failed'

/** Drag-to-adjust and approval are valid ONLY while the run awaits approval —
 *  the server enforces the same guard (adjust/approve both require
 *  AWAITING_USER_APPROVAL and 409 otherwise), so every other state must render
 *  read-only. A verified write activates the plan (ACTIVE_PLAN and its
 *  downstream drift / replan / terminal states); the two calendar_write_*
 *  progress states are transient mid-write; a failed write leaves the plan
 *  unactivated. A missing/blank state (no run yet) has no editable draft. */
export function reviewMode(status: StatusResult | null): ReviewMode {
  switch (status?.state) {
    case 'awaiting_user_approval':
      return 'editable'
    case 'calendar_write_approved':
    case 'calendar_write_in_progress':
      return 'writing'
    case 'calendar_write_failed':
      return 'failed'
    default:
      return 'written'
  }
}

export interface ReviewBanner {
  title: string
  sub: string
}

/** Banner copy for the read-only modes. 'failed' is the careful one: the MVP
 *  does not auto-roll-back, so it must NOT claim the blocks are on the calendar
 *  and must say the plan wasn't activated (same honesty as writeFailureMessage
 *  in lib/approval.ts). The 'editable' banner is bespoke — it carries the drag
 *  instructions and the approval CTA — so the screen renders that one directly. */
export function reviewBanner(mode: ReviewMode): ReviewBanner {
  switch (mode) {
    case 'written':
      return {
        title: 'Your week is scheduled',
        sub: 'These blocks are written to your Google Calendar and confirmed. Track them and check them off in Today.',
      }
    case 'writing':
      return {
        title: 'Writing your week…',
        sub: 'Loop is writing these blocks to your calendar and verifying each one. This page is read-only until that finishes.',
      }
    case 'failed':
      return {
        title: 'The last write didn’t fully verify',
        sub: 'These blocks aren’t confirmed on your calendar and your plan wasn’t activated. Open the approval screen to retry the missing events or remove what was written.',
      }
    case 'editable':
      return { title: 'Review your proposed week', sub: '' }
  }
}
