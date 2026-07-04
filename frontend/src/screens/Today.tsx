import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, api, errorMessage } from '../api/client'
import type { TodayResult, TodayTask } from '../api/types'
import { fmtClock, fmtWhen } from '../lib/datetime'

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
  const [rowError, setRowError] = useState<{ taskId: string; text: string } | null>(null)

  function load(initial = false) {
    if (initial) setLoading(true)
    api
      .today()
      .then((r) => {
        setResult(r)
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

  async function checkin(task: TodayTask, outcome: 'complete' | 'missed') {
    setPending(task.task_id)
    setRowError(null)
    try {
      await api.checkin(task.task_id, outcome)
    } catch (err) {
      setPending(null)
      // A 401 has already redirected to login — don't fire a doomed reload.
      if (err instanceof ApiError && err.status === 401) return
      // 409 = the server refused (not due / already reported / not in plan).
      setRowError({ taskId: task.task_id, text: errorMessage(err) })
      load() // refresh so the row reflects the server's current truth
      return
    }
    setPending(null)
    load() // re-render from the server's truth, never an optimistic guess
  }

  if (loading) return <div className="screen-center muted">Loading today…</div>
  if (error) return <div className="screen-center">Couldn’t load Today — {error}</div>

  const tasks = result?.tasks ?? []
  if (tasks.length === 0) {
    return (
      <div className="screen-center col" style={{ gap: 12, textAlign: 'center', maxWidth: 460 }}>
        <h2 className="t-h2">No active plan yet</h2>
        <p className="muted">
          Propose and approve a schedule, then your scheduled tasks show up here to check off. Your
          check-ins feed drift and accountability.
        </p>
        <button className="btn btn-primary" type="button" onClick={() => navigate('/plan')}>
          Build a plan →
        </button>
      </div>
    )
  }

  return (
    <section className="read-wrap">
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
                    onClick={() => void checkin(task, 'complete')}
                  >
                    Complete
                  </button>
                </>
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
