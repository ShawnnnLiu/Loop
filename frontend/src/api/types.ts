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

/** Mirror of contracts/common_types.py::EvidenceKind — the closed classification
 *  of one confirmed evidence item (NP-A). Closed for humans too: it is a join key
 *  for the deterministic narrative kernel, so the UI offers this fixed dropdown. */
export type EvidenceKind =
  | 'work'
  | 'project'
  | 'volunteering'
  | 'leadership'
  | 'research'
  | 'award'
  | 'coursework'

/** The kind enum in registry order — the dropdown source. Kept in lockstep with
 *  the backend enum; GET /api/evidence-vocabulary also returns it as the oracle. */
export const EVIDENCE_KINDS: EvidenceKind[] = [
  'work',
  'project',
  'volunteering',
  'leadership',
  'research',
  'award',
  'coursework',
]

/** Mirror of contracts/user_profile.py::ExperienceItem — one confirmed
 *  evidence entry (RI-A). `kind` + `theme_tags` are the story-layer additions
 *  (NP-A): both proposed by the intake node, both editable, both closed-vocab. */
export interface ExperienceItem {
  title: string
  organization: string | null
  summary: string | null
  kind: EvidenceKind
  theme_tags: string[]
}

/** Mirror of contracts/pathway_selection.py::SlotOverride — an explicit
 *  item→slot correction. No NP-E editing UI yet; carried so the round-trip
 *  preserves any overrides a stored profile already holds. */
export interface SlotOverride {
  item_title: string
  item_organization: string | null
  slot_id: string
}

/** Mirror of contracts/pathway_selection.py::PathwaySelection — the user's
 *  confirmed pathway, pinned to the registry version it was made against. */
export interface PathwaySelection {
  pathway_id: string
  pathway_registry_version: string
  selected_at: string
  slot_overrides: SlotOverride[]
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
  experience: ExperienceItem[]
  skills: string[]
  preferred_session_length_min: number
  max_session_length_min: number
  deep_work_windows: DeepWorkWindow[]
  hard_constraints: HardConstraints
  preferences: Preferences
  motivation_profile_id?: string | null
  /** The user's chosen narrative pathway (NP-D); null = skipped, and every
   *  downstream surface behaves exactly as before the story layer. */
  pathway_selection: PathwaySelection | null
  resume_text: string | null
  /** Optional freeform plan the user pasted ("Blind 75 first, then system
   *  design"). Strategist-only raw context — never parsed client-side. */
  plan_direction: string | null
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

// Résumé intake (RI-D). The wizard's Extract button drives one persistence-
// free POST /api/onboard/extract: the ResumeIntakeNode proposes candidates,
// the user edits them client-side, and only the finished wizard writes —
// via POST /api/onboard, the unchanged single write path.

/** Draft answers from earlier wizard steps, all optional (mirror of
 *  contracts/resume_intake_input.py::DraftProfileContext). */
export interface DraftProfileContext {
  goal?: string | null
  target_role?: string | null
  experience_level?: ExperienceLevel | null
  timeline_weeks?: number | null
  weekly_hours?: number | null
}

/** Body of POST /api/onboard/extract. The acting user is session-derived;
 *  the allowed weak-spot vocabulary is service-resolved — the client sends
 *  neither. */
export interface ExtractResumePayload {
  resume_text: string
  draft_context?: DraftProfileContext
}

/** Mirror of contracts/resume_extraction.py::ResumeExtraction — the node's
 *  schema-bound proposal. Provenance is structural, by field group:
 *  experience/skills = extracted, strengths/weak spots = inferred,
 *  company categories = suggested. No confidence values anywhere. */
export interface ResumeExtraction {
  experience: ExperienceItem[]
  skills: string[]
  known_strengths: string[]
  inferred_weak_spots: string[]
  target_company_categories: string[]
}

/** One extracted skill surface resolved onto the taxonomy (mirror of
 *  app/results.py::CanonicalSkill). `display_name` is what the wizard
 *  offers to store. */
export interface CanonicalSkill {
  skill_id: string
  display_name: string
  surface: string
}

/** Mirror of app/results.py::ExtractResumeResult. An LLM failure arrives as
 *  a 200 with status "failed" + the typed reason_code — a local, retryable
 *  UX event, not an ApiError. Out-of-vocabulary skill surfaces come back
 *  visibly flagged in `skills_unmatched`, never silently promoted. */
export interface ExtractResumeResult {
  status: 'ok' | 'failed'
  run_id: string
  user_id: string
  proposal: ResumeExtraction | null
  skills_canonical: CanonicalSkill[]
  skills_unmatched: string[]
  taxonomy_version: string | null
  reason_code: ReasonCode | null
  detail: string | null
}

// Narrative pathways (NP-D/NP-E). Every ranking and slot state below is
// reproducible by the deterministic narrative/ kernel over the stored (or draft)
// profile — no LLM output participates in any of them.

export type SlotState = 'filled' | 'partial' | 'empty'

/** Mirror of app/results.py::PathwaySlotView — one evidence slot with its
 *  kernel-computed coverage state. `matched_item_indices` point into
 *  `UserProfile.experience` so the UI can name *why* a pillar is filled. */
export interface PathwaySlotView {
  slot_id: string
  title: string
  state: SlotState
  matched_item_indices: number[]
}

/** Mirror of app/results.py::PathwayCard — one pathway with kernel-computed fit.
 *  `filled_slots`/`total_slots` are the honest "n of m pillars" count (never a
 *  score) and the card-ordering key (sorted filled_slots desc, ties by registry
 *  order server-side). The optional LLM fit note (NP-F) is served separately by
 *  POST /api/pathways/fit-notes so this card stays kernel-only. */
export interface PathwayCard {
  pathway_id: string
  display_name: string
  spine: string
  audience_note: string
  career_track: string
  filled_slots: number
  total_slots: number
  slots: PathwaySlotView[]
  selected: boolean
}

/** Mirror of app/results.py::PathwaysResult. `version_mismatch` means the stored
 *  selection is pinned to a registry version no longer served — surfaced for an
 *  explicit re-confirm, never silently re-mapped. */
export interface PathwaysResult {
  track: string | null
  registry_version: string
  selected_pathway_id: string | null
  version_mismatch: boolean
  cards: PathwayCard[]
}

/** Body of POST /api/onboard/pathways — the wizard's persistence-free draft
 *  coverage preview (nothing persists; the only write path stays onboard). */
export interface PreviewPathwaysPayload {
  user_profile: UserProfile
  track?: string | null
}

/** Mirror of app/results.py::EvidenceVocabularyResult — the closed dropdowns the
 *  UI binds evidence tagging to. `kinds` is the fixed enum; `themes` is the
 *  registry's per-track slice (empty when no track resolves). */
export interface EvidenceVocabularyResult {
  track: string | null
  registry_version: string
  kinds: EvidenceKind[]
  themes: string[]
}

/** Body of POST /api/pathways/fit-notes. `user_profile` is the wizard's
 *  not-yet-saved draft (persistence-free); omit it to note the stored profile. */
export interface FitNotesPayload {
  user_profile?: UserProfile
  track?: string | null
}

/** Mirror of app/results.py::FitNotesResult — batched LLM fit notes keyed by
 *  `pathway_id`, display-only prose that decorates the deterministic `pathways`
 *  ranking (present only for the top cards the batch covered). An LLM failure is
 *  a 200 with status "failed" + reason_code (inspected, not caught); the cards
 *  are never blocked on it. */
export interface FitNotesResult {
  status: 'ok' | 'failed'
  registry_version: string
  notes: Record<string, string>
  reason_code: string | null
  detail: string | null
}

/** Mirror of app/results.py::StorySummaryResult — the user-initiated "where your
 *  package stands" summary over the selected pathway's deterministic slot states.
 *  Display-only; `summary`/`detail` are empty on a "failed" status. */
export interface StorySummaryResult {
  status: 'ok' | 'failed'
  summary: string
  detail: string[]
  reason_code: string | null
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

/** LLM prose attachment (reflection / explanation): display copy, never
 *  control-plane — the typed reason_code stays the contract. */
export interface ProseSummary {
  summary: string
  detail: string[]
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
  explanation: ProseSummary | null
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
  /** Persisted prose for a run parked in a failure state — what the product
   *  already told the user about WHY (B5 reason-aware resume). */
  explanation: ProseSummary | null
  /** Persisted drift reflection for a parked replan (Week banner disclosure). */
  reflection: ProseSummary | null
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

/** Compact deterministic delta between the pending draft's plan and its parent
 *  plan version (D4) — computed server-side from the two persisted plans, never
 *  by an LLM and never client-side. A task counts as preserved only when its
 *  full content is identical. */
export interface PlanDiffView {
  from_plan_version: string
  to_plan_version: string
  tasks_added: number
  tasks_removed: number
  tasks_changed: number
  tasks_preserved: number
  /** Plan-wide net minutes delta; positive means more total work. */
  net_load_change_min: number
  /** One deterministic line per removed/changed/added task, in that order. */
  changes: string[]
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
  /** Content delta vs the parent plan version — present for any draft with a
   *  parent (replan, recalibration, drop); null on a fresh propose. */
  plan_diff: PlanDiffView | null
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
 *  service did with it. `reason_code` is null for unchanged; null or a
 *  non-blocking advisory (`DEPENDENCY_ADVISORY` / `OVERLAP_ADVISORY` /
 *  `DAILY_LOAD_ADVISORY`, ADR-0008/0009/0010) for `adopted`; a hard
 *  policy-bound placement code for `rejected`; and `EXTERNAL_EVENT_DELETED`
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

/** One persisted coaching note, replayed for display (D2). */
export interface ReflectionHistoryEntry {
  created_at: string
  summary: string
  detail: string[]
  plan_version: string | null
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
  /** Persisted reflections, newest first — independent of the snapshot,
   *  so history renders even from the empty accountability state. */
  reflection_history: ReflectionHistoryEntry[]
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
