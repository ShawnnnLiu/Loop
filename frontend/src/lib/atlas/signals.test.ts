import { describe, expect, it } from 'vitest'

import type { KnowledgeNodeView } from '../../api/types'
import { NO_SIGNALS, readSignals, sessionTrail } from './signals'

function node(overrides: Partial<KnowledgeNodeView>): Partial<KnowledgeNodeView> {
  return overrides
}

describe('atlas signals — defensive readers', () => {
  it('reads every SA-A field, camelCased', () => {
    const s = readSignals(
      node({
        sessions_total: 4,
        sessions_done: 2,
        next_session_at: '2026-07-23T09:00:00+00:00',
        evidence_label: 'talk-recording-link.md',
        evidence_confirmed_at: '2026-07-18T00:00:00+00:00',
        review_flagged: true,
        self_assessed: true,
      }),
    )
    expect(s).toEqual({
      sessionsTotal: 4,
      sessionsDone: 2,
      nextSessionAt: '2026-07-23T09:00:00+00:00',
      evidenceLabel: 'talk-recording-link.md',
      evidenceConfirmedAt: '2026-07-18T00:00:00+00:00',
      reviewFlagged: true,
      selfAssessed: true,
    })
  })

  it('coalesces missing fields to the null/false baseline (partial payload)', () => {
    // An older/partial payload with none of the SA-A fields degrades cleanly,
    // never throws — the graceful-degradation contract at the read boundary.
    expect(readSignals({})).toEqual(NO_SIGNALS)
    expect(readSignals(node({ sessions_total: 3 }))).toEqual({
      ...NO_SIGNALS,
      sessionsTotal: 3,
    })
  })

  it('treats undefined and null identically (both drop the flourish)', () => {
    expect(readSignals(node({ next_session_at: null }))).toEqual(NO_SIGNALS)
  })

  describe('sessionTrail', () => {
    it('needs both counts present to draw a trail', () => {
      expect(sessionTrail({ ...NO_SIGNALS, sessionsTotal: 4, sessionsDone: null })).toBeNull()
      expect(sessionTrail({ ...NO_SIGNALS, sessionsTotal: null, sessionsDone: 2 })).toBeNull()
      expect(sessionTrail({ ...NO_SIGNALS, sessionsTotal: 4, sessionsDone: 2 })).toEqual({
        total: 4,
        done: 2,
      })
    })

    it('drops a zero-total trail (nothing to draw)', () => {
      expect(sessionTrail({ ...NO_SIGNALS, sessionsTotal: 0, sessionsDone: 0 })).toBeNull()
    })

    it('clamps done into [0, total] so it never over-fills', () => {
      expect(sessionTrail({ ...NO_SIGNALS, sessionsTotal: 3, sessionsDone: 9 })).toEqual({
        total: 3,
        done: 3,
      })
      expect(sessionTrail({ ...NO_SIGNALS, sessionsTotal: 3, sessionsDone: -1 })).toEqual({
        total: 3,
        done: 0,
      })
    })
  })
})
