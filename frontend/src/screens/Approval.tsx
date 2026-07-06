import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, api, errorMessage } from '../api/client'
import type { DraftView, RollbackResult, WriteCycleResult } from '../api/types'
import type { WriteFailureInfo } from '../lib/approval'
import {
  failureInfoFromRecovery,
  failureInfoFromResult,
  rollbackConfirmMessage,
  rollbackOutcomeMessage,
  shortHash,
  toWriteBlocks,
  writeOutcome,
} from '../lib/approval'
import { planDiffLine } from '../lib/review'

// The approval gate — the ONLY place the product writes to a calendar. The
// backend gate (approval event, payload-hash recheck, write, per-event
// verification) is already complete; this is purely its UI.
//
// Approve -> POST /api/approve (mints approval_event_id + approved_payload_hash)
// then POST /api/write. The write re-checks the approved hash against the live
// draft under the recorded canonicalization version; if the plan changed, it is
// refused server-side. We render the outcome from the server's truth: N/N
// verified activates the plan; on a typed reason_code the write FAILED — the
// engine does NOT auto-roll-back, so we report honestly what landed and what
// didn't (see writeFailureMessage) and offer the two explicit, server-gated
// recovery actions: retry the missing events (/retry-write, hash rechecked
// again) or remove everything the write created (/rollback, behind its own
// count-naming confirmation because deleting calendar events is destructive).

type Phase =
  | { kind: 'gate' } // idle: blocks shown, gate not opened
  | { kind: 'confirm' } // the confirm modal is open
  | { kind: 'writing' } // approve + write (or retry-write) in flight
  | { kind: 'verified'; result: WriteCycleResult }
  | { kind: 'failed'; info: WriteFailureInfo }
  | { kind: 'rollbackConfirm'; info: WriteFailureInfo; count: number }
  | { kind: 'rollingBack' }
  | { kind: 'rolledBack'; result: RollbackResult }
  | { kind: 'error'; message: string }

export function ApprovalScreen({ email }: { email: string | null }) {
  const navigate = useNavigate()
  const [view, setView] = useState<DraftView | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [phase, setPhase] = useState<Phase>({ kind: 'gate' })

  useEffect(() => {
    let active = true
    async function load() {
      try {
        const [v, status] = await Promise.all([api.draft(), api.status()])
        if (!active) return
        setView(v)
        // A run already parked in the write-failure state (e.g. the user
        // navigated here via the Week screen's "Recover" CTA, or reloaded):
        // open straight onto the recovery card. The dry-run supplies the
        // removable-event count the card and confirm dialog name.
        if (status.state === 'calendar_write_failed') {
          const preview = await api.rollback(true)
          if (!active) return
          setPhase({
            kind: 'failed',
            info: failureInfoFromRecovery(
              status.reason_code,
              preview.rollbackable_event_count,
            ),
          })
        }
        setLoading(false)
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return
        if (active) {
          setLoadError(errorMessage(err))
          setLoading(false)
        }
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [])

  async function confirmWrite() {
    setPhase({ kind: 'writing' })
    try {
      // Two server calls, both subject to the gate: approve mints the
      // approval_event_id + hash; write re-checks that hash and verifies.
      await api.approve(false)
      const result = await api.write()
      // A failed write is a 200 with reason_code set (verification, hash
      // mismatch, transient calendar error). The engine does NOT roll back on
      // its own — the failed card offers retry/rollback as explicit choices.
      setPhase(
        writeOutcome(result) === 'failed'
          ? { kind: 'failed', info: failureInfoFromResult(result) }
          : { kind: 'verified', result },
      )
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return // redirected to login
      setPhase({ kind: 'error', message: errorMessage(err) })
    }
  }

  async function retryMissing() {
    setPhase({ kind: 'writing' })
    try {
      // Server-gated: only valid from calendar_write_failed, and the
      // approved-hash recheck runs again before any event is created.
      const result = await api.retryWrite()
      setPhase(
        writeOutcome(result) === 'failed'
          ? { kind: 'failed', info: failureInfoFromResult(result) }
          : { kind: 'verified', result },
      )
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return
      setPhase({ kind: 'error', message: errorMessage(err) })
    }
  }

  async function openRollbackConfirm(info: WriteFailureInfo) {
    try {
      // Dry-run: the server reports exactly how many events a rollback would
      // delete; the confirmation names that count before anything happens.
      const preview = await api.rollback(true)
      setPhase({ kind: 'rollbackConfirm', info, count: preview.rollbackable_event_count })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return
      setPhase({ kind: 'error', message: errorMessage(err) })
    }
  }

  async function runRollback() {
    setPhase({ kind: 'rollingBack' })
    try {
      const result = await api.rollback()
      setPhase({ kind: 'rolledBack', result })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return
      setPhase({ kind: 'error', message: errorMessage(err) })
    }
  }

  if (loading) return <div className="screen-center muted">Loading your draft…</div>
  if (loadError) return <div className="screen-center">Couldn’t load the draft — {loadError}</div>

  const blocks = view ? toWriteBlocks(view) : []
  if (blocks.length === 0) {
    return (
      <div className="screen-center col" style={{ gap: 12 }}>
        <h2 className="t-h2">No draft to approve yet</h2>
        <p className="muted">Build a plan and adjust it, then come back to write it to your calendar.</p>
        <button className="btn btn-primary" type="button" onClick={() => navigate('/plan')}>
          Build a plan →
        </button>
      </div>
    )
  }

  const target = email ? `Google Calendar · ${email}` : 'your dedicated Google Calendar'

  return (
    <div className="approve-wrap">
      <div className="approve-left col" style={{ gap: 13 }}>
        <div>
          <span className="label">Ready to schedule</span>
          <h2 className="t-h2" style={{ marginTop: 7 }}>
            {blocks.length} {blocks.length === 1 ? 'block' : 'blocks'} to write this cycle
          </h2>
          <p className="muted" style={{ fontSize: 13.5, marginTop: 3 }}>
            You’ve arranged these. The next step is the only place Loop writes to your calendar.
          </p>
          {view?.plan_diff && (
            // Replan/drop drafts approve as a delta (D4): the deterministic
            // server-computed diff vs the plan the user already approved.
            <p style={{ fontSize: 13, marginTop: 6, color: 'var(--clay-deep)' }}>
              {planDiffLine(view.plan_diff)}
            </p>
          )}
        </div>
        <div className="card" style={{ padding: '8px 10px' }}>
          {blocks.map((b, i) => (
            <div
              key={b.taskId}
              className="row"
              style={{
                justifyContent: 'space-between',
                padding: '9px 8px',
                borderBottom: i < blocks.length - 1 ? '1px solid var(--line)' : 'none',
              }}
            >
              <div className="row" style={{ gap: 10, minWidth: 0 }}>
                <span className="mono" style={{ fontSize: 12, color: 'var(--muted)', width: 120, flex: 'none' }}>
                  {b.when}
                </span>
                <span style={{ fontSize: 14, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {b.title}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="approve-right col" style={{ gap: 14 }}>
        <div className="card soft" style={{ padding: '16px 18px' }}>
          <div className="label" style={{ marginBottom: 8 }}>
            The approval gate
          </div>
          <p style={{ fontSize: 13, color: 'var(--ink-soft)', lineHeight: 1.5 }}>
            No silent writes. Loop never touches your calendar without an explicit approval and a
            payload-hash recheck, and verifies every event after writing.
          </p>
          <button
            className="btn btn-primary lg"
            type="button"
            style={{ width: '100%', marginTop: 14 }}
            // Disabled once a write ran (or a parked failure was detected):
            // approve would 409 outside AWAITING_USER_APPROVAL — the recovery
            // card, not this gate, owns the next step.
            disabled={phase.kind !== 'gate' && phase.kind !== 'confirm'}
            onClick={() => setPhase({ kind: 'confirm' })}
          >
            Review &amp; write to calendar →
          </button>
        </div>

        {phase.kind === 'verified' && (
          <div className="card" style={{ padding: '16px 18px', borderColor: 'var(--sage)', background: 'var(--sage-soft)' }}>
            <span className="verify-pill ok">
              {phase.result.verified_task_ids.length} / {phase.result.planned_event_count} verified
            </span>
            <div style={{ fontSize: 13.5, color: 'var(--ink-soft)', marginTop: 10, lineHeight: 1.5 }}>
              Written to <b>{target}</b> and confirmed present on Google Calendar.
            </div>
            <button className="btn btn-soft sm" type="button" style={{ marginTop: 12 }} onClick={() => navigate('/today')}>
              Go to Today →
            </button>
          </div>
        )}

        {(phase.kind === 'failed' || phase.kind === 'rollbackConfirm') && (
          <div className="err-card">
            {(() => {
              const info = phase.info
              return (
                <>
                  <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                    <span className="err-code">{info.reasonCode ?? 'CALENDAR_WRITE_FAILED'}</span>
                    {info.pill && <span className="verify-pill bad">{info.pill}</span>}
                  </div>
                  <div style={{ fontSize: 13.5, color: 'var(--ink-2)', marginTop: 10, lineHeight: 1.5 }}>
                    {info.message}
                  </div>
                  <div className="col" style={{ gap: 8, marginTop: 12 }}>
                    <button className="btn btn-primary sm" type="button" onClick={() => void retryMissing()}>
                      Retry the missing events →
                    </button>
                    {info.removable && (
                      <button
                        className="btn btn-soft sm"
                        type="button"
                        onClick={() => void openRollbackConfirm(info)}
                      >
                        Remove the events that were written…
                      </button>
                    )}
                    <button className="btn btn-quiet sm" type="button" onClick={() => navigate('/review')}>
                      Back to the draft
                    </button>
                  </div>
                </>
              )
            })()}
          </div>
        )}

        {phase.kind === 'rollingBack' && (
          <div className="card" style={{ padding: '16px 18px' }}>
            <span className="spin" style={{ width: 12, height: 12, marginRight: 7 }} />
            Removing the written events…
          </div>
        )}

        {phase.kind === 'rolledBack' && (
          <div
            className="card"
            style={
              phase.result.fully_rolled_back
                ? { padding: '16px 18px', borderColor: 'var(--sage)', background: 'var(--sage-soft)' }
                : { padding: '16px 18px' }
            }
          >
            <span className="label">
              {phase.result.fully_rolled_back ? 'Events removed' : 'Rollback incomplete'}
            </span>
            <div style={{ fontSize: 13.5, color: 'var(--ink-soft)', marginTop: 10, lineHeight: 1.5 }}>
              {rollbackOutcomeMessage(phase.result)}
            </div>
            <div className="row" style={{ gap: 8, marginTop: 12 }}>
              {phase.result.fully_rolled_back ? (
                <button className="btn btn-primary sm" type="button" onClick={() => navigate('/plan')}>
                  Build a new plan →
                </button>
              ) : (
                // The destructive intent was already confirmed; this retries
                // deleting only what the first pass couldn't remove.
                <button className="btn btn-primary sm" type="button" onClick={() => void runRollback()}>
                  Try removing them again
                </button>
              )}
            </div>
          </div>
        )}

        {phase.kind === 'error' && (
          <div className="banner-error">
            Couldn’t complete the write — {phase.message}
          </div>
        )}
      </div>

      {phase.kind === 'rollbackConfirm' && (
        <div className="scrim">
          <div className="modal">
            <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--line)' }}>
              <span className="label">Confirm removal</span>
              <h3 className="t-h3" style={{ marginTop: 7 }}>
                Remove {phase.count} {phase.count === 1 ? 'event' : 'events'} from Google Calendar?
              </h3>
            </div>
            <div style={{ padding: '18px 24px' }}>
              <p style={{ fontSize: 13.5, color: 'var(--ink-soft)', lineHeight: 1.5 }}>
                {rollbackConfirmMessage(phase.count)}
              </p>
              <div className="guard">
                <span>🔒</span>
                <span>
                  Only events this write created are deleted — matched by their recorded ids,
                  never by title or time.
                </span>
              </div>
            </div>
            <div
              className="row"
              style={{
                justifyContent: 'flex-end',
                gap: 10,
                padding: '14px 24px',
                borderTop: '1px solid var(--line)',
                background: 'var(--paper-2)',
              }}
            >
              <button
                className="btn btn-quiet"
                type="button"
                onClick={() => setPhase({ kind: 'failed', info: phase.info })}
              >
                Cancel
              </button>
              <button className="btn btn-primary" type="button" onClick={() => void runRollback()}>
                Remove {phase.count === 1 ? 'the event' : `${phase.count} events`} →
              </button>
            </div>
          </div>
        </div>
      )}

      {(phase.kind === 'confirm' || phase.kind === 'writing') && (
        <div className="scrim">
          <div className="modal">
            <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--line)' }}>
              <span className="label">Confirm calendar write</span>
              <h3 className="t-h3" style={{ marginTop: 7 }}>
                Write {blocks.length} {blocks.length === 1 ? 'block' : 'blocks'} to Google Calendar?
              </h3>
            </div>
            <div style={{ padding: '18px 24px' }}>
              <div className="cfg-row">
                <div className="cl">Target calendar</div>
                <span className="chip" style={{ cursor: 'default' }}>
                  {target}
                </span>
              </div>
              <div className="cfg-row">
                <div className="cl">Events to create</div>
                <span style={{ fontWeight: 600 }}>{blocks.length}</span>
              </div>
              <div className="cfg-row">
                <div className="cl">Payload hash</div>
                <span className="mono" style={{ fontSize: 12, color: 'var(--muted)' }}>
                  {shortHash(view?.payload_hash ?? null)}
                </span>
              </div>
              <div className="cfg-row" style={{ borderBottom: 'none' }}>
                <div className="cl">After write</div>
                <span style={{ fontSize: 13, color: 'var(--ink-soft)' }}>each event re-read &amp; verified</span>
              </div>
              <div className="guard">
                <span>🔒</span>
                <span>
                  This is the only action that writes to your calendar. The hash is rechecked at write
                  time; if your plan changed, the write is refused.
                </span>
              </div>
            </div>
            <div
              className="row"
              style={{
                justifyContent: 'flex-end',
                gap: 10,
                padding: '14px 24px',
                borderTop: '1px solid var(--line)',
                background: 'var(--paper-2)',
              }}
            >
              <button
                className="btn btn-quiet"
                type="button"
                disabled={phase.kind === 'writing'}
                onClick={() => setPhase({ kind: 'gate' })}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                type="button"
                disabled={phase.kind === 'writing'}
                onClick={() => void confirmWrite()}
              >
                {phase.kind === 'writing' ? (
                  <>
                    <span className="spin" style={{ width: 12, height: 12, marginRight: 7 }} />
                    Writing…
                  </>
                ) : (
                  'Approve write →'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
