import { Fragment, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import type { UserProfile } from '../api/types'
import { fmtMinutes } from '../lib/datetime'
import type { ReviewMode } from '../lib/review'
import {
  type MilestoneGroup,
  type PlanDay,
  type PlanItem,
  railAction,
  railCounts,
  railMeta,
  railStatus,
  targetLine,
} from '../lib/weekplan'

// The design-reference week plan (design/calendar.jsx), rendered from real
// data: milestone bar (per-category check-in progress + the profile's goal
// and target), week-nav row, a 7-column stacked-block board (no time axis),
// and an agenda rail for the selected day. Purely presentational — every
// state/copy decision lives in lib/weekplan.ts, and the parent screen owns
// the data, mode, and rolling window (it remounts this component per window
// via key={windowMs}, which also resets the day selection).
//
// Deliberate deltas from the mock, because the backend owns the truth:
// approval is whole-draft, so the rail's CTA goes to /approve instead of
// per-item Accept; per-block editing is the grid's drag, so proposed items
// offer "Adjust →" (switch to grid); check-ins live on Today; no WHY cards
// (no per-task rationale data), no keyboard shortcuts (those actions don't
// exist), no actual-minutes meta (no telemetry surfaced here).

export interface WeekRange {
  label: string
  canPrev: boolean
  canNext: boolean
  atToday: boolean
}

interface WeekPlanViewProps {
  days: PlanDay[]
  mode: ReviewMode
  profile: UserProfile | null
  milestones: MilestoneGroup[]
  range: WeekRange
  onPrev: () => void
  onNext: () => void
  onToday: () => void
  onSwitchToGrid: () => void
}

export function WeekPlanView({
  days,
  mode,
  profile,
  milestones,
  range,
  onPrev,
  onNext,
  onToday,
  onSwitchToGrid,
}: WeekPlanViewProps) {
  const navigate = useNavigate()
  // Default to today's column when this window contains it, else the first.
  const [selIdx, setSelIdx] = useState(() => Math.max(0, days.findIndex((d) => d.isToday)))
  const sel = days[selIdx] ?? days[0]
  const anyDeleted = days.some((d) => d.items.some((item) => item.state === 'deleted'))
  const status = railStatus(mode)
  const target = targetLine(profile)

  return (
    <>
      {(profile !== null || milestones.length > 0) && (
        <div className="wp-ms-bar">
          <div>
            <div className="label" style={{ marginBottom: milestones.length > 0 ? 9 : 0 }}>
              Milestones{profile ? ` · ${profile.goal}` : ''}
            </div>
            {milestones.length > 0 && (
              <div className="wp-ms-track">
                {milestones.map((m, i) => (
                  <Fragment key={m.label}>
                    <span className={`wp-ms ${m.state}`}>
                      <span className="tick">
                        {m.state === 'done' ? '✓' : m.state === 'active' ? '◔' : ''}
                      </span>
                      {m.label}
                      {m.state === 'done' ? '' : ` · ${m.done}/${m.total}`}
                    </span>
                    {i < milestones.length - 1 && <span className="wp-ms-link" />}
                  </Fragment>
                ))}
              </div>
            )}
          </div>
          <span className="spacer" />
          {target && (
            <div style={{ textAlign: 'right' }}>
              <div className="label">Target</div>
              <div className="t-h4" style={{ marginTop: 4 }}>
                {target}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="wp-body">
        <div className="wp-board">
          <div className="wp-nav">
            <div className="row" style={{ gap: 10, alignItems: 'center' }}>
              <button
                className="wp-nav-btn"
                type="button"
                aria-label="Previous week"
                disabled={!range.canPrev}
                onClick={onPrev}
              >
                ←
              </button>
              <h2 className="t-h2">{range.label}</h2>
              <button
                className="wp-nav-btn"
                type="button"
                aria-label="Next week"
                disabled={!range.canNext}
                onClick={onNext}
              >
                →
              </button>
              {!range.atToday && (
                <button className="btn btn-soft sm" type="button" onClick={onToday}>
                  Today
                </button>
              )}
            </div>
            <span className="muted" style={{ fontSize: 12.5 }}>
              click a day to expand →
            </span>
          </div>

          <div className="wp-grid">
            {days.map((d) => (
              <div
                key={d.dayMs}
                role="button"
                tabIndex={0}
                aria-pressed={d.dayIdx === selIdx}
                className={`wp-day${
                  d.dayIdx === selIdx ? ' sel' : d.isToday ? ' today' : ''
                }${d.meta === 'rest' ? ' rest' : ''}`}
                onClick={() => setSelIdx(d.dayIdx)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' || event.key === ' ') {
                    event.preventDefault()
                    setSelIdx(d.dayIdx)
                  }
                }}
              >
                <div className="wp-day-top">
                  <span className="wp-dow">{d.dow}</span>
                  <span className="wp-num">{d.num}</span>
                </div>
                <span className="wp-day-meta">{d.meta}</span>
                <div className="wp-day-div" />
                <div className="wp-col">
                  {d.meta === 'rest' ? (
                    <div className="wp-rest-note">Rest day</div>
                  ) : (
                    d.items.map((item) => (
                      <div key={item.key} className={`wp-blk ${item.state}`}>
                        <div className="wp-bt">
                          {item.state === 'locked' ? '🔒 ' : ''}
                          {fmtMinutes(item.startMin)}
                        </div>
                        <div className="wp-bn">{item.title}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="wp-board-div" />
          <div className="wp-legend">
            {mode === 'editable' ? (
              <span className="lg">
                <span className="wp-sw proposed" />
                proposed
              </span>
            ) : mode === 'written' || mode === 'replan' ? (
              <>
                <span className="lg">
                  <span className="wp-sw accepted" />
                  on your calendar
                </span>
                <span className="lg">
                  <span className="wp-sw done" />
                  logged
                </span>
              </>
            ) : (
              <span className="lg">
                <span className="wp-sw unconfirmed" />
                not confirmed
              </span>
            )}
            <span className="lg">
              <span className="wp-sw locked" />
              imported · fixed
            </span>
            {anyDeleted && (
              <span className="lg">
                <span className="wp-sw deleted" />✕ deleted from your calendar
              </span>
            )}
          </div>
        </div>

        <div className="wp-rail">
          <div className="wp-rail-top">
            <div>
              <div className="label">{sel.isToday ? 'Selected · today' : 'Selected'}</div>
              <h2 className="t-h1" style={{ marginTop: 4 }}>
                {sel.dow}, {sel.label}
              </h2>
              <div className="muted" style={{ fontSize: 13, marginTop: 3 }}>
                {railCounts(sel, mode)} ·{' '}
                <span className={`wp-status ${status.tone}`}>{status.label}</span>
              </div>
            </div>
            {mode === 'editable' && (
              <button
                className="btn btn-primary sm"
                type="button"
                onClick={() => navigate('/approve')}
              >
                Approve this week →
              </button>
            )}
          </div>
          <div className="wp-rail-list">
            {sel.items.length === 0 ? (
              <div className="muted" style={{ fontStyle: 'italic', fontSize: 13 }}>
                Nothing planned — a rest day.
              </div>
            ) : (
              sel.items.map((item) => (
                <RailItem key={item.key} item={item} onSwitchToGrid={onSwitchToGrid} />
              ))
            )}
          </div>
        </div>
      </div>
    </>
  )
}

function RailItem({ item, onSwitchToGrid }: { item: PlanItem; onSwitchToGrid: () => void }) {
  const navigate = useNavigate()
  const action = railAction(item)
  return (
    <div className={`wp-rail-item ${item.state}`}>
      <div className="wp-rail-row">
        <div className="wp-rail-main">
          <div className="wp-rail-time">
            {fmtMinutes(item.startMin)} – {fmtMinutes(item.endMin)}
            {item.state === 'locked' ? ' · 🔒' : ''}
          </div>
          <div className="wp-rail-title">{item.title}</div>
          <div className="wp-rail-meta">{railMeta(item)}</div>
        </div>
        <div className="row" style={{ gap: 7, flexShrink: 0 }}>
          {action.kind === 'chip' ? (
            <span className={item.state === 'done' ? 'tag ok' : 'tag'}>{action.label}</span>
          ) : (
            <button
              className="btn btn-soft sm"
              type="button"
              onClick={action.kind === 'link' ? () => navigate(action.to) : onSwitchToGrid}
            >
              {action.label}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
