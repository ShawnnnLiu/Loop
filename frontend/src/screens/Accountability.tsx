import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, api, errorMessage } from '../api/client'
import type { AccountabilityResult, RecommitChoice } from '../api/types'
import {
  RECOMMIT_CHOICES,
  recommitOutcomeMessage,
  weeklyCheckinOutcomeMessage,
} from '../lib/accountability'

// Accountability: the projection of completion telemetry + weekly check-in
// against the user's accountability contract, plus the two answerable asks
// (B3): the weekly check-in card when it's due, and the recommitment card
// when a nudge asked and hasn't been answered. Numbers and interventions are
// computed deterministically by the engine; the only writes here are the
// user's own typed answers (a check-in event / a recommitment choice) —
// never a calendar write, never a silent plan change.

function pct(value: number): string {
  return `${Math.round(value * 100)}%`
}

export function AccountabilityScreen() {
  const navigate = useNavigate()
  const [result, setResult] = useState<AccountabilityResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [blockers, setBlockers] = useState('')
  const [busy, setBusy] = useState<'checkin' | RecommitChoice | null>(null)
  const [notice, setNotice] = useState<{ text: string; reviewCta: boolean } | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  function load(initial = false) {
    if (initial) setLoading(true)
    api
      .accountability()
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

  async function submitCheckin() {
    setBusy('checkin')
    setActionError(null)
    try {
      const outcome = await api.weeklyCheckin(blockers)
      setNotice({ text: weeklyCheckinOutcomeMessage(outcome), reviewCta: false })
      setBlockers('')
      load()
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) setActionError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function answerRecommit(choice: RecommitChoice) {
    setBusy(choice)
    setActionError(null)
    try {
      const outcome = await api.recommit(choice)
      setNotice({ text: recommitOutcomeMessage(outcome), reviewCta: outcome.replan_required })
      load()
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) setActionError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

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
        Your completion telemetry and weekly check-in against your accountability contract. The
        numbers and interventions are computed deterministically — the only thing recorded here is
        what you answer below.
      </p>

      {notice && (
        <div
          className="card"
          style={{ marginTop: 14, padding: '12px 16px', borderColor: 'var(--sage)', background: 'var(--sage-soft)', maxWidth: 600 }}
        >
          <span style={{ fontSize: 13.5 }}>{notice.text}</span>
          {notice.reviewCta && (
            <button className="btn btn-primary sm" type="button" style={{ marginLeft: 10 }} onClick={() => navigate('/review')}>
              Review the updated plan →
            </button>
          )}
        </div>
      )}
      {actionError && (
        <div className="banner-error" style={{ marginTop: 14, maxWidth: 600 }}>
          That didn’t go through — {actionError}
        </div>
      )}

      {data?.checkin_due && (
        <div className="card" style={{ marginTop: 14, padding: '16px 18px', maxWidth: 600 }}>
          <div className="label" style={{ marginBottom: 6 }}>
            Weekly check-in
          </div>
          <div style={{ fontWeight: 600, fontSize: 15 }}>How did this week go?</div>
          <p className="muted" style={{ fontSize: 13, marginTop: 4, lineHeight: 1.5 }}>
            Loop counts the week’s scheduled and completed tasks for you — add anything that got in
            the way if you like.
          </p>
          <textarea
            className="input"
            rows={2}
            maxLength={2000}
            placeholder="Anything that got in the way? (optional)"
            value={blockers}
            onChange={(e) => setBlockers(e.target.value)}
            style={{ width: '100%', marginTop: 10, resize: 'vertical' }}
          />
          <button
            className="btn btn-primary sm"
            type="button"
            style={{ marginTop: 10 }}
            disabled={busy !== null}
            onClick={() => void submitCheckin()}
          >
            {busy === 'checkin' ? 'Recording…' : 'Record my week'}
          </button>
        </div>
      )}

      {data?.open_recommitment_request_id && (
        <div className="card" style={{ marginTop: 14, padding: '16px 18px', maxWidth: 600 }}>
          <div className="label" style={{ marginBottom: 6 }}>
            Recommitment
          </div>
          <div style={{ fontWeight: 600, fontSize: 15 }}>
            Your pace slipped recently — can you recommit to this plan?
          </div>
          <p className="muted" style={{ fontSize: 13, marginTop: 4, lineHeight: 1.5 }}>
            Pick what’s true for you. Plan changes come back as a draft for your review — nothing
            changes silently.
          </p>
          <div className="col" style={{ gap: 8, marginTop: 12 }}>
            {RECOMMIT_CHOICES.map((opt) => (
              <button
                key={opt.choice}
                type="button"
                className="card"
                disabled={busy !== null}
                style={{ padding: '10px 14px', textAlign: 'left', cursor: 'pointer' }}
                onClick={() => void answerRecommit(opt.choice)}
              >
                <span style={{ fontWeight: 600, fontSize: 13.5 }}>
                  {busy === opt.choice ? 'Recording… ' : opt.title}
                </span>
                <span className="muted" style={{ fontSize: 12.5, marginLeft: 8 }}>
                  {opt.description}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

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
