import type {
  AccountabilityResult,
  AdjustResult,
  ApproveResult,
  CalendarReconciliationResult,
  CheckinResult,
  DraftAdjustment,
  DraftView,
  EvidenceKind,
  EvidenceVocabularyResult,
  ExtractResumePayload,
  ExtractResumeResult,
  MeResult,
  OnboardPayload,
  OnboardResult,
  PathwaysResult,
  PreviewPathwaysPayload,
  ProposeRequest,
  ProposeResult,
  RecommitChoice,
  RecommitResult,
  RollbackResult,
  StatusResult,
  ThresholdsResult,
  TodayResult,
  WeeklyCheckinResult,
  WriteCycleResult,
} from './types'

/** A non-OK HTTP response from the API (4xx/5xx). A *workflow* failure is NOT
 *  an ApiError — the backend returns those as 200 with a typed `reason_code`
 *  in the body, so callers inspect the result instead of catching. ApiError is
 *  for precondition failures (409), bad requests (422), and transport faults. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: unknown,
  ) {
    super(`API request failed (${status})`)
    this.name = 'ApiError'
  }
}

/** The server-side OAuth entry point — a full-page redirect, not a fetch. */
export const LOGIN_URL = '/auth/login'

let onUnauthenticated: () => void = () => {
  window.location.assign(LOGIN_URL)
}

/** Override how a 401 is handled (the default sends the browser to login).
 *  Used in tests and could drive an in-app "session expired" surface later. */
export function setUnauthenticatedHandler(handler: () => void): void {
  onUnauthenticated = handler
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    credentials: 'include',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  // A 401 means the session is gone (or never existed); hand off to login.
  if (response.status === 401) {
    onUnauthenticated()
    throw new ApiError(401, null)
  }

  const data: unknown =
    response.status === 204 ? null : await response.json().catch(() => null)

  if (!response.ok) {
    throw new ApiError(response.status, data)
  }
  return data as T
}

// Read projections (F-A). Mutations (onboard / propose / adjust / approve /
// write / checkin) are added to this surface by the screens that drive them.
export const api = {
  me: () => request<MeResult>('GET', '/me'),
  status: () => request<StatusResult>('GET', '/status'),
  draft: () => request<DraftView>('GET', '/draft'),
  adjust: (adjustments: DraftAdjustment[]) =>
    request<AdjustResult>('POST', '/adjust', { adjustments }),
  today: () => request<TodayResult>('GET', '/today'),
  thresholds: () => request<ThresholdsResult>('GET', '/thresholds'),
  accountability: () => request<AccountabilityResult>('GET', '/accountability'),
  onboard: (payload: OnboardPayload) => request<OnboardResult>('POST', '/onboard', payload),
  // Résumé intake (RI-D): persistence-free extraction behind the wizard's
  // explicit Extract button. An LLM failure is a 200 with status "failed" +
  // typed reason_code (inspected, not caught); only a contract-invalid
  // payload 422s. Nothing is stored until the wizard finishes via onboard.
  extractResume: (payload: ExtractResumePayload) =>
    request<ExtractResumeResult>('POST', '/onboard/extract', payload),
  // Narrative pathways (NP-D/NP-E), all kernel-computed, no LLM. `pathways`
  // reads coverage over the stored profile; `previewPathways` is the wizard's
  // persistence-free draft coverage (nothing stored). `evidenceVocabulary`
  // serves the closed kind/theme dropdowns (onboarding not required — the wizard
  // passes its not-yet-saved target_role). `selectPathway` is a targeted
  // selection mutation (a pathway change invalidates the plan server-side, like
  // onboard) and `markEvidence` appends one confirmed evidence item; both return
  // the refreshed me projection.
  pathways: (track?: string) =>
    request<PathwaysResult>('GET', track ? `/pathways?track=${encodeURIComponent(track)}` : '/pathways'),
  previewPathways: (payload: PreviewPathwaysPayload) =>
    request<PathwaysResult>('POST', '/onboard/pathways', payload),
  evidenceVocabulary: (role?: string) =>
    request<EvidenceVocabularyResult>(
      'GET',
      role ? `/evidence-vocabulary?role=${encodeURIComponent(role)}` : '/evidence-vocabulary',
    ),
  selectPathway: (pathwayId: string) =>
    request<MeResult>('POST', '/pathways/select', { pathway_id: pathwayId }),
  markEvidence: (item: {
    title: string
    organization?: string | null
    summary?: string | null
    kind: EvidenceKind
    theme_tags: string[]
  }) => request<MeResult>('POST', '/evidence', item),
  propose: (body: ProposeRequest = {}) => request<ProposeResult>('POST', '/propose', body),
  // Approval gate (F-F). `approve` records the explicit decision and mints the
  // approval_event_id + hash the write requires; `write` is the only call that
  // touches a calendar. The target calendar is server-derived in hosted mode —
  // the client never names it (a body cannot redirect the write).
  approve: (reject = false) => request<ApproveResult>('POST', '/approve', { reject }),
  write: () => request<WriteCycleResult>('POST', '/write', {}),
  // Write-failure recovery (B1). Both are valid only while the run sits in
  // calendar_write_failed (409 otherwise) and re-gated server-side: rollback
  // deletes by recorded mapping ids; retry re-runs the approved-hash recheck
  // before creating only the confirmed-missing events. `rollback(true)` is the
  // dry-run that feeds the confirmation dialog's event count.
  rollback: (dryRun = false) =>
    request<RollbackResult>('POST', '/rollback', { dry_run: dryRun }),
  retryWrite: () => request<WriteCycleResult>('POST', '/retry-write', {}),
  // Check-in (F-G): completion telemetry, guarded server-side (due + idempotent).
  checkin: (taskId: string, outcome: 'complete' | 'missed') =>
    request<CheckinResult>('POST', '/checkin', { task_id: taskId, outcome }),
  // Inbound calendar reconciliation (R-e). `setCalendarSync` flips the opt-in and
  // returns the refreshed me projection. `reconcile` is an on-demand, read-only
  // pull that adopts the user's valid edits to Loop's events; it 409s when no
  // plan is active and returns `sync_disabled` when the opt-in is off, so the
  // Week screen only calls it for an active plan with the opt-in on.
  setCalendarSync: (enabled: boolean) =>
    request<MeResult>('POST', '/calendar-sync', { enabled }),
  reconcile: () => request<CalendarReconciliationResult>('POST', '/reconcile', {}),
  // Accountability loop (B3): answer the open recommitment ask with a typed
  // choice; submit the weekly check-in (counts are server-computed — the
  // client contributes only optional blockers prose).
  recommit: (choice: RecommitChoice) =>
    request<RecommitResult>('POST', '/recommit', { choice }),
  weeklyCheckin: (blockers?: string) =>
    request<WeeklyCheckinResult>('POST', '/weekly-checkin', {
      blockers: blockers?.trim() ? blockers.trim() : null,
    }),
}

/** Best-effort human message out of an ApiError body (the ValidationError
 *  handler returns {error, type}; FastAPI body-validation returns {detail}). */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const body = error.body
    if (body && typeof body === 'object') {
      const record = body as Record<string, unknown>
      if (typeof record.error === 'string') return record.error
      if (typeof record.detail === 'string') return record.detail
    }
    return `Request failed (${error.status})`
  }
  return error instanceof Error ? error.message : 'Something went wrong'
}
