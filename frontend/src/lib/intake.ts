// Pure logic for the onboarding wizard (RI-D): step layout + deep-link
// mapping, the form state the screen edits, the payload/prefill round-trip,
// and the extract-proposal merge policy. React-free and unit-tested, the same
// split as lib/review.ts, so the screen stays a thin view: the server-side
// UserProfile contract is the validation oracle, and the ResumeIntakeNode's
// proposal only ever lands in client state the user can edit — nothing
// persists until the wizard finishes through POST /api/onboard.

import type {
  DraftProfileContext,
  EvidenceKind,
  ExperienceLevel,
  ExtractResumeResult,
  MeResult,
  OnboardPayload,
  Weekday,
} from '../api/types'

/** The 5-step wizard. NP-E inserted "Your story" (index 3) between the résumé
 *  step and Connect. Indices 0–2 are unchanged so the reason-aware deep link in
 *  lib/review.ts (capacity/fit failures → ?step=1, "Time & constraints") still
 *  lands correctly; the mapping test pins that. */
export const STEP_LABELS = [
  'Goal',
  'Time & constraints',
  'Résumé & profile',
  'Your story',
  'Connect',
]

/** Parse a ?step= deep link. Junk becomes the first step; out-of-range
 *  indices clamp to the last step, so a stale link can never open a step that
 *  no longer exists. */
export function stepFromParam(raw: string | null): number {
  const requested = Number.parseInt(raw ?? '0', 10)
  if (Number.isNaN(requested)) return 0
  return Math.min(Math.max(requested, 0), STEP_LABELS.length - 1)
}

/** Mirrors of the resume_intake_input contract bounds, so the Extract button
 *  disables instead of round-tripping to a 422. The server stays the oracle. */
export const RESUME_MIN_CHARS = 50
export const RESUME_MAX_CHARS = 40_000

/** Mirror of contracts/user_profile.py::PLAN_DIRECTION_MAX_CHARS (the source
 *  of truth); the textarea's maxLength is UX, the contract is enforcement. */
export const PLAN_DIRECTION_MAX_CHARS = 4000

/** One experience row as the form edits it — '' where the contract has null,
 *  because controlled inputs want strings. buildPayload converts back. `kind`
 *  and `theme_tags` are the story-layer tags (NP-E): a closed-vocab kind (default
 *  `work`) and 0–5 closed-vocab themes the user edits from dropdowns. */
export interface ExperienceRow {
  title: string
  organization: string
  summary: string
  kind: EvidenceKind
  theme_tags: string[]
}

export interface FormState {
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
  experience: ExperienceRow[]
  skills: string[]
  known_strengths: string[]
  known_weaknesses: string[]
  resume_text: string
  plan_direction: string
  target_companies: string[]
  target_level: string
  prefer_evening_sessions: boolean
  prefer_weekend_long_blocks: boolean
  avoid_back_to_back_deep_work: boolean
  // Story layer (NP-E): the chosen pathway, or null when the user skips the
  // "Your story" step. `pathway_registry_version` pins the version the cards were
  // drawn against (from the preview result), so the stored selection carries the
  // same version discipline the taxonomy uses.
  pathway_id: string | null
  pathway_registry_version: string | null
}

export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

const WEEKDAYS: Weekday[] = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']

export function initialForm(me: MeResult): FormState {
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
    experience: (profile?.experience ?? []).map((item) => ({
      title: item.title,
      organization: item.organization ?? '',
      summary: item.summary ?? '',
      kind: item.kind ?? 'work',
      theme_tags: item.theme_tags ?? [],
    })),
    skills: profile?.skills ?? [],
    known_strengths: profile?.known_strengths ?? [],
    known_weaknesses: profile?.known_weaknesses ?? [],
    resume_text: profile?.resume_text ?? '',
    plan_direction: profile?.plan_direction ?? '',
    target_companies: profile?.target_companies ?? [],
    target_level: profile?.target_level ?? '',
    pathway_id: profile?.pathway_selection?.pathway_id ?? null,
    pathway_registry_version: profile?.pathway_selection?.pathway_registry_version ?? null,
  }
}

/** Trim, drop blanks, and dedupe case-insensitively (first spelling wins) —
 *  the profile contract requires case-insensitive uniqueness for list fields. */
export function cleanList(items: string[]): string[] {
  const out: string[] = []
  const seen = new Set<string>()
  for (const raw of items) {
    const item = raw.trim()
    if (!item || seen.has(item.toLowerCase())) continue
    seen.add(item.toLowerCase())
    out.push(item)
  }
  return out
}

/** Append chips from raw input (comma-splittable, so a pasted "a, b, c" lands
 *  as three chips) onto an existing list, deduped case-insensitively. */
export function addChips(list: string[], raw: string): string[] {
  return cleanList([...list, ...raw.split(',')])
}

/** The theme-vocabulary cap the contract enforces (max 5 per item), mirrored so
 *  the UI stops adding a sixth chip instead of round-tripping to a 422. */
export const MAX_THEME_TAGS = 5

export function buildPayload(form: FormState, timezone: string): OnboardPayload {
  const now = new Date().toISOString()
  // Emit a selection only when both the id and its pinned registry version are
  // present (they are set together when the user picks a card); a bare id would
  // be a contract-invalid selection.
  const pathwaySelection =
    form.pathway_id && form.pathway_registry_version
      ? {
          pathway_id: form.pathway_id,
          pathway_registry_version: form.pathway_registry_version,
          selected_at: now,
          slot_overrides: [],
        }
      : null
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
      target_companies: cleanList(form.target_companies),
      target_level: form.target_level.trim() || null,
      timeline_weeks: form.timeline_weeks,
      weekly_hours: form.weekly_hours,
      experience_level: form.experience_level,
      known_strengths: cleanList(form.known_strengths),
      known_weaknesses: cleanList(form.known_weaknesses),
      // A row without a title is an empty editor row, not an entry; '' maps
      // back to the contract's null for the optional columns.
      experience: form.experience
        .map((row) => ({
          title: row.title.trim(),
          organization: row.organization.trim() || null,
          summary: row.summary.trim() || null,
          kind: row.kind,
          // Closed-vocab tags, deduped case-insensitively and capped like the
          // contract; the dropdowns already constrain membership.
          theme_tags: cleanList(row.theme_tags).slice(0, MAX_THEME_TAGS),
        }))
        .filter((row) => row.title.length > 0),
      skills: cleanList(form.skills),
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
      pathway_selection: pathwaySelection,
      resume_text: form.resume_text.trim() || null,
      // Trimmed-empty becomes null, never "" — the contract rejects "" by
      // design (min_length=1).
      plan_direction: form.plan_direction.trim() || null,
      created_at: now,
      updated_at: now,
    },
  }
}

/** The draft answers from earlier wizard steps the node may use as context —
 *  unanswered fields go as null, mirroring DraftProfileContext. */
export function draftContext(form: FormState): DraftProfileContext {
  return {
    goal: form.goal.trim() || null,
    target_role: form.target_role.trim() || null,
    experience_level: form.experience_level,
    timeline_weeks: form.timeline_weeks,
    weekly_hours: form.weekly_hours,
  }
}

/** Whether the Extract button must be disabled: a request is already in
 *  flight, or the paste is outside the contract's length bounds. */
export function extractDisabled(resumeText: string, pending: boolean): boolean {
  const length = resumeText.trim().length
  return pending || length < RESUME_MIN_CHARS || length > RESUME_MAX_CHARS
}

/** The five auto-fillable sections (Experience, Skills, Strong areas, Weak
 *  areas, Targets) — true when any holds user-visible content, in which case
 *  applying a proposal must be gated by an explicit confirm (never destroy
 *  hand-typed input silently). Résumé text and target level don't count:
 *  extraction never overwrites them. */
export function sectionsHaveContent(form: FormState): boolean {
  return (
    form.experience.some(
      (row) => row.title.trim() !== '' || row.organization.trim() !== '' || row.summary.trim() !== '',
    ) ||
    form.skills.length > 0 ||
    form.known_strengths.length > 0 ||
    form.known_weaknesses.length > 0 ||
    form.target_companies.length > 0
  )
}

/** Replace-on-extract: the proposal replaces exactly the five auto-fillable
 *  sections and touches nothing else. Skills take the CANONICAL display names
 *  (the taxonomy-resolved view the wizard offers to store) — unmatched
 *  surfaces stay out of the form until the user explicitly keeps them. */
export function applyProposal(form: FormState, result: ExtractResumeResult): FormState {
  const proposal = result.proposal
  if (result.status !== 'ok' || proposal === null) return form
  return {
    ...form,
    experience: proposal.experience.map((item) => ({
      title: item.title,
      organization: item.organization ?? '',
      summary: item.summary ?? '',
      // Carry the node's proposed tags into the editable form (NP-C proposes
      // them); the user reviews and can change both in the review step.
      kind: item.kind ?? 'work',
      theme_tags: item.theme_tags ?? [],
    })),
    skills: cleanList(result.skills_canonical.map((skill) => skill.display_name)),
    known_strengths: cleanList(proposal.known_strengths),
    known_weaknesses: cleanList(proposal.inferred_weak_spots),
    target_companies: cleanList(proposal.target_company_categories),
  }
}

/** The typed failure surface: a non-ok result becomes banner content with the
 *  reason_code (LLM_CALL_FAILED is the service's own fallback, mirrored here
 *  for a malformed body); an ok result yields nothing. The form is never
 *  touched on failure — applyProposal refuses non-ok results. */
export function failureNotice(
  result: ExtractResumeResult,
): { code: string; detail: string | null } | null {
  if (result.status === 'ok' && result.proposal !== null) return null
  return { code: result.reason_code ?? 'LLM_CALL_FAILED', detail: result.detail }
}

/** The weak-areas "a guess" flag: shown while the section still carries at
 *  least one entry from the latest extraction — once the user has replaced
 *  them all, "inferred from your résumé" would be a false label. */
export function weakAreasAreGuess(current: string[], extracted: string[]): boolean {
  if (extracted.length === 0) return false
  const lowered = new Set(extracted.map((item) => item.toLowerCase()))
  return current.some((item) => lowered.has(item.toLowerCase()))
}
