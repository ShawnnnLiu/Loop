import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { ApiError, api, errorMessage } from '../api/client'
import type {
  EvidenceKind,
  ExperienceLevel,
  ExtractResumeResult,
  MeResult,
  PathwaysResult,
  Weekday,
} from '../api/types'
import { EVIDENCE_KINDS } from '../api/types'
import {
  MAX_THEME_TAGS,
  PLAN_DIRECTION_MAX_CHARS,
  RESUME_MIN_CHARS,
  STEP_LABELS,
  addChips,
  applyProposal,
  browserTimezone,
  buildPayload,
  cleanList,
  draftContext,
  extractDisabled,
  failureNotice,
  initialForm,
  sectionsHaveContent,
  stepFromParam,
  weakAreasAreGuess,
  type ExperienceRow,
  type FormState,
} from '../lib/intake'
import { characterSheet, kindLabel, unfilledSlots } from '../lib/story'
import { PathwayCardView } from '../components/PathwayCard'

// The onboarding wizard. Every field maps straight onto the UserProfile
// contract, which is the single validation oracle — the wizard only shapes
// input (chips -> lists, day toggles -> windows). One step is AI-assisted
// (RI-D): "Résumé & profile" can call the persistence-free extract endpoint
// behind an explicit button; the proposal lands in client state the user
// reviews and edits, and nothing persists until the wizard finishes through
// POST /api/onboard — LLMs propose, the review gate + contract dispose.
// Skipping the résumé keeps every field fully hand-editable. Google is
// already connected (it is the entry gate), so the final step confirms the
// connection rather than triggering OAuth.

const DAYS: Weekday[] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const LEVELS: ExperienceLevel[] = ['beginner', 'intermediate', 'advanced']

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

const chipButtonStyle: React.CSSProperties = {
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  color: 'inherit',
  font: 'inherit',
  fontSize: 13,
  padding: '0 0 0 6px',
  lineHeight: 1,
}

/** Chip editor over a string list: type, Enter/comma/blur commits, × removes.
 *  Free-text entry is always allowed — the skill vocabulary constrains the
 *  AI's proposals, never the user. */
function ChipInput({
  id,
  value,
  onChange,
  placeholder,
}: {
  id: string
  value: string[]
  onChange: (next: string[]) => void
  placeholder: string
}) {
  const [text, setText] = useState('')
  const commit = () => {
    if (!text.trim()) return
    onChange(addChips(value, text))
    setText('')
  }
  return (
    <div className="chip-row" style={{ alignItems: 'center', marginTop: 8 }}>
      {value.map((item) => (
        <span key={item} className="chip on sm">
          {item}
          <button
            type="button"
            aria-label={`remove ${item}`}
            style={chipButtonStyle}
            onClick={() => onChange(value.filter((entry) => entry !== item))}
          >
            ×
          </button>
        </span>
      ))}
      <input
        id={id}
        className="input"
        style={{ maxWidth: 230, padding: '6px 10px', fontSize: 13 }}
        value={text}
        placeholder={placeholder}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault()
            commit()
          }
        }}
        onBlur={commit}
      />
    </div>
  )
}

/** Structural provenance label for a section the last extraction filled —
 *  per field group (extracted / inferred / suggested), never per chip, and
 *  never a confidence score (axiom 08: LLMs do not assign confidence). */
function Provenance({ kind, show }: { kind: 'extracted' | 'inferred' | 'suggested'; show: boolean }) {
  if (!show) return null
  return (
    <span className="tag" style={{ marginLeft: 8 }}>
      AI · {kind}
    </span>
  )
}

export function OnboardingScreen({ me }: { me: MeResult }) {
  const navigate = useNavigate()
  // Reason-aware deep link (B5): a capacity/fit failure sends the user
  // straight to the step that caused it — /onboarding?step=1 opens
  // "Time & constraints". Indices are the 4-step layout's (RI-D); stale
  // 5-step-era links clamp inside stepFromParam.
  const [searchParams] = useSearchParams()
  const [step, setStep] = useState(() => stepFromParam(searchParams.get('step')))
  const [form, setForm] = useState<FormState>(() => initialForm(me))
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Extraction state is client-only (RI-D): applied proposals live in the
  // same editable form as hand-typed input; unmatched skill surfaces and the
  // weak-spot origin list exist only to render the flagged group / "a guess"
  // tag until the wizard finishes.
  const [extracting, setExtracting] = useState(false)
  const [applied, setApplied] = useState(false)
  const [extractError, setExtractError] = useState<{ code: string | null; detail: string | null } | null>(null)
  const [pendingProposal, setPendingProposal] = useState<ExtractResumeResult | null>(null)
  const [unmatched, setUnmatched] = useState<string[]>([])
  const [extractedWeakSpots, setExtractedWeakSpots] = useState<string[]>([])

  // Story layer (NP-E): the closed theme vocabulary for the tag editors, and the
  // persistence-free pathway-card preview over the draft evidence for the
  // "Your story" step. Both are deterministic reads — no LLM.
  const [themes, setThemes] = useState<string[]>([])
  const [pathways, setPathways] = useState<PathwaysResult | null>(null)
  const [pathwaysLoading, setPathwaysLoading] = useState(false)
  const [pathwaysError, setPathwaysError] = useState<string | null>(null)

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }))

  // Fetch the track's theme vocabulary once the role is known and the user has
  // reached the tagging steps; empty themes (no track) simply hides the theme
  // pickers. Ignores errors — tagging is optional, kinds work without it.
  useEffect(() => {
    const role = form.target_role.trim()
    if (step < 2 || !role) return
    let active = true
    api
      .evidenceVocabulary(role)
      .then((vocab) => {
        if (active) setThemes(vocab.themes)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [step, form.target_role])

  const toggleDay = (day: Weekday) =>
    setForm((prev) => ({
      ...prev,
      dwwDays: prev.dwwDays.includes(day)
        ? prev.dwwDays.filter((d) => d !== day)
        : [...prev.dwwDays, day],
    }))

  const setExperienceRow = (index: number, field: keyof ExperienceRow, value: string) =>
    setForm((prev) => ({
      ...prev,
      experience: prev.experience.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    }))
  const addExperienceRow = () =>
    setForm((prev) => ({
      ...prev,
      experience: [
        ...prev.experience,
        { title: '', organization: '', summary: '', kind: 'work', theme_tags: [] },
      ],
    }))
  const removeExperienceRow = (index: number) =>
    setForm((prev) => ({ ...prev, experience: prev.experience.filter((_, i) => i !== index) }))

  const setExperienceKind = (index: number, kind: EvidenceKind) =>
    setForm((prev) => ({
      ...prev,
      experience: prev.experience.map((row, i) => (i === index ? { ...row, kind } : row)),
    }))
  // Toggle a closed-vocab theme on one item, honoring the contract's 5-tag cap.
  const toggleExperienceTheme = (index: number, theme: string) =>
    setForm((prev) => ({
      ...prev,
      experience: prev.experience.map((row, i) => {
        if (i !== index) return row
        const has = row.theme_tags.includes(theme)
        if (!has && row.theme_tags.length >= MAX_THEME_TAGS) return row
        return {
          ...row,
          theme_tags: has ? row.theme_tags.filter((t) => t !== theme) : [...row.theme_tags, theme],
        }
      }),
    }))

  // Persistence-free pathway preview over the current draft evidence. Re-run each
  // time the "Your story" step opens so the cards reflect the latest tags, and
  // pin the selection to the registry version the cards were drawn against.
  function loadPathways() {
    setPathwaysLoading(true)
    setPathwaysError(null)
    const tz = form.timezone.trim() || browserTimezone() || 'UTC'
    api
      .previewPathways({ user_profile: buildPayload(form, tz).user_profile })
      .then((result) => {
        setPathways(result)
        setPathwaysLoading(false)
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) return
        setPathwaysError(errorMessage(err))
        setPathwaysLoading(false)
      })
  }

  const selectPathway = (pathwayId: string, registryVersion: string) => {
    setForm((prev) => ({
      ...prev,
      pathway_id: pathwayId,
      pathway_registry_version: registryVersion,
    }))
  }
  const skipPathway = () =>
    setForm((prev) => ({ ...prev, pathway_id: null, pathway_registry_version: null }))

  // Advance one step; entering "Your story" (index 3) refreshes the card preview
  // over the latest draft evidence.
  const advance = () => {
    const next = Math.min(STEP_LABELS.length - 1, step + 1)
    if (next === 3) loadPathways()
    setStep(next)
  }

  function applyResult(result: ExtractResumeResult) {
    setForm((prev) => applyProposal(prev, result))
    setUnmatched(result.skills_unmatched)
    setExtractedWeakSpots(result.proposal?.inferred_weak_spots ?? [])
    setApplied(true)
    setPendingProposal(null)
  }

  const keepUnmatched = (surface: string) => {
    setForm((prev) => ({ ...prev, skills: cleanList([...prev.skills, surface]) }))
    setUnmatched((prev) => prev.filter((entry) => entry !== surface))
  }
  const dropUnmatched = (surface: string) =>
    setUnmatched((prev) => prev.filter((entry) => entry !== surface))

  async function runExtract() {
    setExtracting(true)
    setExtractError(null)
    setPendingProposal(null)
    try {
      const result = await api.extractResume({
        resume_text: form.resume_text,
        draft_context: draftContext(form),
      })
      const failure = failureNotice(result)
      if (failure) {
        // LLM failure: HTTP 200 + typed reason_code. Local and retryable —
        // every section below stays hand-editable, the wizard stays navigable.
        setExtractError(failure)
      } else if (sectionsHaveContent(form)) {
        // Never destroy hand-typed input silently: hold the proposal until
        // the user confirms the replace.
        setPendingProposal(result)
      } else {
        applyResult(result)
      }
      setExtracting(false)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return // redirected to login
      // Transport / contract-invalid (422) failures carry no typed
      // reason_code; surface the message honestly instead of inventing one.
      setExtractError({ code: null, detail: errorMessage(err) })
      setExtracting(false)
    }
  }

  // Client-side guards mirror the contract's hard rules so most submits pass;
  // the server stays the oracle and any remaining rejection surfaces below.
  const goalReady = form.goal.trim().length > 0 && form.target_role.trim().length > 0
  const sessionsValid = form.max_session_length_min >= form.preferred_session_length_min
  const canAdvance = step !== 0 || goalReady
  const isLast = step === STEP_LABELS.length - 1
  const resumeLength = form.resume_text.trim().length
  const planDirectionLength = form.plan_direction.length
  const weakAreasGuess = weakAreasAreGuess(form.known_weaknesses, extractedWeakSpots)
  const sheet = characterSheet(form.experience)
  const experienceTitles = form.experience.map((row) => row.title)
  const selectedCard = pathways?.cards.find((c) => c.pathway_id === form.pathway_id) ?? null

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
                placeholder="e.g. Backend SWE, Data Scientist, or Data Engineer"
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
            Résumé &amp; profile
          </h1>
          <p className="muted" style={{ marginTop: 4 }}>
            Paste your résumé and Loop drafts the fields below — the one AI-assisted step, and you
            review every field. Prefer to type? Everything works by hand. Nothing is saved until you
            finish setup.
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

          <div className="row" style={{ gap: 12, alignItems: 'center' }}>
            <button
              className="btn btn-primary"
              type="button"
              disabled={extractDisabled(form.resume_text, extracting)}
              onClick={() => void runExtract()}
            >
              {extracting ? (
                <>
                  <span className="spin" style={{ width: 11, height: 11, marginRight: 7 }} />
                  Reading your résumé…
                </>
              ) : applied ? (
                'Looks wrong? Re-extract'
              ) : (
                'Extract from résumé'
              )}
            </button>
            {resumeLength > 0 && resumeLength < RESUME_MIN_CHARS && (
              <span className="field-hint" style={{ marginTop: 0 }}>
                paste at least {RESUME_MIN_CHARS} characters to extract
              </span>
            )}
          </div>

          {extractError && (
            <div className="banner-error" style={{ marginTop: 14 }}>
              We couldn&rsquo;t read your résumé this time — nothing below was changed. Fill the
              fields in by hand or try again.
              {extractError.code && (
                <span className="err-code" style={{ marginLeft: 8 }}>
                  {extractError.code}
                </span>
              )}
              {extractError.detail && (
                <div style={{ marginTop: 4, fontSize: 12.5 }}>{extractError.detail}</div>
              )}
            </div>
          )}

          {pendingProposal && (
            <div className="card" style={{ padding: '12px 16px', marginTop: 14 }}>
              <div style={{ fontWeight: 600 }}>
                Replace your current entries with the extracted ones?
              </div>
              <div className="muted" style={{ fontSize: 13, marginTop: 3 }}>
                Some fields below already have content — extracting overwrites the experience,
                skills, strong/weak areas, and target sections. Your résumé text and target level
                stay untouched.
              </div>
              <div className="row" style={{ gap: 8, marginTop: 10 }}>
                <button
                  className="btn btn-primary sm"
                  type="button"
                  onClick={() => applyResult(pendingProposal)}
                >
                  Replace
                </button>
                <button
                  className="btn btn-quiet sm"
                  type="button"
                  onClick={() => setPendingProposal(null)}
                >
                  Keep mine
                </button>
              </div>
            </div>
          )}

          {applied && (
            <div className="row" style={{ marginTop: 18, gap: 8, alignItems: 'baseline' }}>
              <span className="label">Extracted from your résumé</span>
              <span className="tag warn">AI · please review</span>
            </div>
          )}

          <div className="field">
            <span className="field-label">
              Experience
              <Provenance kind="extracted" show={applied} />
            </span>
            {form.experience.map((row, i) => (
              <div key={i} className="card soft" style={{ padding: '10px 12px', marginTop: 8 }}>
                <div className="row" style={{ gap: 8 }}>
                  <input
                    className="input"
                    style={{ flex: 1 }}
                    aria-label={`experience ${i + 1} title`}
                    placeholder="Title — e.g. Backend intern"
                    value={row.title}
                    onChange={(e) => setExperienceRow(i, 'title', e.target.value)}
                  />
                  <input
                    className="input"
                    style={{ flex: 1 }}
                    aria-label={`experience ${i + 1} organization`}
                    placeholder="Organization (optional)"
                    value={row.organization}
                    onChange={(e) => setExperienceRow(i, 'organization', e.target.value)}
                  />
                  <button
                    type="button"
                    className="btn btn-quiet sm"
                    aria-label={`remove experience ${i + 1}`}
                    onClick={() => removeExperienceRow(i)}
                  >
                    ×
                  </button>
                </div>
                <input
                  className="input"
                  style={{ marginTop: 8, width: '100%', boxSizing: 'border-box' }}
                  aria-label={`experience ${i + 1} summary`}
                  placeholder="One-line summary (optional)"
                  value={row.summary}
                  onChange={(e) => setExperienceRow(i, 'summary', e.target.value)}
                />
                <div className="row" style={{ gap: 10, marginTop: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <label className="cs" htmlFor={`kind-${i}`}>
                    Kind
                  </label>
                  <select
                    id={`kind-${i}`}
                    className="input"
                    style={{ maxWidth: 150, padding: '6px 8px', fontSize: 13 }}
                    value={row.kind}
                    onChange={(e) => setExperienceKind(i, e.target.value as EvidenceKind)}
                  >
                    {EVIDENCE_KINDS.map((k) => (
                      <option key={k} value={k}>
                        {kindLabel(k)}
                      </option>
                    ))}
                  </select>
                  {themes.length > 0 && (
                    <span className="cs">
                      Themes ({row.theme_tags.length}/{MAX_THEME_TAGS})
                    </span>
                  )}
                </div>
                {themes.length > 0 && (
                  <div className="chip-row" style={{ marginTop: 6 }}>
                    {themes.map((theme) => {
                      const on = row.theme_tags.includes(theme)
                      const atCap = !on && row.theme_tags.length >= MAX_THEME_TAGS
                      return (
                        <button
                          key={theme}
                          type="button"
                          className={`chip sm${on ? ' on' : ''}`}
                          disabled={atCap}
                          aria-pressed={on}
                          onClick={() => toggleExperienceTheme(i, theme)}
                        >
                          {theme}
                        </button>
                      )
                    })}
                  </div>
                )}
              </div>
            ))}
            <div>
              <button type="button" className="btn btn-quiet sm" style={{ marginTop: 8 }} onClick={addExperienceRow}>
                + Add experience
              </button>
            </div>
          </div>

          <div className="field">
            <label className="field-label" htmlFor="skills-input">
              Skills
              <Provenance kind="extracted" show={applied} />
            </label>
            <ChipInput
              id="skills-input"
              value={form.skills}
              onChange={(next) => set('skills', next)}
              placeholder="e.g. Python — Enter to add"
            />
            {unmatched.length > 0 && (
              <div
                className="card soft"
                style={{ padding: '10px 12px', marginTop: 10, borderStyle: 'dashed' }}
              >
                <span className="field-label">Not recognized</span>
                <div className="field-hint" style={{ marginTop: 2 }}>
                  Found in your résumé but not in our skill vocabulary — keep or remove.
                </div>
                <div className="chip-row" style={{ marginTop: 8 }}>
                  {unmatched.map((surface) => (
                    <span key={surface} className="chip sm">
                      {surface}
                      <button type="button" style={chipButtonStyle} onClick={() => keepUnmatched(surface)}>
                        keep
                      </button>
                      <button
                        type="button"
                        aria-label={`remove ${surface}`}
                        style={chipButtonStyle}
                        onClick={() => dropUnmatched(surface)}
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          <div className="grid-2">
            <div className="field">
              <label className="field-label" htmlFor="strong-input">
                Strong areas
                <Provenance kind="inferred" show={applied} />
              </label>
              <ChipInput
                id="strong-input"
                value={form.known_strengths}
                onChange={(next) => set('known_strengths', next)}
                placeholder="e.g. SQL — Enter to add"
              />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="weak-input">
                Weak areas
                {weakAreasGuess && (
                  <span className="tag warn" style={{ marginLeft: 8 }}>
                    a guess
                  </span>
                )}
              </label>
              <ChipInput
                id="weak-input"
                value={form.known_weaknesses}
                onChange={(next) => set('known_weaknesses', next)}
                placeholder="e.g. system design — Enter to add"
              />
              {weakAreasGuess ? (
                <div className="field-hint">Inferred from your résumé — edit freely.</div>
              ) : (
                <div className="field-hint">We protect more time for weak areas.</div>
              )}
            </div>
          </div>

          <div className="grid-2">
            <div className="field">
              <label className="field-label" htmlFor="companies-input">
                Target companies or categories
                <Provenance kind="suggested" show={applied} />
              </label>
              <ChipInput
                id="companies-input"
                value={form.target_companies}
                onChange={(next) => set('target_companies', next)}
                placeholder="e.g. infra startups — Enter to add"
              />
              <div className="field-hint">
                Extraction suggests categories only — type any company names you want.
              </div>
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
              <div className="field-hint">Always yours to set — never auto-filled.</div>
            </div>
          </div>

          <div className="field">
            <label className="field-label" htmlFor="plan-direction">
              Already have a plan? (optional)
            </label>
            <textarea
              id="plan-direction"
              className="textarea"
              style={{ minHeight: 120 }}
              value={form.plan_direction}
              onChange={(e) => set('plan_direction', e.target.value)}
              maxLength={PLAN_DIRECTION_MAX_CHARS}
              placeholder="e.g. Blind 75 first, then two weeks of system design…"
            />
            <div className="field-hint">
              Paste your own plan or the first steps you want to take — we&rsquo;ll adapt it to
              your weekly hours and timeline.
            </div>
            {planDirectionLength >= PLAN_DIRECTION_MAX_CHARS * 0.8 && (
              <div className="field-hint">
                {planDirectionLength.toLocaleString()} / {PLAN_DIRECTION_MAX_CHARS.toLocaleString()}{' '}
                characters
              </div>
            )}
          </div>
        </section>
      )}

      {step === 3 && (
        <section>
          <h1 className="t-h1" style={{ marginTop: 14 }}>
            Your story
          </h1>
          <p className="muted" style={{ marginTop: 4 }}>
            Pick one story to build toward - the planner will prioritize the pillars you haven&rsquo;t
            filled yet. This is optional: skip it and Loop works exactly as before. You can change it
            any time from Tuning.
          </p>

          <div className="card soft" style={{ padding: '12px 16px', marginTop: 14 }}>
            <span className="label">Who you are today</span>
            {sheet.total === 0 ? (
              <p className="muted" style={{ fontSize: 13, marginTop: 6, lineHeight: 1.5 }}>
                Your evidence is thin so far - that&rsquo;s honest, not a problem. Choosing an
                aspirational story from zero is a legitimate move; the plan then schedules the work
                that fills it.
              </p>
            ) : (
              <>
                <div className="chip-row" style={{ marginTop: 8 }}>
                  {sheet.kindCounts.map((kc) => (
                    <span key={kc.kind} className="chip sm on">
                      {kc.count} {kindLabel(kc.kind)}
                    </span>
                  ))}
                </div>
                {sheet.topThemes.length > 0 && (
                  <div className="chip-row" style={{ marginTop: 6 }}>
                    {sheet.topThemes.map((theme) => (
                      <span key={theme} className="chip sm">
                        {theme}
                      </span>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {pathwaysLoading && (
            <div className="row" style={{ marginTop: 16, alignItems: 'center', gap: 8 }}>
              <span className="spin" style={{ width: 12, height: 12 }} />
              <span className="muted">Ranking your pathways…</span>
            </div>
          )}
          {pathwaysError && (
            <div className="banner-error" style={{ marginTop: 14 }}>
              Couldn&rsquo;t load pathways — {pathwaysError}
              <button className="btn btn-quiet sm" type="button" style={{ marginLeft: 10 }} onClick={loadPathways}>
                Retry
              </button>
            </div>
          )}
          {pathways && !pathwaysLoading && pathways.cards.length === 0 && (
            <p className="muted" style={{ marginTop: 16, fontSize: 13 }}>
              We don&rsquo;t have curated pathways for this role yet — skip this step and continue.
            </p>
          )}

          {pathways &&
            !pathwaysLoading &&
            pathways.cards.map((card) => (
              <PathwayCardView
                key={card.pathway_id}
                card={{ ...card, selected: card.pathway_id === form.pathway_id }}
                experienceTitles={experienceTitles}
                onSelect={() => selectPathway(card.pathway_id, pathways.registry_version)}
              />
            ))}

          {selectedCard && (
            <div
              className="card"
              style={{ marginTop: 14, padding: '12px 16px', borderColor: 'var(--sage)', background: 'var(--sage-soft)' }}
            >
              <span style={{ fontWeight: 600, fontSize: 13.5 }}>
                Your plan will prioritize filling{' '}
                {unfilledSlots(selectedCard).length === 0
                  ? 'no new pillars — this story is already complete'
                  : `${unfilledSlots(selectedCard).length} pillar${
                      unfilledSlots(selectedCard).length === 1 ? '' : 's'
                    }`}
                .
              </span>
              {unfilledSlots(selectedCard).length > 0 && (
                <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>
                  {unfilledSlots(selectedCard)
                    .map((s) => s.title)
                    .join(' · ')}
                </div>
              )}
            </div>
          )}

          {pathways && !pathwaysLoading && pathways.cards.length > 0 && (
            <button
              type="button"
              className="btn btn-quiet sm"
              style={{ marginTop: 14 }}
              onClick={skipPathway}
            >
              {form.pathway_id ? 'Clear selection (skip)' : 'Skip — no pathway for now'}
            </button>
          )}
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
          <button className="btn btn-primary lg" type="button" disabled={!canAdvance} onClick={advance}>
            Next →
          </button>
        )}
      </div>
    </div>
  )
}
