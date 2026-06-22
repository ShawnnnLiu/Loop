import type {
  AccountabilityResult,
  MeResult,
  StatusResult,
  ThresholdsResult,
  TodayResult,
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
  today: () => request<TodayResult>('GET', '/today'),
  thresholds: () => request<ThresholdsResult>('GET', '/thresholds'),
  accountability: () => request<AccountabilityResult>('GET', '/accountability'),
}
