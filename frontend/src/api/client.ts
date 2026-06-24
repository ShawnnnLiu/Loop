import type {
  AccountabilityResult,
  AdjustResult,
  ApproveResult,
  CheckinResult,
  DraftAdjustment,
  DraftView,
  MeResult,
  OnboardPayload,
  OnboardResult,
  ProposeRequest,
  ProposeResult,
  StatusResult,
  ThresholdsResult,
  TodayResult,
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
  propose: (body: ProposeRequest = {}) => request<ProposeResult>('POST', '/propose', body),
  // Approval gate (F-F). `approve` records the explicit decision and mints the
  // approval_event_id + hash the write requires; `write` is the only call that
  // touches a calendar. The target calendar is server-derived in hosted mode —
  // the client never names it (a body cannot redirect the write).
  approve: (reject = false) => request<ApproveResult>('POST', '/approve', { reject }),
  write: () => request<WriteCycleResult>('POST', '/write', {}),
  // Abandon a run whose write failed so the user can start over (the SPA's only
  // non-operator exit from CALENDAR_WRITE_FAILED). Does not touch the calendar.
  discard: () => request<ApproveResult>('POST', '/discard', {}),
  // Check-in (F-G): completion telemetry, guarded server-side (due + idempotent).
  checkin: (taskId: string, outcome: 'complete' | 'missed') =>
    request<CheckinResult>('POST', '/checkin', { task_id: taskId, outcome }),
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
