import { useEffect, useState } from 'react'

import { ApiError, api, errorMessage } from '../api/client'
import type { AccountabilityResult } from '../api/types'

// Accountability: a read-only projection of completion telemetry + weekly
// check-in against the user's accountability contract. Empty-state FIRST
// (backend D-5 / axiom 21): the snapshot is null until a motivation profile
// exists, and onboarding deliberately omits that capture — so the page
// distinguishes "not set up" (no motivation profile) from "no active plan yet".
// Every number and the chosen intervention are computed deterministically by the
// engine; nothing is written here.

function pct(value: number): string {
  return `${Math.round(value * 100)}%`
}

export function AccountabilityScreen() {
  const [result, setResult] = useState<AccountabilityResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api
      .accountability()
      .then((r) => active && (setResult(r), setLoading(false)))
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

  if (loading) return <div className="screen-center muted">Loading accountability…</div>
  if (error) return <div className="screen-center">Couldn’t load accountability — {error}</div>

  const data = result
  const state = data?.state ?? null

  // Empty-state: no snapshot yet. Two distinct reasons, two distinct messages.
  if (!state) {
    const notSetUp = !data?.has_motivation_profile
    return (
      <section className="read-wrap">
        <span className="label">Accountability</span>
        <h1 className="t-h1" style={{ marginTop: 8 }}>
          {notSetUp ? 'Accountability isn’t set up yet' : 'No active plan yet'}
        </h1>
        <div className="card soft" style={{ marginTop: 16, padding: '18px 20px', maxWidth: 560 }}>
          <p className="muted" style={{ lineHeight: 1.55 }}>
            {notSetUp ? (
              <>
                It turns your completion history into a deterministic “are you on track?” read, but it
                needs a <b>motivation profile</b> first — capturing that in the UI is a follow-up, so
                there’s nothing to show here yet.
              </>
            ) : (
              <>
                Propose and approve a schedule, check off a few tasks on Today, and your accountability
                read shows up here.
              </>
            )}
          </p>
        </div>
      </section>
    )
  }

  const decision = data?.decision ?? null
  return (
    <section className="read-wrap">
      <span className="label">Accountability</span>
      <h1 className="t-h1" style={{ marginTop: 8 }}>
        Are you on track?
      </h1>
      <p className="muted" style={{ marginTop: 6, maxWidth: 600 }}>
        A read-only projection of your completion telemetry and weekly check-in. The numbers and the
        chosen intervention are computed deterministically — never written here.
      </p>

      <div className="card" style={{ marginTop: 18, padding: '6px 18px' }}>
        <div className="cfg-row">
          <div className="cl">Status</div>
          <span className="tag ok">{state.current_status}</span>
        </div>
        <div className="cfg-row">
          <div className="cl">Completion · 7d / 14d</div>
          <span style={{ fontWeight: 600 }}>
            {pct(state.completion_rate_7d)} · {pct(state.completion_rate_14d)}
          </span>
        </div>
        <div className="cfg-row">
          <div className="cl">Missed (7d) · reschedules (7d)</div>
          <span style={{ fontWeight: 600 }}>
            {state.missed_tasks_7d} · {state.reschedule_count_7d}
          </span>
        </div>
        <div className="cfg-row">
          <div className="cl">Behind schedule</div>
          <span style={{ fontWeight: 600 }}>{state.behind_schedule_percent}%</span>
        </div>
        <div className="cfg-row">
          <div className="cl">Weekly check-in</div>
          <span style={{ fontWeight: 600 }}>{data?.checkin_status ?? '—'}</span>
        </div>
        <div className="cfg-row" style={{ borderBottom: 'none' }}>
          <div className="cl">Sponsor report allowed</div>
          <span style={{ fontWeight: 600 }}>{state.sponsor_report_allowed ? 'yes' : 'no'}</span>
        </div>
      </div>

      {decision && (
        <div className="card soft" style={{ marginTop: 14, padding: '14px 18px', maxWidth: 600 }}>
          <div className="label" style={{ marginBottom: 8 }}>
            Recommended intervention
          </div>
          <div className="cfg-row">
            <div className="cl">Private lane</div>
            <span style={{ fontWeight: 600 }}>
              {decision.action ?? 'none'}
              {decision.reason_code ? ` (${decision.reason_code})` : ''}
            </span>
          </div>
          <div className="cfg-row" style={{ borderBottom: 'none' }}>
            <div className="cl">Sponsor lane</div>
            <span style={{ fontWeight: 600 }}>{decision.sponsor_action ?? 'none'}</span>
          </div>
        </div>
      )}
    </section>
  )
}
