// TypeScript mirrors of the JSON the backend returns
// (agentic_calendar/app/results.py). These grow per screen; the set below is
// the F-A read surface the SPA renders from. Tz-aware datetimes arrive as ISO
// strings (the client localizes); enums arrive as their string values.

export type ReasonCode = string

export type ExperienceLevel = 'beginner' | 'intermediate' | 'advanced'
export type Weekday = 'Mon' | 'Tue' | 'Wed' | 'Thu' | 'Fri' | 'Sat' | 'Sun'

export interface DeepWorkWindow {
  day: Weekday
  start: string // HH:MM
  end: string // HH:MM
}

export interface HardConstraints {
  no_events_before: string // HH:MM
  no_events_after: string // HH:MM
  allow_weekends: boolean
  max_daily_study_min: number
  min_break_between_deep_blocks_min: number
}

export interface Preferences {
  prefer_evening_sessions: boolean
  prefer_weekend_long_blocks: boolean
  avoid_back_to_back_deep_work: boolean
}

/** Mirror of contracts/user_profile.py::UserProfile. Times are HH:MM strings;
 *  created_at/updated_at are tz-aware ISO datetimes. */
export interface UserProfile {
  user_id: string
  profile_version: string
  goal: string
  target_role: string
  target_companies: string[]
  target_level: string | null
  timeline_weeks: number
  weekly_hours: number
  experience_level: ExperienceLevel
  known_strengths: string[]
  known_weaknesses: string[]
  preferred_session_length_min: number
  max_session_length_min: number
  deep_work_windows: DeepWorkWindow[]
  hard_constraints: HardConstraints
  preferences: Preferences
  motivation_profile_id?: string | null
  resume_text: string | null
  created_at: string
  updated_at: string
}

/** The /api/onboard request body. The server overrides user_profile.user_id
 *  with the session user, so what the client sends there is a placeholder. */
export interface OnboardPayload {
  user_profile: UserProfile
  timezone: string
}

export interface OnboardResult {
  user_id: string
  created: boolean
  timezone: string
  has_motivation_profile: boolean
}

export interface MeResult {
  user_id: string
  onboarded: boolean
  timezone: string | null
  email: string | null
  profile: UserProfile | null
}

/** The SPA never supplies free/busy — the server fetches it (hosted) since it
 *  needs the per-user token cipher. So only the optional knobs are sent. */
export interface ProposeRequest {
  horizon_days?: number
  recovery_mode?: string
}

/** Subset of ProposeResult the generation screen reads. A *workflow* failure
 *  arrives here as a 200 with `reason_code` set (not an ApiError). */
export interface ProposeResult {
  run_id: string
  state: string
  reason_code: ReasonCode | null
  draft_schedule_id: string | null
  draft_payload_hash: string | null
  scheduled_task_count: number
  explanation: Record<string, unknown> | null
}

/** Subset of StatusResult the UI reads; the endpoint returns more fields. */
export interface StatusResult {
  user_id: string
  onboarded: boolean
  timezone: string | null
  state: string | null
  reason_code: ReasonCode | null
  plan_version: string | null
  active_plan_version: string | null
  draft_schedule_id: string | null
  approval_event_id: string | null
}

export interface TodayTask {
  task_id: string
  title: string
  category: string
  required_focus_level: string
  start: string
  end: string
  due: boolean
  reported: boolean
}

export interface TodayResult {
  timezone: string | null
  tasks: TodayTask[]
}

export interface ThresholdFieldView {
  name: string
  value: number | boolean
  status: 'default' | 'overridden'
}

export interface ThresholdSectionView {
  name: string
  fields: ThresholdFieldView[]
}

export interface ThresholdsResult {
  sections: ThresholdSectionView[]
  history: unknown[]
}

export interface AccountabilityResult {
  has_motivation_profile: boolean
  checkin_status: string | null
  state: unknown | null
  decision: unknown | null
}
