import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, api, errorMessage } from '../api/client'
import type { TodayResult, TodayTask } from '../api/types'
import { CONFIDENCE_OPTIONS, type SolveConfidence } from '../lib/checkin'
import { fmtClock, fmtWhen } from '../lib/datetime'
import { attentionChip } from '../lib/review'

// Today / check-in: the telemetry feedback loop. Renders the active plan's
// scheduled tasks; a block becomes "due" once its time has passed, at which
// point Complete / Missed POST a single guarded check-in (/api/checkin). This is
// NOT a calendar write — it is completion telemetry the engine calibrates on.
// The server owns the guard (membership / due / idempotency), so a double-click
// can never double-count; we re-render from the server after every check-in.

export function TodayScreen() {
  const navigate = useNavigate()
  const [result, setResult] = useState<TodayResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState<string | null>(null)
  // MM-B: the task whose Complete tap has revealed the confidence triage but not
  // yet fired the POST. Kept out of `load()` so a refresh dismisses a stale reveal.
  const [confirming, setConfirming] = useState<string | null>(null)
  const [rowError, setRowError] = useState<{ taskId: string; text: string } | null>(null)
  const [runState, setRunState] = useState<string | null>(null)

  function load(initial = false) {
    if (initial) setLoading(true)
    // Status rides along so a parked run (replan required, failed write,
    // stopped run) is visible where the user actually lives — not only on
    // the Week screen they might not visit.
    Promise.all([api.today(), api.status()])
      .then(([r, s]) => {
        setResult(r)
        setRunState(s.state)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) return
        setError(errorMessage(err))
        setLoading(false)
      })
  }

  useEffect(() => {
    load(true)
  }, [])

  async function checkin(
    task: TodayTask,
    outcome: 'complete' | 'missed',
    confidence?: SolveConfidence,
  ) {
    setPending(task.task_id)
    setRowError(null)
    try {
      await api.checkin(task.task_id, outcome, confidence)
    } catch (err) {
      setPending(null)
      // A 401 has already redirected to login — don't fire a doomed reload.
      if (err instanceof ApiError && err.status === 401) return
      // 409 = the server refused (not due / already reported / not in plan).
      setRowError({ taskId: task.task_id, text: errorMessage(err) })
      setConfirming(null)
      load() // refresh so the row reflects the server's current truth
      return
    }
    setPending(null)
    setConfirming(null)
    load() // re-render from the server's truth, never an optimistic guess
  }

  if (loading) return <div className="screen-center muted">Loading today…</div>
  if (error) return <div className="screen-center">Couldn’t load Today — {error}</div>

  const tasks = result?.tasks ?? []
  const chip = attentionChip(runState)
  if (tasks.length === 0) {
    // A parked run must stay visible even with no active plan (e.g. a failed
    // calendar write) — otherwise "No active plan yet" hides the problem.
    return (
      <div className="screen-center col" style={{ gap: 12, textAlign: 'center', maxWidth: 460 }}>
        {chip ? (
          <>
            <span className="tag danger" style={{ alignSelf: 'center' }}>
              needs attention
            </span>
            <h2 className="t-h2">{chip.label}</h2>
            <button className="btn btn-primary" type="button" onClick={() => navigate(chip.to)}>
              Take a look →
            </button>
          </>
        ) : (
          <>
            <h2 className="t-h2">No active plan yet</h2>
            <p className="muted">
              Propose and approve a schedule, then your scheduled tasks show up here to check off.
              Your check-ins feed drift and accountability.
            </p>
            <button className="btn btn-primary" type="button" onClick={() => navigate('/plan')}>
              Build a plan →
            </button>
          </>
        )}
      </div>
    )
  }

  return (
    <section className="read-wrap">
      {chip && (
        <button
          type="button"
          className="card"
          onClick={() => navigate(chip.to)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 10,
            width: '100%',
            textAlign: 'left',
            cursor: 'pointer',
            padding: '12px 16px',
            marginBottom: 16,
            borderColor: 'var(--clay-deep)',
          }}
        >
          <span className="tag danger">needs attention</span>
          <span style={{ fontSize: 13.5, fontWeight: 500 }}>{chip.label}</span>
          <span className="muted" style={{ marginLeft: 'auto', fontSize: 13 }}>
            →
          </span>
        </button>
      )}
      <span className="label">Your schedule</span>
      <h1 className="t-h1" style={{ marginTop: 8 }}>
        Today &amp; ahead
      </h1>
      <p className="muted" style={{ marginTop: 6, maxWidth: 560 }}>
        Mark each task complete or missed once its time has passed. Check-ins are completion
        telemetry — they’re never written to your calendar.
      </p>

      <div className="card" style={{ marginTop: 18, padding: '4px 0' }}>
        {tasks.map((task, i) => (
          <div
            key={task.task_id}
            className="today-row"
            style={{ borderBottom: i < tasks.length - 1 ? '1px solid var(--line)' : 'none' }}
          >
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 14.5 }}>{task.title}</div>
              <div className="mono" style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>
                {fmtWhen(task.start)}–{fmtClock(task.end)} · {task.category} · {task.required_focus_level}
              </div>
              {rowError?.taskId === task.task_id && (
                <div style={{ fontSize: 12.5, color: '#a33', marginTop: 4 }}>{rowError.text}</div>
              )}
            </div>
            <div className="row" style={{ gap: 8, flex: 'none' }}>
              {task.deleted && (
                <span
                  className="tag danger"
                  title="You deleted this event from your Google Calendar — the task is still in your plan. Complete it or build a new plan."
                >
                  ✕ deleted from calendar
                </span>
              )}
              {task.reported ? (
                <span className="tag ok">✓ reported</span>
              ) : task.due ? (
                confirming === task.task_id ? (
                  // MM-B reveal: Complete tapped, no POST yet. Any chip carries its
                  // solve_confidence; Skip completes with no signal (neutral).
                  <div className="row" style={{ gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <span className="muted" style={{ fontSize: 12.5 }}>
                      How did it go?
                    </span>
                    {CONFIDENCE_OPTIONS.map((opt) => (
                      <button
                        key={opt.value}
                        className="chip sm"
                        type="button"
                        disabled={pending === task.task_id}
                        onClick={() => void checkin(task, 'complete', opt.value)}
                      >
                        {opt.label}
                      </button>
                    ))}
                    <button
                      className="btn btn-quiet sm"
                      type="button"
                      disabled={pending === task.task_id}
                      onClick={() => void checkin(task, 'complete')}
                    >
                      Skip →
                    </button>
                  </div>
                ) : (
                  <>
                    <button
                      className="btn btn-soft sm"
                      type="button"
                      disabled={pending === task.task_id}
                      onClick={() => void checkin(task, 'missed')}
                    >
                      Missed
                    </button>
                    <button
                      className="btn btn-primary sm"
                      type="button"
                      disabled={pending === task.task_id}
                      onClick={() => setConfirming(task.task_id)}
                    >
                      Complete
                    </button>
                  </>
                )
              ) : (
                <span className="tag">upcoming</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
