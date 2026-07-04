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
  /** Opt-in to inbound calendar reconciliation (adopt the user's own edits to
   *  Loop's events). Off by default — axiom 06 keeps the in-app schedule the
   *  system of record, so treating an external edit as authoritative is opt-in. */
  inbound_calendar_sync_enabled: boolean
}

/** The SPA never supplies free/busy — the server fetches it (hosted) since it
 *  needs the per-user token cipher. So only the optional knobs are sent. */
export interface ProposeRequest {
  horizon_days?: number
  recovery_mode?: string
}

/** One typed, structured violation from a terminal validation failure
 *  (mirror of contracts/validation_result.py::Violation). `details` holds
 *  deterministic numeric facts; the client formats them into a specific
 *  recovery message. `type` is the contract surface (a ViolationType value). */
export interface Violation {
  type: string
  task_id: string | null
  module_id: string | null
  details: Record<string, unknown>
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
  violations: Violation[]
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
  replan_kind: 'recovery' | 'recalibration' | null
  recovery_mode: string | null
  /** REPLAN_REQUIRED on the recovery path with no mode resolved (the profile
   *  says ask_each_time): propose 409s until the client supplies a mode, so
   *  the Week screen renders the picker instead of a bare CTA. */
  recovery_mode_pending_user_choice: boolean
}

export interface DraftScheduleEntry {
  task_id: string
  start: string // ISO, tz-aware
  end: string
  calendar_event_status: string
}

export interface DraftSchedule {
  draft_schedule_id: string
  plan_version: string
  entries: DraftScheduleEntry[]
}

export interface FreeBusyInterval {
  start: string
  end: string
}

export interface DraftView {
  draft: DraftSchedule | null
  payload_hash: string | null
  hash_canonicalization_version: string
  free_busy: FreeBusyInterval[]
  task_titles: Record<string, string>
  /** Tasks whose calendar event the user deleted externally (durable
   *  `event_deleted` memory, scoped to the draft's plan version). Rendered as a
   *  distinct "deleted from calendar" state — never the written checkmark; the
   *  task itself is still planned. */
  deleted_task_ids: string[]
}

/** A single move sent to /api/adjust; the server derives `end` from the
 *  original duration (a move can relocate a block but never resize it). */
export interface DraftAdjustment {
  task_id: string
  start: string // ISO, tz-aware
}

export interface AdjustViolation {
  task_id: string
  reason_code: ReasonCode
  detail: string
}

export interface AdjustResult {
  run_id: string
  state: string
  applied: boolean
  reason_code: ReasonCode | null
  draft_schedule_id: string | null
  draft_payload_hash: string | null
  adjusted_task_ids: string[]
  scheduled_task_count: number
  violations: AdjustViolation[]
}

// Inbound calendar reconciliation (mirror of
// contracts/calendar_reconciliation.py). The engine detects the user's own
// edits to Loop's events on their Google Calendar (move / resize / delete) and
// ADOPTS valid edits into a fresh draft of the same plan version — read-only
// against the calendar, it never writes back. Off unless opted in (axiom 06).
export type CalendarEditType = 'unchanged' | 'moved' | 'resized' | 'deleted'
export type ReconciliationDisposition = 'unchanged' | 'adopted' | 'rejected' | 'flagged_deleted'
export type ReconciliationOutcome =
  | 'sync_disabled'
  | 'deferred'
  | 'no_change'
  | 'adopted'
  | 'flagged'
  | 'mixed'

/** One mapped task's recorded-vs-observed difference and what the deterministic
 *  service did with it. `reason_code` is null for adopted/unchanged, one of the
 *  drag-to-adjust placement codes for `rejected`, and `EXTERNAL_EVENT_DELETED`
 *  for `flagged_deleted` (observed_* are null when the event was deleted). */
export interface CalendarEventDelta {
  task_id: string
  calendar_event_id: string | null
  change_type: CalendarEditType
  recorded_start: string
  recorded_end: string
  observed_start: string | null
  observed_end: string | null
  disposition: ReconciliationDisposition
  reason_code: ReasonCode | null
}

export interface CalendarReconciliationResult {
  run_id: string
  plan_version: string
  reconciled_at: string
  target_calendar_id: string
  outcome: ReconciliationOutcome
  /** Non-null iff the outcome adopted ≥1 move (`adopted` / `mixed`) — the new
   *  draft to refetch so the Week grid shows the adopted times. */
  adopted_draft_schedule_id: string | null
  deltas: CalendarEventDelta[]
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
  /** The user deleted this task's calendar event externally (`event_deleted`).
   *  The task is still planned and can still be checked in — deleted is a
   *  distinct state, never shown as completion. */
  deleted: boolean
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

/** Mirror of contracts/threshold_change_log.py::ThresholdChange. Append-only
 *  journal of every effective tuning change (axiom 07). */
export interface ThresholdChange {
  config_section: string
  threshold_field: string
  prior_value: number
  new_value: number
  effective_at: string // ISO, tz-aware
  justification: string
  dataset_reference: string
}

export interface ThresholdsResult {
  sections: ThresholdSectionView[]
  history: ThresholdChange[]
}

/** Subset of contracts/accountability_state.py::AccountabilityState the
 *  dashboard reads (the full state carries more deterministic fields). */
export interface AccountabilityState {
  completion_rate_7d: number
  completion_rate_14d: number
  missed_tasks_7d: number
  reschedule_count_7d: number
  behind_schedule_percent: number
  current_status: string
  sponsor_report_allowed: boolean
}

/** Subset of InterventionDecision — the chosen deterministic intervention. */
export interface InterventionDecision {
  action: string | null
  reason_code: ReasonCode | null
  sponsor_action: string | null
}

export interface AccountabilityResult {
  has_motivation_profile: boolean
  checkin_status: string | null
  state: AccountabilityState | null
  decision: InterventionDecision | null
  /** The weekly check-in is due or missed — render the check-in card. */
  checkin_due: boolean
  /** The latest unanswered recommitment ask — render the recommit card. */
  open_recommitment_request_id: string | null
}

export type RecommitChoice = 'keep_plan' | 'revise_timeline' | 'revise_intensity' | 'revise_goal'

/** Mirror of RecommitResult: the typed answer to a recommitment ask.
 *  `replan_required` means the choice parked (or re-aimed) a recovery replan —
 *  the draft still goes through review + approval. */
export interface RecommitResult {
  user_id: string
  recommitment_request_id: string
  recommitment_event_id: string
  choice: RecommitChoice
  recovery_mode: string | null
  replan_required: boolean
  state: string | null
}

/** Mirror of WeeklyCheckinResult. Counts are server-computed. */
export interface WeeklyCheckinResult {
  user_id: string
  checkin_id: string
  checkin_status: string
  week_start: string // ISO date
  week_end: string
  scheduled_task_count: number
  completed_task_count: number
}

/** Mirror of ApproveResult. `approval_event_id` + `approved_payload_hash` are
 *  the proof the write gate requires; the server, not the client, holds them. */
export interface ApproveResult {
  run_id: string
  user_id: string
  state: string
  rejected: boolean
  plan_version: string
  approval_event_id: string | null
  approved_payload_hash: string | null
  expires_at_iso: string | null
}

/** Mirror of WriteCycleResult. A failed write (e.g. verification) arrives here
 *  as a 200 with `reason_code` set. The engine does not auto-roll-back:
 *  unverified events are flagged VERIFICATION_FAILED and left on the calendar,
 *  and the plan is not activated. Recovery is explicit and user-triggered —
 *  `/rollback` removes the written events, `/retry-write` re-creates the
 *  missing ones (both re-gated server-side). The client only reports typed
 *  outcomes and triggers those routes; it never touches the calendar itself. */
export interface WriteCycleResult {
  run_id: string
  user_id: string
  state: string
  dry_run: boolean
  write_status: string | null
  reason_code: ReasonCode | null
  planned_event_count: number
  written_task_ids: string[]
  verified_task_ids: string[]
  failed_task_ids: string[]
  mapping_status_by_task: Record<string, string>
  error: string | null
}

/** Mirror of RollbackCycleResult: the outcome of a user-triggered rollback of
 *  a failed write. `dry_run` responses carry only the would-delete count (for
 *  the confirmation dialog). A completed rollback moves the run to
 *  `error_requires_user`; a partial one stays in `calendar_write_failed` so
 *  recovery can be retried. */
export interface RollbackResult {
  run_id: string
  user_id: string
  state: string
  dry_run: boolean
  rollbackable_event_count: number
  deleted_event_ids: string[]
  failed_event_ids: string[]
  fully_rolled_back: boolean | null
  reason_code: ReasonCode | null
  error: string | null
}

/** Subset of IngestResult the check-in flow reads back (the full result carries
 *  drift/accountability fields the steady-state surfaces don't render yet). */
export interface CheckinResult {
  user_id: string
  ingested_count: number
  duplicate_count: number
  rejected_count: number
  plan_completed: boolean
}
