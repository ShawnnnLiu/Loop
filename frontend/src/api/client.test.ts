import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, api, errorMessage, setUnauthenticatedHandler } from './client'

function jsonResponse(status: number, body: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

let onUnauthenticated: ReturnType<typeof vi.fn>

beforeEach(() => {
  // Replace the default handler (which would touch window.location) with a spy.
  onUnauthenticated = vi.fn()
  setUnauthenticatedHandler(onUnauthenticated)
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('api client request handling', () => {
  it('returns the parsed body on a 200 and hits the /api-prefixed path', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { user_id: 'u_1', onboarded: true }))
    vi.stubGlobal('fetch', fetchMock)

    const me = await api.me()

    expect(me.user_id).toBe('u_1')
    expect(fetchMock).toHaveBeenCalledWith('/api/me', expect.objectContaining({ method: 'GET', credentials: 'include' }))
  })

  it('sends a JSON body with credentials on a POST', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { run_id: 'r', state: 'awaiting_user_approval', reason_code: null }))
    vi.stubGlobal('fetch', fetchMock)

    await api.propose({ horizon_days: 14 })

    expect(fetchMock).toHaveBeenCalledWith('/api/propose', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ horizon_days: 14 }),
    })
  })

  it('treats a workflow failure (200 + reason_code) as a normal result, not an error', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(200, { state: 'error_requires_user', reason_code: 'INSUFFICIENT_WEEKLY_CAPACITY' })))

    const result = await api.propose()

    expect(result.reason_code).toBe('INSUFFICIENT_WEEKLY_CAPACITY')
  })

  it('redirects (via the handler) and throws ApiError(401) on an unauthenticated response', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(401, { detail: 'not authenticated' })))

    await expect(api.me()).rejects.toMatchObject({ status: 401 })
    expect(onUnauthenticated).toHaveBeenCalledOnce()
  })

  it('throws ApiError carrying status + body on a 409 precondition failure', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(409, { error: 'bad state', type: 'CycleError' })))

    await expect(api.status()).rejects.toBeInstanceOf(ApiError)
    await expect(api.status()).rejects.toMatchObject({
      status: 409,
      body: { error: 'bad state', type: 'CycleError' },
    })
    expect(onUnauthenticated).not.toHaveBeenCalled()
  })

  it('setCalendarSync posts the opt-in flag and reads back the refreshed me', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, { user_id: 'u_1', onboarded: true, inbound_calendar_sync_enabled: true }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const me = await api.setCalendarSync(true)

    expect(me.inbound_calendar_sync_enabled).toBe(true)
    expect(fetchMock).toHaveBeenCalledWith('/api/calendar-sync', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: true }),
    })
  })

  it('extractResume posts the résumé + draft context and returns an LLM failure as a normal result', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, {
        status: 'failed',
        run_id: 'intake-run_1',
        user_id: 'u_1',
        proposal: null,
        skills_canonical: [],
        skills_unmatched: [],
        taxonomy_version: null,
        reason_code: 'LLM_RETRY_LIMIT_EXCEEDED',
        detail: 'transport failed after retries',
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const payload = {
      resume_text: 'x'.repeat(60),
      draft_context: { goal: null, target_role: 'Backend SWE' },
    }
    const result = await api.extractResume(payload)

    expect(result.status).toBe('failed')
    expect(result.reason_code).toBe('LLM_RETRY_LIMIT_EXCEEDED')
    expect(fetchMock).toHaveBeenCalledWith('/api/onboard/extract', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  })

  it('pathways / evidenceVocabulary encode the optional query param, omitting it when absent', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { cards: [], kinds: [], themes: [] }))
    vi.stubGlobal('fetch', fetchMock)

    await api.pathways()
    await api.pathways('ai_engineer')
    await api.evidenceVocabulary('Backend SWE')

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/pathways', expect.objectContaining({ method: 'GET' }))
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/pathways?track=ai_engineer',
      expect.objectContaining({ method: 'GET' }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      '/api/evidence-vocabulary?role=Backend%20SWE',
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('selectPathway posts the id and markEvidence posts the tagged item', async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { user_id: 'u_1', onboarded: true }))
    vi.stubGlobal('fetch', fetchMock)

    await api.selectPathway('backend-infrastructure-engineer')
    await api.markEvidence({ title: 'Shelter app', kind: 'volunteering', theme_tags: ['community'] })

    expect(fetchMock).toHaveBeenNthCalledWith(1, '/api/pathways/select', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pathway_id: 'backend-infrastructure-engineer' }),
    })
    expect(fetchMock).toHaveBeenNthCalledWith(2, '/api/evidence', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: 'Shelter app', kind: 'volunteering', theme_tags: ['community'] }),
    })
  })

  it('reconcile posts an empty body and returns the typed reconciliation result', async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, { run_id: 'run_1', outcome: 'sync_disabled', deltas: [] }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const result = await api.reconcile()

    expect(result.outcome).toBe('sync_disabled')
    expect(fetchMock).toHaveBeenCalledWith('/api/reconcile', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
  })
})

describe('errorMessage', () => {
  it('prefers the {error} field a CycleError/ValidationError returns', () => {
    expect(errorMessage(new ApiError(409, { error: 'no active plan', type: 'CycleError' }))).toBe('no active plan')
  })

  it('falls back to {detail} (FastAPI body validation)', () => {
    expect(errorMessage(new ApiError(422, { detail: 'field required' }))).toBe('field required')
  })

  it('reports the status when the body has no message', () => {
    expect(errorMessage(new ApiError(500, null))).toBe('Request failed (500)')
  })

  it('handles plain Errors and unknown values', () => {
    expect(errorMessage(new Error('boom'))).toBe('boom')
    expect(errorMessage('weird')).toBe('Something went wrong')
  })
})
