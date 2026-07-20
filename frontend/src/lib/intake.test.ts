import { describe, expect, it } from 'vitest'

import type { ExtractResumeResult, MeResult, UserProfile } from '../api/types'
import {
  PLAN_DIRECTION_MAX_CHARS,
  RESUME_MIN_CHARS,
  STEP_LABELS,
  addChips,
  applyProposal,
  buildPayload,
  cleanList,
  draftContext,
  extractDisabled,
  failureNotice,
  initialForm,
  sectionsHaveContent,
  stepFromParam,
  weakAreasAreGuess,
} from './intake'
import { setupDeepLink } from './review'

const bareMe: MeResult = {
  user_id: 'u_1',
  onboarded: false,
  timezone: null,
  email: null,
  profile: null,
  inbound_calendar_sync_enabled: false,
}

const profile: UserProfile = {
  user_id: 'u_1',
  profile_version: 'profile_001',
  goal: 'Get interview-ready',
  target_role: 'Backend SWE',
  target_companies: ['infra startups'],
  target_level: 'new grad',
  timeline_weeks: 10,
  weekly_hours: 8,
  experience_level: 'intermediate',
  known_strengths: ['SQL'],
  known_weaknesses: ['graphs'],
  experience: [{ title: 'Backend intern', organization: 'Acme', summary: null }],
  skills: ['Python'],
  preferred_session_length_min: 60,
  max_session_length_min: 180,
  deep_work_windows: [{ day: 'Mon', start: '18:00', end: '21:00' }],
  hard_constraints: {
    no_events_before: '08:00',
    no_events_after: '22:30',
    allow_weekends: true,
    max_daily_study_min: 180,
    min_break_between_deep_blocks_min: 30,
  },
  preferences: {
    prefer_evening_sessions: false,
    prefer_weekend_long_blocks: false,
    avoid_back_to_back_deep_work: false,
  },
  motivation_profile_id: null,
  resume_text: null,
  plan_direction: null,
  created_at: '2026-07-06T00:00:00Z',
  updated_at: '2026-07-06T00:00:00Z',
}

/** The RI-C response shape: canonical skills resolved onto the taxonomy,
 *  the out-of-vocabulary surface flagged, never silently promoted. */
const okResult: ExtractResumeResult = {
  status: 'ok',
  run_id: 'intake-run_1',
  user_id: 'u_1',
  proposal: {
    experience: [
      { title: 'Backend intern', organization: 'Stripe', summary: 'Built billing services' },
      { title: 'Research assistant', organization: null, summary: null },
    ],
    skills: ['python', 'Postgres', 'Flurbo.js'],
    known_strengths: ['backend services', 'API design'],
    inferred_weak_spots: ['System design', 'Dynamic programming'],
    target_company_categories: ['infra startups', 'big tech'],
  },
  skills_canonical: [
    { skill_id: 'skill.python', display_name: 'Python', surface: 'python' },
    { skill_id: 'skill.postgresql', display_name: 'PostgreSQL', surface: 'Postgres' },
  ],
  skills_unmatched: ['Flurbo.js'],
  taxonomy_version: 'skill_taxonomy_v1',
  reason_code: null,
  detail: null,
}

const failedResult: ExtractResumeResult = {
  status: 'failed',
  run_id: 'intake-run_2',
  user_id: 'u_1',
  proposal: null,
  skills_canonical: [],
  skills_unmatched: [],
  taxonomy_version: null,
  reason_code: 'LLM_RETRY_LIMIT_EXCEEDED',
  detail: 'transport failed after retries',
}

describe('step mapping (5 -> 4 consolidation)', () => {
  it('is the 4-step layout with the Skills step absorbed into Résumé & profile', () => {
    expect(STEP_LABELS).toEqual(['Goal', 'Time & constraints', 'Résumé & profile', 'Connect'])
  })

  it('keeps the reason-aware deep link pointed at Time & constraints', () => {
    // lib/review.ts sends capacity/fit failures to this URL; if the step
    // layout shifts under it again, this is the test that must break.
    const link = setupDeepLink('INSUFFICIENT_WEEKLY_CAPACITY')
    const raw = new URLSearchParams(link.split('?')[1]).get('step')
    expect(STEP_LABELS[stepFromParam(raw)]).toBe('Time & constraints')
  })

  it('clamps stale 5-step-era indices instead of opening a missing step', () => {
    // Old index 4 was Connect; it clamps onto the new last step — still Connect.
    expect(stepFromParam('4')).toBe(3)
    expect(stepFromParam('9')).toBe(3)
  })

  it('falls back to the first step on junk', () => {
    expect(stepFromParam(null)).toBe(0)
    expect(stepFromParam('')).toBe(0)
    expect(stepFromParam('nope')).toBe(0)
    expect(stepFromParam('-2')).toBe(0)
  })
})

describe('payload round-trip (experience + skills)', () => {
  it('starts empty for a new user and submits empty lists', () => {
    const form = initialForm(bareMe)
    expect(form.experience).toEqual([])
    expect(form.skills).toEqual([])
    const payload = buildPayload(form, 'UTC')
    expect(payload.user_profile.experience).toEqual([])
    expect(payload.user_profile.skills).toEqual([])
  })

  it('prefills both fields from a saved profile and round-trips them', () => {
    const form = initialForm({ ...bareMe, onboarded: true, profile })
    // '' in the editor row stands for the contract's null.
    expect(form.experience).toEqual([{ title: 'Backend intern', organization: 'Acme', summary: '' }])
    expect(form.skills).toEqual(['Python'])
    const payload = buildPayload(form, 'UTC')
    expect(payload.user_profile.experience).toEqual([
      { title: 'Backend intern', organization: 'Acme', summary: null },
    ])
    expect(payload.user_profile.skills).toEqual(['Python'])
  })

  it('drops title-less editor rows and maps blank optionals back to null', () => {
    const form = initialForm(bareMe)
    form.experience = [
      { title: '  Backend intern ', organization: '  ', summary: 'Shipped stuff ' },
      { title: '   ', organization: 'Ghost Corp', summary: 'row without a title' },
    ]
    const payload = buildPayload(form, 'UTC')
    expect(payload.user_profile.experience).toEqual([
      { title: 'Backend intern', organization: null, summary: 'Shipped stuff' },
    ])
  })

  it('trims and dedupes skills case-insensitively, first spelling wins', () => {
    const form = initialForm(bareMe)
    form.skills = [' Python ', 'python', 'Go', '']
    expect(buildPayload(form, 'UTC').user_profile.skills).toEqual(['Python', 'Go'])
  })

  it('sends the draft wizard answers as context, unanswered as null', () => {
    const form = initialForm(bareMe)
    form.goal = '  '
    form.target_role = 'Backend SWE'
    expect(draftContext(form)).toEqual({
      goal: null,
      target_role: 'Backend SWE',
      experience_level: 'intermediate',
      timeline_weeks: 10,
      weekly_hours: 8,
    })
  })
})

describe('plan direction round-trip', () => {
  it('starts empty, submits null when trimmed-empty, and passes a set value verbatim', () => {
    const form = initialForm(bareMe)
    expect(form.plan_direction).toBe('')
    // Trimmed-empty must submit null, never '' — the contract rejects ''.
    expect(buildPayload(form, 'UTC').user_profile.plan_direction).toBeNull()
    form.plan_direction = '   '
    expect(buildPayload(form, 'UTC').user_profile.plan_direction).toBeNull()
    form.plan_direction = 'Blind 75 first, then two weeks of system design.'
    expect(buildPayload(form, 'UTC').user_profile.plan_direction).toBe(
      'Blind 75 first, then two weeks of system design.',
    )
  })

  it('allows a value at exactly the cap', () => {
    const form = initialForm(bareMe)
    form.plan_direction = 'x'.repeat(PLAN_DIRECTION_MAX_CHARS)
    expect(buildPayload(form, 'UTC').user_profile.plan_direction).toHaveLength(
      PLAN_DIRECTION_MAX_CHARS,
    )
  })

  it('prefills from a saved profile on re-onboard, like resume_text', () => {
    const withPlan = { ...profile, plan_direction: 'Dynamic programming first.' }
    const form = initialForm({ ...bareMe, onboarded: true, profile: withPlan })
    expect(form.plan_direction).toBe('Dynamic programming first.')
    expect(buildPayload(form, 'UTC').user_profile.plan_direction).toBe(
      'Dynamic programming first.',
    )
  })
})

describe('merge policy on Extract', () => {
  it('fills the five auto-fillable sections of a pristine form and nothing else', () => {
    const form = initialForm(bareMe)
    form.goal = 'my goal'
    form.target_level = 'senior'
    form.resume_text = 'x'.repeat(60)

    const next = applyProposal(form, okResult)

    expect(next.experience).toEqual([
      { title: 'Backend intern', organization: 'Stripe', summary: 'Built billing services' },
      { title: 'Research assistant', organization: '', summary: '' },
    ])
    // Canonical display names — never the raw surfaces, never the unmatched one.
    expect(next.skills).toEqual(['Python', 'PostgreSQL'])
    expect(next.known_strengths).toEqual(['backend services', 'API design'])
    expect(next.known_weaknesses).toEqual(['System design', 'Dynamic programming'])
    expect(next.target_companies).toEqual(['infra startups', 'big tech'])
    // Untouched: the user's own text and the never-auto-filled field.
    expect(next.goal).toBe('my goal')
    expect(next.target_level).toBe('senior')
    expect(next.resume_text).toBe('x'.repeat(60))
  })

  it('gates the replace behind a confirm exactly when a section has user content', () => {
    const pristine = initialForm(bareMe)
    expect(sectionsHaveContent(pristine)).toBe(false)
    // Résumé text and target level are NOT auto-fillable — no confirm for them.
    expect(sectionsHaveContent({ ...pristine, resume_text: 'x'.repeat(60), target_level: 'senior' })).toBe(false)
    expect(sectionsHaveContent({ ...pristine, skills: ['Python'] })).toBe(true)
    expect(sectionsHaveContent({ ...pristine, known_weaknesses: ['graphs'] })).toBe(true)
    expect(
      sectionsHaveContent({
        ...pristine,
        experience: [{ title: '', organization: 'Acme', summary: '' }],
      }),
    ).toBe(true)
    // An empty editor row alone is not content.
    expect(
      sectionsHaveContent({
        ...pristine,
        experience: [{ title: '', organization: '', summary: '' }],
      }),
    ).toBe(false)
  })

  it('keeps edits made after extraction and re-gates the next extract', () => {
    const applied = applyProposal(initialForm(bareMe), okResult)
    const edited = { ...applied, skills: addChips(applied.skills, 'Kubernetes') }
    expect(edited.skills).toEqual(['Python', 'PostgreSQL', 'Kubernetes'])
    // The next Extract press must ask before overwriting the edited sections.
    expect(sectionsHaveContent(edited)).toBe(true)
  })

  it('refuses to touch the form on a failed result', () => {
    const form = { ...initialForm(bareMe), skills: ['Python'] }
    expect(applyProposal(form, failedResult)).toBe(form)
  })
})

describe('extract flow state', () => {
  const longEnough = 'x'.repeat(RESUME_MIN_CHARS)

  it('disables the button while a request is pending', () => {
    expect(extractDisabled(longEnough, true)).toBe(true)
    expect(extractDisabled(longEnough, false)).toBe(false)
  })

  it('disables the button outside the contract length bounds (no 422 round-trip)', () => {
    expect(extractDisabled('', false)).toBe(true)
    expect(extractDisabled('too short', false)).toBe(true)
    expect(extractDisabled('x'.repeat(40_001), false)).toBe(true)
  })

  it('turns a failed result into a typed banner and an ok result into none', () => {
    expect(failureNotice(failedResult)).toEqual({
      code: 'LLM_RETRY_LIMIT_EXCEEDED',
      detail: 'transport failed after retries',
    })
    expect(failureNotice(okResult)).toBeNull()
  })

  it('falls back to the service default code on a malformed failure body', () => {
    expect(failureNotice({ ...failedResult, reason_code: null })).toMatchObject({
      code: 'LLM_CALL_FAILED',
    })
  })

  it('shows the weak-areas guess flag only while extracted entries remain', () => {
    const extracted = ['System design', 'Dynamic programming']
    expect(weakAreasAreGuess(['system design', 'graphs'], extracted)).toBe(true)
    expect(weakAreasAreGuess(['graphs'], extracted)).toBe(false)
    expect(weakAreasAreGuess(['System design'], [])).toBe(false)
  })
})

describe('chip list helpers', () => {
  it('splits pasted comma lists into chips and dedupes case-insensitively', () => {
    expect(addChips(['Python'], ' go , GO, Postgres ,,')).toEqual(['Python', 'go', 'Postgres'])
  })

  it('cleanList keeps the first spelling of a duplicate', () => {
    expect(cleanList(['PostgreSQL', 'postgresql', ' '])).toEqual(['PostgreSQL'])
  })
})
