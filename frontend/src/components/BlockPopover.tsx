import { useEffect } from 'react'

import type { PopoverPlacement } from '../lib/popover'

// Details card for one grid block: the full (never ellipsized) title, times,
// and an honest status line mirroring the block's legend state. Presentational
// only (same posture as WeekPlanView): props in, callbacks out, no fetching.
// The card is absolutely positioned inside .sched-cols; the transparent
// backdrop is fixed so a click anywhere else closes it.

interface BlockPopoverProps {
  title: string // full, wrapped — never ellipsized
  when: string // "Tue Jul 21 · 10:30a–11:15a · 45m"
  status: string
  detail?: string | null // "Coding drills · deep focus" when known
  /** ALWAYS null today — tasks have no description field anywhere in the
   *  DraftView. The slot exists so a future plan only touches data plumbing. */
  description?: string | null
  placement: PopoverPlacement
  onClose: () => void
}

export function BlockPopover({
  title,
  when,
  status,
  detail,
  description,
  placement,
  onClose,
}: BlockPopoverProps) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <>
      <div className="blk-pop-backdrop" onClick={onClose} />
      <div
        className="blk-pop"
        role="dialog"
        aria-label={title}
        style={{
          left: `${placement.leftPct}%`,
          top: placement.topPx,
          transform:
            placement.side === 'left' ? 'translateX(calc(-100% - 6px))' : 'translateX(6px)',
        }}
      >
        <div className="bp-title">{title}</div>
        <div className="bp-when">{when}</div>
        <div className="bp-status">{status}</div>
        {detail && <div className="bp-detail">{detail}</div>}
        {description && <div className="bp-desc">{description}</div>}
      </div>
    </>
  )
}
