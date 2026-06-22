import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, api, errorMessage } from '../api/client'

// The generation surface. Triggers POST /api/propose and shows the deterministic
// pipeline while it runs. The pipeline animation is cosmetic — propose is one
// server call that runs the whole Strategist -> Planner -> Validation ->
// Scheduler pipeline (with bounded repair) and returns the outcome. A *workflow*
// failure comes back as a 200 with a typed reason_code (not an exception), which
// we render in the three-part shape — what went wrong, and how to recover. No
// dead ends: every failure offers a real next step.

const PIPELINE = [
  { t: 'Strategist', m: 'setting strategy & milestones' },
  { t: 'Planner', m: 'drafting weekly blocks' },
  { t: 'Validation', m: 'checking fit & constraints' },
  { t: 'Scheduler', m: 'placing around your calendar' },
]

// Static guidance per typed reason_code. The recovery affordance is the same
// shape for all: adjust your inputs (re-onboard) or try again.
const REASONS: Record<string, { title: string; what: string }> = {
  INSUFFICIENT_WEEKLY_CAPACITY: {
    title: 'Not enough weekly time',
    what: 'Your goal needs more hours than your weekly budget allows. Raise weekly hours or extend the timeline.',
  },
  USER_FIT_VIOLATED: {
    title: "Doesn't fit your constraints",
    what: "Some blocks couldn't fit inside your deep-work windows and hard limits. Relaxing a constraint usually clears it.",
  },
  REPAIR_LIMIT_EXCEEDED: {
    title: 'Constraints too tight',
    what: 'The planner exhausted its repair budget without a valid plan. Loosen a constraint or extend the timeline.',
  },
  COVERAGE_INCOMPLETE: {
    title: "Plan didn't cover everything",
    what: "Not every topic could be scheduled in the time available. Add hours, extend the timeline, or narrow the goal.",
  },
  NO_VALID_CONTIGUOUS_BLOCK: {
    title: 'No room to schedule',
    what: "There aren't enough free blocks in your windows and around your calendar. Add days/hours or widen your windows.",
  },
  DAILY_LOAD_EXCEEDED: {
    title: 'Daily limit too low',
    what: 'The per-day study cap leaves no room to place everything. Raise the daily cap or extend the timeline.',
  },
  LLM_REFUSAL: {
    title: "Couldn't draft a plan",
    what: 'The model declined to produce a plan for this input. Try again, or rephrase your goal.',
  },
}

function describe(code: string | null): { title: string; what: string } {
  if (code && REASONS[code]) return REASONS[code]
  return {
    title: "Couldn't build your plan",
    what: 'Something went wrong while generating. You can try again or adjust your setup.',
  }
}

type Phase = 'ready' | 'running' | 'failed'
type Failure = { code: string | null; message: string }

export function GenerationScreen() {
  const navigate = useNavigate()
  const [phase, setPhase] = useState<Phase>('ready')
  const [active, setActive] = useState(0)
  const [failure, setFailure] = useState<Failure | null>(null)

  // Cosmetic stage advance while the single propose request is in flight.
  useEffect(() => {
    if (phase !== 'running') return
    const id = setInterval(() => setActive((a) => Math.min(a + 1, PIPELINE.length - 1)), 700)
    return () => clearInterval(id)
  }, [phase])

  async function generate() {
    setFailure(null)
    setActive(0)
    setPhase('running')
    try {
      const result = await api.propose()
      if (result.reason_code) {
        setFailure({ code: result.reason_code, message: '' })
        setPhase('failed')
        return
      }
      navigate('/review') // success: a draft is awaiting approval (F-E)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return // redirected to login
      if (err instanceof ApiError && err.status === 409) {
        navigate('/onboarding') // not set up yet
        return
      }
      setFailure({ code: null, message: errorMessage(err) })
      setPhase('failed')
    }
  }

  if (phase === 'failed' && failure) {
    const { title, what } = describe(failure.code)
    return (
      <div className="gen-wrap">
        <div className="gen-card err-card">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <span className="err-code">{failure.code ?? 'GENERATION_FAILED'}</span>
            <span className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>
              recoverable
            </span>
          </div>
          <h2 className="t-h3" style={{ marginTop: 12 }}>
            {title}
          </h2>
          <p style={{ fontSize: 13.5, color: 'var(--ink-soft)', marginTop: 6, lineHeight: 1.5 }}>
            {failure.message || what}
          </p>
          <div className="row" style={{ gap: 9, marginTop: 16 }}>
            <button className="btn btn-primary" type="button" onClick={() => void generate()}>
              Try again
            </button>
            <button className="btn btn-soft" type="button" onClick={() => navigate('/onboarding')}>
              Adjust your setup
            </button>
          </div>
        </div>
      </div>
    )
  }

  const running = phase === 'running'
  return (
    <div className="gen-wrap">
      <div className="card raise gen-card">
        <span className="label">Building your plan</span>
        <h2 className="t-h2" style={{ marginTop: 10 }}>
          {running ? 'Drafting your plan' : 'Ready to build your plan'}
        </h2>
        <p className="muted" style={{ fontSize: 13.5, marginTop: 4 }}>
          A multi-stage deterministic pipeline with bounded repair. Nothing is written to your
          calendar — you review and approve the draft next.
        </p>

        {running && (
          <div style={{ marginTop: 18 }}>
            {PIPELINE.map((stage, i) => {
              const status = i < active ? 'done' : i === active ? 'active' : 'pending'
              return (
                <div key={stage.t} className={`pl-step ${status}`}>
                  <span className="pl-ico">{status === 'done' ? '✓' : i + 1}</span>
                  <div style={{ flex: 1 }}>
                    <div className="pl-t">{stage.t}</div>
                    <div className="pl-m">{stage.m}</div>
                  </div>
                  {status === 'active' && <span className="spin" />}
                </div>
              )
            })}
          </div>
        )}

        <div className="row" style={{ marginTop: 20 }}>
          <span className="spacer" />
          <button className="btn btn-primary lg" type="button" disabled={running} onClick={() => void generate()}>
            {running ? 'Working…' : 'Build my plan →'}
          </button>
        </div>
      </div>
    </div>
  )
}
