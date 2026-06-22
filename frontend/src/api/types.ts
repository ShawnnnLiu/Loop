// TypeScript mirrors of the JSON the backend returns
// (agentic_calendar/app/results.py). These grow per screen; the set below is
// the F-A read surface the SPA renders from. Tz-aware datetimes arrive as ISO
// strings (the client localizes); enums arrive as their string values.

export type ReasonCode = string

/** Loosely typed for now — the onboarding wizard (F-C) types the full
 *  UserProfile and maps it onto form fields. */
export type UserProfile = Record<string, unknown>

export interface MeResult {
  user_id: string
  onboarded: boolean
  timezone: string | null
  email: string | null
  profile: UserProfile | null
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
