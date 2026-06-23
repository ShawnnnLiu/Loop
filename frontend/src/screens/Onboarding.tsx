import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, api, errorMessage } from '../api/client'
import type { ExperienceLevel, MeResult, OnboardPayload, Weekday } from '../api/types'

// The deterministic onboarding wizard. Every field maps straight onto the
// UserProfile contract, which is the single validation oracle — the wizard only
// shapes input (CSV -> list, day toggles -> windows). The one AI-adjacent field,
// the résumé, is captured as RAW TEXT only: no extract/review card (backend D-3).
// Google is already connected (it is the entry gate), so the final step confirms
// the connection rather than triggering OAuth.

const DAYS: Weekday[] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const WEEKDAYS: Weekday[] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
const LEVELS: ExperienceLevel[] = ['beginner', 'intermediate', 'advanced']
const STEP_LABELS = ['Goal', 'Time & constraints', 'Skills', 'Résumé & targets', 'Connect']

interface FormState {
  goal: string
  target_role: string
  experience_level: ExperienceLevel
  timeline_weeks: number
  weekly_hours: number
  preferred_session_length_min: number
  max_session_length_min: number
  dwwDays: Weekday[]
  dwwStart: string
  dwwEnd: string
  timezone: string
  no_events_before: string
  no_events_after: string
  allow_weekends: boolean
  max_daily_study_min: number
  min_break_between_deep_blocks_min: number
  prefer_evening_sessions: boolean
  prefer_weekend_long_blocks: boolean
  avoid_back_to_back_deep_work: boolean
  known_strengths: string
  known_weaknesses: string
  resume_text: string
  target_companies: string
  target_level: string
}

function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

function initialForm(me: MeResult): FormState {
  const profile = me.profile
  const windows = profile?.deep_work_windows ?? []
  return {
    goal: profile?.goal ?? '',
    target_role: profile?.target_role ?? '',
    experience_level: profile?.experience_level ?? 'intermediate',
    timeline_weeks: profile?.timeline_weeks ?? 10,
    weekly_hours: profile?.weekly_hours ?? 8,
    preferred_session_length_min: profile?.preferred_session_length_min ?? 60,
    max_session_length_min: profile?.max_session_length_min ?? 180,
    // New users start with weekday deep-work windows pre-selected so a
    // click-through onboard has real windows for the scheduler; an existing
    // profile keeps whatever days it saved (even none).
    dwwDays: profile ? windows.map((w) => w.day) : WEEKDAYS,
    dwwStart: windows[0]?.start ?? '18:00',
    dwwEnd: windows[0]?.end ?? '21:00',
    // Prefer a real saved zone; "UTC" is the server's fallback default (not a
    // zone a user picks), so treat it as unset and re-detect from the browser —
    // this runs for returning users too, who previously kept the UTC default.
    timezone: me.timezone && me.timezone !== 'UTC' ? me.timezone : browserTimezone(),
    no_events_before: profile?.hard_constraints.no_events_before ?? '08:00',
    no_events_after: profile?.hard_constraints.no_events_after ?? '22:30',
    allow_weekends: profile?.hard_constraints.allow_weekends ?? true,
    max_daily_study_min: profile?.hard_constraints.max_daily_study_min ?? 180,
    min_break_between_deep_blocks_min:
      profile?.hard_constraints.min_break_between_deep_blocks_min ?? 30,
    prefer_evening_sessions: profile?.preferences.prefer_evening_sessions ?? false,
    prefer_weekend_long_blocks: profile?.preferences.prefer_weekend_long_blocks ?? false,
    avoid_back_to_back_deep_work: profile?.preferences.avoid_back_to_back_deep_work ?? false,
    known_strengths: (profile?.known_strengths ?? []).join(', '),
    known_weaknesses: (profile?.known_weaknesses ?? []).join(', '),
    resume_text: profile?.resume_text ?? '',
    target_companies: (profile?.target_companies ?? []).join(', '),
    target_level: profile?.target_level ?? '',
  }
}

function csv(value: string): string[] {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function buildPayload(form: FormState, timezone: string): OnboardPayload {
  const now = new Date().toISOString()
  const windows =
    form.dwwDays.length > 0 && form.dwwStart && form.dwwEnd
      ? form.dwwDays.map((day) => ({ day, start: form.dwwStart, end: form.dwwEnd }))
      : []
  return {
    timezone,
    user_profile: {
      user_id: 'pending', // server overrides with the session user
      profile_version: 'profile_001',
      goal: form.goal.trim(),
      target_role: form.target_role.trim(),
      target_companies: csv(form.target_companies),
      target_level: form.target_level.trim() || null,
      timeline_weeks: form.timeline_weeks,
      weekly_hours: form.weekly_hours,
      experience_level: form.experience_level,
      known_strengths: csv(form.known_strengths),
      known_weaknesses: csv(form.known_weaknesses),
      preferred_session_length_min: form.preferred_session_length_min,
      max_session_length_min: form.max_session_length_min,
      deep_work_windows: windows,
      hard_constraints: {
        no_events_before: form.no_events_before,
        no_events_after: form.no_events_after,
        allow_weekends: form.allow_weekends,
        max_daily_study_min: form.max_daily_study_min,
        min_break_between_deep_blocks_min: form.min_break_between_deep_blocks_min,
      },
      preferences: {
        prefer_evening_sessions: form.prefer_evening_sessions,
        prefer_weekend_long_blocks: form.prefer_weekend_long_blocks,
        avoid_back_to_back_deep_work: form.avoid_back_to_back_deep_work,
      },
      resume_text: form.resume_text.trim() || null,
      created_at: now,
      updated_at: now,
    },
  }
}

// ——— small controls ———

function Stepper({
  value,
  onChange,
  min,
  max,
  step = 1,
}: {
  value: number
  onChange: (next: number) => void
  min: number
  max: number
  step?: number
}) {
  const clamp = (n: number) => Math.max(min, Math.min(max, n))
  return (
    <div className="stepper">
      <button type="button" aria-label="decrease" disabled={value <= min} onClick={() => onChange(clamp(value - step))}>
        −
      </button>
      <span className="val">{value}</span>
      <button type="button" aria-label="increase" disabled={value >= max} onClick={() => onChange(clamp(value + step))}>
        +
      </button>
    </div>
  )
}

function Switch({ on, onChange }: { on: boolean; onChange: (next: boolean) => void }) {
  return (
    <button type="button" className={`switch${on ? ' on' : ''}`} aria-pressed={on} onClick={() => onChange(!on)}>
      <span className="knob" />
    </button>
  )
}

function ConfigRow({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div className="cfg-row">
      <div>
        <div className="cl">{label}</div>
        {hint && <div className="cs">{hint}</div>}
      </div>
      {children}
    </div>
  )
}

export function OnboardingScreen({ me }: { me: MeResult }) {
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [form, setForm] = useState<FormState>(() => initialForm(me))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }))

  const toggleDay = (day: Weekday) =>
    setForm((prev) => ({
      ...prev,
      dwwDays: prev.dwwDays.includes(day)
        ? prev.dwwDays.filter((d) => d !== day)
        : [...prev.dwwDays, day],
    }))

  // Client-side guards mirror the contract's hard rules so most submits pass;
  // the server stays the oracle and any remaining rejection surfaces below.
  const goalReady = form.goal.trim().length > 0 && form.target_role.trim().length > 0
  const sessionsValid = form.max_session_length_min >= form.preferred_session_length_min
  const canAdvance = step !== 0 || goalReady
  const isLast = step === STEP_LABELS.length - 1

  async function submit() {
    setSubmitting(true)
    setError(null)
    const timezone = form.timezone.trim() || browserTimezone() || 'UTC'
    try {
      await api.onboard(buildPayload(form, timezone))
      navigate('/plan') // next: generate the plan (F-D)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return // redirected to login
      setError(errorMessage(err))
      setSubmitting(false)
    }
  }

  return (
    <div className="wizard">
      <div className="wizard-progress">
        {STEP_LABELS.map((label, i) => (
          <div key={label} className={`seg${i <= step ? ' fill' : ''}`} />
        ))}
      </div>
      <div className="wizard-step-label">
        Step {step + 1} / {STEP_LABELS.length} · {STEP_LABELS[step]}
      </div>

      {step === 0 && (
        <section>
          <h1 className="t-h1" style={{ marginTop: 14 }}>
            What are you aiming for?
          </h1>
          <p className="muted" style={{ marginTop: 4 }}>
            This shapes every milestone the planner builds. Plain questions — no AI here.
          </p>
          <div className="field">
            <label className="field-label" htmlFor="goal">
              Your goal — in your words
            </label>
            <textarea
              id="goal"
              className="textarea"
              value={form.goal}
              onChange={(e) => set('goal', e.target.value)}
              placeholder="e.g. Get interview-ready for backend roles in 12 weeks, focusing on system design."
            />
          </div>
          <div className="grid-2">
            <div className="field">
              <label className="field-label" htmlFor="role">
                Target role
              </label>
              <input
                id="role"
                className="input"
                value={form.target_role}
                onChange={(e) => set('target_role', e.target.value)}
                placeholder="Backend SWE"
              />
            </div>
            <div className="field">
              <span className="field-label">Experience level</span>
              <div className="chip-row">
                {LEVELS.map((level) => (
                  <button
                    key={level}
                    type="button"
                    className={`chip${form.experience_level === level ? ' on' : ''}`}
                    onClick={() => set('experience_level', level)}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {step === 1 && (
        <section>
          <h1 className="t-h1" style={{ marginTop: 14 }}>
            Time budget &amp; constraints
          </h1>
          <p className="muted" style={{ marginTop: 4 }}>
            Deterministic rules — the scheduler obeys them exactly.
          </p>

          <div className="grid-2" style={{ marginTop: 4 }}>
            <ConfigRow label="Timeline (weeks)">
              <Stepper value={form.timeline_weeks} min={1} max={52} onChange={(v) => set('timeline_weeks', v)} />
            </ConfigRow>
            <ConfigRow label="Weekly hours">
              <Stepper value={form.weekly_hours} min={1} max={40} onChange={(v) => set('weekly_hours', v)} />
            </ConfigRow>
            <ConfigRow label="Preferred session (min)">
              <Stepper
                value={form.preferred_session_length_min}
                min={15}
                max={720}
                step={15}
                onChange={(v) => set('preferred_session_length_min', v)}
              />
            </ConfigRow>
            <ConfigRow label="Max session (min)" hint="must be ≥ preferred">
              <Stepper
                value={form.max_session_length_min}
                min={15}
                max={720}
                step={15}
                onChange={(v) => set('max_session_length_min', v)}
              />
            </ConfigRow>
          </div>
          {!sessionsValid && (
            <div className="field-hint" style={{ color: '#a33' }}>
              Max session must be at least the preferred session length.
            </div>
          )}

          <div className="field">
            <span className="field-label">Deep-work days &amp; window</span>
            <div className="chip-row">
              {DAYS.map((day) => (
                <button
                  key={day}
                  type="button"
                  className={`chip${form.dwwDays.includes(day) ? ' on' : ''}`}
                  onClick={() => toggleDay(day)}
                >
                  {day}
                </button>
              ))}
            </div>
            <div className="row" style={{ gap: 12, marginTop: 12 }}>
              <input
                className="input time"
                type="time"
                value={form.dwwStart}
                onChange={(e) => set('dwwStart', e.target.value)}
                aria-label="deep-work start"
              />
              <span className="muted">→</span>
              <input
                className="input time"
                type="time"
                value={form.dwwEnd}
                onChange={(e) => set('dwwEnd', e.target.value)}
                aria-label="deep-work end"
              />
              <span className="field-hint" style={{ marginTop: 0 }}>
                applies to each selected day · leave days empty to skip
              </span>
            </div>
          </div>

          <div className="field">
            <label className="field-label" htmlFor="tz">
              Timezone (IANA)
            </label>
            <input
              id="tz"
              className="input tz"
              value={form.timezone}
              onChange={(e) => set('timezone', e.target.value)}
              placeholder="America/Los_Angeles"
            />
          </div>

          <div className="card" style={{ padding: '6px 16px', marginTop: 18 }}>
            <ConfigRow label="No events before">
              <input
                className="input time"
                type="time"
                value={form.no_events_before}
                onChange={(e) => set('no_events_before', e.target.value)}
                aria-label="no events before"
              />
            </ConfigRow>
            <ConfigRow label="No events after">
              <input
                className="input time"
                type="time"
                value={form.no_events_after}
                onChange={(e) => set('no_events_after', e.target.value)}
                aria-label="no events after"
              />
            </ConfigRow>
            <ConfigRow label="Max daily study (min)" hint="caps total minutes per day">
              <Stepper
                value={form.max_daily_study_min}
                min={30}
                max={1440}
                step={30}
                onChange={(v) => set('max_daily_study_min', v)}
              />
            </ConfigRow>
            <ConfigRow label="Min break between deep blocks (min)">
              <Stepper
                value={form.min_break_between_deep_blocks_min}
                min={0}
                max={720}
                step={15}
                onChange={(v) => set('min_break_between_deep_blocks_min', v)}
              />
            </ConfigRow>
            <ConfigRow label="Allow weekends" hint="schedule blocks Sat / Sun">
              <Switch on={form.allow_weekends} onChange={(v) => set('allow_weekends', v)} />
            </ConfigRow>
            <ConfigRow label="Prefer evening sessions">
              <Switch on={form.prefer_evening_sessions} onChange={(v) => set('prefer_evening_sessions', v)} />
            </ConfigRow>
            <ConfigRow label="Prefer weekend long blocks">
              <Switch on={form.prefer_weekend_long_blocks} onChange={(v) => set('prefer_weekend_long_blocks', v)} />
            </ConfigRow>
            <ConfigRow label="Avoid back-to-back deep work">
              <Switch
                on={form.avoid_back_to_back_deep_work}
                onChange={(v) => set('avoid_back_to_back_deep_work', v)}
              />
            </ConfigRow>
          </div>
        </section>
      )}

      {step === 2 && (
        <section>
          <h1 className="t-h1" style={{ marginTop: 14 }}>
            Your skills
          </h1>
          <p className="muted" style={{ marginTop: 4 }}>
            We protect more time for weak areas. Comma-separated — no AI here.
          </p>
          <div className="field">
            <label className="field-label" htmlFor="weak">
              Weak areas
            </label>
            <input
              id="weak"
              className="input"
              value={form.known_weaknesses}
              onChange={(e) => set('known_weaknesses', e.target.value)}
              placeholder="graphs, dynamic programming, system design"
            />
          </div>
          <div className="field">
            <label className="field-label" htmlFor="strong">
              Strong areas
            </label>
            <input
              id="strong"
              className="input"
              value={form.known_strengths}
              onChange={(e) => set('known_strengths', e.target.value)}
              placeholder="arrays, hashing, SQL"
            />
          </div>
        </section>
      )}

      {step === 3 && (
        <section>
          <h1 className="t-h1" style={{ marginTop: 14 }}>
            Résumé &amp; targets
          </h1>
          <p className="muted" style={{ marginTop: 4 }}>
            Optional. Paste your résumé as plain text — it gives the planner background context.
          </p>
          <div className="field">
            <label className="field-label" htmlFor="resume">
              Paste your résumé (optional)
            </label>
            <textarea
              id="resume"
              className="textarea"
              style={{ minHeight: 180 }}
              value={form.resume_text}
              onChange={(e) => set('resume_text', e.target.value)}
              placeholder="Paste plain text — experience, stack, projects…"
            />
            <div className="field-hint">
              Stays on your account, never shared with other users, never used for training.
            </div>
          </div>
          <div className="grid-2">
            <div className="field">
              <label className="field-label" htmlFor="companies">
                Target companies
              </label>
              <input
                id="companies"
                className="input"
                value={form.target_companies}
                onChange={(e) => set('target_companies', e.target.value)}
                placeholder="comma-separated, optional"
              />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="level">
                Target level
              </label>
              <input
                id="level"
                className="input"
                value={form.target_level}
                onChange={(e) => set('target_level', e.target.value)}
                placeholder="e.g. new grad, senior (optional)"
              />
            </div>
          </div>
        </section>
      )}

      {step === 4 && (
        <section>
          <h1 className="t-h1" style={{ marginTop: 14 }}>
            You&rsquo;re connected
          </h1>
          <p className="muted" style={{ marginTop: 4 }}>
            Loop reads your busy times to schedule around them and writes approved blocks back —
            nothing else, and never without your approval.
          </p>
          <div className="card" style={{ padding: '16px 18px', marginTop: 18 }}>
            <ConfigRow label="Google Calendar" hint="connected via the secure sign-in">
              <span className="chip on">{me.email ?? 'connected'}</span>
            </ConfigRow>
          </div>
          <p className="muted" style={{ marginTop: 14, fontSize: 13 }}>
            Finishing setup saves your profile. Next, Loop drafts your plan — nothing is written to
            your calendar until you approve it.
          </p>
        </section>
      )}

      {error && <div className="banner-error">{error}</div>}

      <div className="footer-bar">
        <button
          className="btn btn-quiet"
          type="button"
          disabled={step === 0 || submitting}
          onClick={() => setStep((s) => Math.max(0, s - 1))}
        >
          ← Back
        </button>
        {isLast ? (
          <button className="btn btn-primary lg" type="button" disabled={submitting} onClick={() => void submit()}>
            {submitting ? 'Saving…' : 'Finish setup →'}
          </button>
        ) : (
          <button
            className="btn btn-primary lg"
            type="button"
            disabled={!canAdvance}
            onClick={() => setStep((s) => Math.min(STEP_LABELS.length - 1, s + 1))}
          >
            Next →
          </button>
        )}
      </div>
    </div>
  )
}
