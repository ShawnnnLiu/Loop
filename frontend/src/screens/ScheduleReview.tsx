import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, api, errorMessage } from '../api/client'
import type { DraftView } from '../api/types'
import {
  dayHeader,
  dayUtcMs,
  fmtMinutes,
  isoAt,
  minutesOfDay,
  mondayIndex,
  parseWall,
  weekMondayMs,
} from '../lib/datetime'

// The drag-to-adjust schedule review (the signature interaction). PROPOSED
// blocks are draggable (snap 15 min, move across the week's days); imported
// Google-Calendar busy times are fixed and translucent. On drop we send the new
// start to POST /api/adjust and RE-RENDER FROM THE SERVER — it re-validates
// every move and never trusts the client (backend D-6). A rejected move keeps a
// typed reason_code and the block snaps back to the server's truth. There is no
// 60s undo; per-block control here is what makes the single plan-level approval
// (next screen) safe.

const START_HOUR = 8
const END_HOUR = 23
const HOURS = END_HOUR - START_HOUR
const HOUR_PX = 46
const SNAP = 15
const GRID_TOP = START_HOUR * 60
const GRID_BOT = END_HOUR * 60

interface Block {
  taskId: string
  title: string
  mondayMs: number
  dayIdx: number
  startMin: number
  durMin: number
  offset: string
}

interface BusyBlock {
  mondayMs: number
  dayIdx: number
  startMin: number
  durMin: number
}

type DragState = { taskId: string; dayIdx: number; startMin: number }

function toBlocks(view: DraftView): Block[] {
  const titles = view.task_titles
  return (view.draft?.entries ?? []).map((entry) => {
    const start = parseWall(entry.start)
    const dayMs = dayUtcMs(start)
    return {
      taskId: entry.task_id,
      title: titles[entry.task_id] ?? entry.task_id,
      mondayMs: weekMondayMs(dayMs),
      dayIdx: mondayIndex(dayMs),
      startMin: minutesOfDay(start),
      durMin: Math.round((Date.parse(entry.end) - Date.parse(entry.start)) / 60000),
      offset: start.offset,
    }
  })
}

function toBusy(view: DraftView): BusyBlock[] {
  return view.free_busy.map((interval) => {
    const start = parseWall(interval.start)
    const dayMs = dayUtcMs(start)
    return {
      mondayMs: weekMondayMs(dayMs),
      dayIdx: mondayIndex(dayMs),
      startMin: minutesOfDay(start),
      durMin: Math.round((Date.parse(interval.end) - Date.parse(interval.start)) / 60000),
    }
  })
}

const topPx = (startMin: number) => ((startMin - GRID_TOP) / 60) * HOUR_PX
const heightPx = (durMin: number) => Math.max(18, (durMin / 60) * HOUR_PX - 3)
const clamp = (n: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, n))

export function ScheduleReviewScreen() {
  const navigate = useNavigate()
  const [view, setView] = useState<DraftView | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [weekIdx, setWeekIdx] = useState(0)
  const [drag, setDrag] = useState<DragState | null>(null)
  const [saving, setSaving] = useState(false)
  const [violation, setViolation] = useState<{ taskId: string; text: string } | null>(null)
  const colsRef = useRef<HTMLDivElement>(null)
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
    api
      .draft()
      .then((v) => active && (setView(v), setLoading(false)))
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

  if (loading) return <div className="screen-center muted">Loading your draft…</div>
  if (error) return <div className="screen-center">Couldn’t load the draft — {error}</div>

  const blocks = view ? toBlocks(view) : []
  const busy = view ? toBusy(view) : []
  if (blocks.length === 0) {
    return (
      <div className="screen-center col" style={{ gap: 12 }}>
        <h2 className="t-h2">No draft to review yet</h2>
        <button className="btn btn-primary" type="button" onClick={() => navigate('/plan')}>
          Build a plan →
        </button>
      </div>
    )
  }

  const weeks = [...new Set(blocks.map((b) => b.mondayMs))].sort((a, b) => a - b)
  const safeWeek = clamp(weekIdx, 0, weeks.length - 1)
  const mondayMs = weeks[safeWeek]
  const weekBlocks = blocks.filter((b) => b.mondayMs === mondayMs)
  const weekBusy = busy.filter((b) => b.mondayMs === mondayMs)

  const posOf = (b: Block): { dayIdx: number; startMin: number } =>
    drag && drag.taskId === b.taskId ? { dayIdx: drag.dayIdx, startMin: drag.startMin } : b

  function onDown(event: React.PointerEvent, b: Block) {
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
    setDrag({ taskId: b.taskId, dayIdx: b.dayIdx, startMin: b.startMin })
  }

  function onMove(event: React.PointerEvent) {
    const g = geo.current
    if (!g) return
    const dDay = Math.round((event.clientX - g.x0) / g.dayW)
    const dMin = Math.round(((event.clientY - g.y0) / g.hourH) * 60) / SNAP
    const day = clamp(g.origDay + dDay, 0, 6)
    const start = clamp(g.origStart + Math.round(dMin) * SNAP, GRID_TOP, GRID_BOT - g.dur)
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
      setDrag(null) // no move
      return
    }
    setSaving(true)
    const iso = isoAt(mondayMs, g.day, g.start, g.offset)
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

  return (
    <div className="sched">
      <div className="sched-banner">
        <span className="agent-mark">✦</span>
        <div style={{ flex: 1 }}>
          <div className="t-h3">Review your proposed week</div>
          <div className="muted" style={{ fontSize: 13, marginTop: 2 }}>
            Drag any <b style={{ color: 'var(--clay-deep)' }}>proposed</b> block to a new time or
            day. Your existing calendar events are fixed. Every move is re-checked on the server.
          </div>
        </div>
        {weeks.length > 1 && (
          <div className="row" style={{ gap: 6 }}>
            <button
              className="btn btn-soft sm"
              type="button"
              disabled={safeWeek === 0}
              onClick={() => setWeekIdx(safeWeek - 1)}
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
              onClick={() => setWeekIdx(safeWeek + 1)}
            >
              →
            </button>
          </div>
        )}
        <button className="btn btn-primary lg" type="button" onClick={() => navigate('/approve')}>
          Continue to approval →
        </button>
      </div>

      {violation && (
        <div className="banner-error" style={{ margin: '12px clamp(16px,4vw,26px) 0' }}>
          That move was rejected by the server — {violation.text}
        </div>
      )}

      <div className="sched-scroll">
        <div className="sched-head">
          <div className="gutter" />
          {Array.from({ length: 7 }).map((_, i) => {
            const h = dayHeader(mondayMs, i)
            return (
              <div key={i} className="dcol">
                <div className="label" style={{ fontSize: 11 }}>
                  {h.dow}
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
                style={{
                  left: `${(b.dayIdx / 7) * 100}%`,
                  width: `${100 / 7}%`,
                  top: topPx(b.startMin),
                  height: heightPx(b.durMin),
                }}
              >
                <div className="bt">🔒 Busy</div>
                <div className="bm">
                  {fmtMinutes(b.startMin)}–{fmtMinutes(b.startMin + b.durMin)}
                </div>
              </div>
            ))}

            {weekBlocks.map((b) => {
              const pos = posOf(b)
              const dragging = drag?.taskId === b.taskId
              const bad = violation?.taskId === b.taskId
              return (
                <div
                  key={b.taskId}
                  className={`blk blk-proposed${dragging ? ' dragging' : ''}${bad ? ' bad' : ''}`}
                  onPointerDown={(e) => onDown(e, b)}
                  onPointerMove={onMove}
                  onPointerUp={(e) => void onUp(e)}
                  style={{
                    left: `${(pos.dayIdx / 7) * 100}%`,
                    width: `${100 / 7}%`,
                    top: topPx(pos.startMin),
                    height: heightPx(b.durMin),
                  }}
                >
                  <div className="bt">⠿ {b.title}</div>
                  <div className="bm">
                    {fmtMinutes(pos.startMin)}–{fmtMinutes(pos.startMin + b.durMin)}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      <div className="sched-legend">
        <span>
          <span className="sw" style={{ border: '1.5px dashed var(--clay)', background: 'var(--clay-tint)' }} />
          proposed · drag to adjust
        </span>
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
        <span className="spacer" />
        <span>{saving ? 'saving…' : 'snaps to 15 min · drag across days'}</span>
      </div>
    </div>
  )
}
