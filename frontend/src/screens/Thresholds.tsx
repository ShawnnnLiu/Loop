import { useEffect, useState } from 'react'

import { ApiError, api, errorMessage } from '../api/client'
import type { MeResult, PathwaysResult, ThresholdsResult } from '../api/types'
import { fmtWhen } from '../lib/datetime'
import { PathwayCardView } from '../components/PathwayCard'

// Thresholds: a read-only mirror of the effective deterministic tuning the
// system serves, plus the append-only change journal. Display-only by design
// (axiom 07): tuning values change ONLY via tuning.toml -> apply_tuning, which
// journals every effective change. The UI never edits — there is no write path
// here. Each value is tagged default vs. overridden against the code default;
// all values are heuristic priors pending calibration.

function fmtValue(value: number | boolean): string {
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return String(value)
}

export function ThresholdsScreen() {
  const [result, setResult] = useState<ThresholdsResult | null>(null)
  const [me, setMe] = useState<MeResult | null>(null)
  const [pathways, setPathways] = useState<PathwaysResult | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [syncing, setSyncing] = useState(false)
  const [syncError, setSyncError] = useState<string | null>(null)
  // The pathway id the user is about to switch to, held for an explicit confirm
  // because the change regenerates the plan (profile-update policy).
  const [pendingPathway, setPendingPathway] = useState<string | null>(null)
  const [pathwayBusy, setPathwayBusy] = useState(false)
  const [pathwayError, setPathwayError] = useState<string | null>(null)

  function loadPathways() {
    api
      .pathways()
      .then(setPathways)
      .catch((err: unknown) => {
        if (!(err instanceof ApiError && err.status === 401)) setPathwayError(errorMessage(err))
      })
  }

  useEffect(() => {
    let active = true
    // The thresholds are read-only tuning; `me` carries the one writable knob on
    // this screen — the inbound-calendar-sync opt-in — and the pathway cards are
    // the story-layer "Change pathway" surface (a change here regenerates the plan).
    Promise.all([api.thresholds(), api.me(), api.pathways()])
      .then(([r, m, p]) => {
        if (!active) return
        setResult(r)
        setMe(m)
        setPathways(p)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) return
        if (active) {
          setError(errorMessage(err))
          setLoading(false)
        }
      })
    return () => {
      active = false
    }
  }, [])

  async function confirmPathwayChange() {
    if (!pendingPathway) return
    setPathwayBusy(true)
    setPathwayError(null)
    try {
      await api.selectPathway(pendingPathway)
      setPendingPathway(null)
      loadPathways() // reflect the new selection (the plan was invalidated server-side)
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) setPathwayError(errorMessage(err))
    } finally {
      setPathwayBusy(false)
    }
  }

  // Flip the opt-in and re-render from the refreshed me the server returns —
  // server is the source of truth, never an optimistic local guess.
  async function toggleSync() {
    if (!me || syncing) return
    setSyncing(true)
    setSyncError(null)
    try {
      const refreshed = await api.setCalendarSync(!me.inbound_calendar_sync_enabled)
      setMe(refreshed)
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) {
        setSyncError(errorMessage(err))
      }
    } finally {
      setSyncing(false)
    }
  }

  if (loading) return <div className="screen-center muted">Loading thresholds…</div>
  if (error) return <div className="screen-center">Couldn’t load thresholds — {error}</div>

  const sections = result?.sections ?? []
  const history = result?.history ?? []

  return (
    <section className="read-wrap">
      <span className="label">System tuning</span>
      <h1 className="t-h1" style={{ marginTop: 8 }}>
        Thresholds
      </h1>
      <p className="muted" style={{ marginTop: 6, maxWidth: 640 }}>
        The effective deterministic tuning the system serves from, and every change to it. The
        tuning values below are <b>read-only</b>: they change only via{' '}
        <span className="mono">tuning.toml</span>, which journals each effective change here (axiom
        07). All values are heuristic priors pending calibration.
      </p>

      {me && (
        <div className="card" style={{ marginTop: 18, padding: '6px 18px' }}>
          <div className="label" style={{ padding: '12px 0 4px' }}>
            Calendar sync
          </div>
          <div className="cfg-row">
            <div>
              <div className="cl">Adopt my Google Calendar edits</div>
              <div className="cs" style={{ maxWidth: 560 }}>
                When on, Loop checks the events it created on your calendar and updates your plan to
                match any you moved or resized — but only when the new time still fits your plan. It
                only ever reads its own events and never changes your calendar. Off by default.
              </div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={me.inbound_calendar_sync_enabled}
              aria-label="Adopt my Google Calendar edits"
              className={`switch${me.inbound_calendar_sync_enabled ? ' on' : ''}`}
              disabled={syncing}
              onClick={() => void toggleSync()}
            >
              <span className="knob" />
            </button>
          </div>
          {syncError && (
            <div className="banner-error" style={{ margin: '0 0 12px' }}>
              Couldn’t update the setting — {syncError}
            </div>
          )}
        </div>
      )}

      {pathways && (
        <div style={{ marginTop: 26 }}>
          <div className="label">Your story pathway</div>
          <p className="muted" style={{ marginTop: 6, maxWidth: 600, lineHeight: 1.5 }}>
            The narrative you&rsquo;re building toward. Changing it <b>regenerates your plan</b> around
            the new pillars and re-runs planning — your evidence is never reset, only re-matched to the
            new story. Pillar states below are computed deterministically from your confirmed evidence.
          </p>

          {pathwayError && (
            <div className="banner-error" style={{ marginTop: 12 }}>
              Couldn’t change your pathway — {pathwayError}
            </div>
          )}

          {pathways.cards.map((card) => (
            <PathwayCardView
              key={card.pathway_id}
              card={card}
              experienceTitles={(me?.profile?.experience ?? []).map((e) => e.title)}
              onSelect={() => {
                setPathwayError(null)
                setPendingPathway(card.pathway_id)
              }}
              selectLabel="Switch to this story"
              confirming={pendingPathway === card.pathway_id}
              confirmPrompt={
                <>
                  Switch to <b>{card.display_name}</b>? This discards your current draft/active plan
                  and regenerates it around the new pillars. Your evidence is never reset — only
                  re-matched to the new story.
                </>
              }
              confirmLabel="Switch and replan"
              busy={pathwayBusy}
              onConfirm={() => void confirmPathwayChange()}
              onCancel={() => setPendingPathway(null)}
            />
          ))}
        </div>
      )}

      {sections.map((section) => (
        <div key={section.name} className="card" style={{ marginTop: 16, padding: '6px 18px' }}>
          <div className="label" style={{ padding: '12px 0 4px' }}>
            {section.name}
          </div>
          {section.fields.map((field, i) => (
            <div
              key={field.name}
              className="cfg-row"
              style={{ borderBottom: i < section.fields.length - 1 ? '1px solid var(--line)' : 'none' }}
            >
              <div className="cl mono" style={{ fontSize: 13 }}>
                {field.name}
              </div>
              <div className="row" style={{ gap: 10 }}>
                <span style={{ fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                  {fmtValue(field.value)}
                </span>
                <span className={`tag${field.status === 'overridden' ? ' warn' : ''}`}>{field.status}</span>
              </div>
            </div>
          ))}
        </div>
      ))}

      <h2 className="t-h3" style={{ marginTop: 26 }}>
        Change history
      </h2>
      {history.length === 0 ? (
        <p className="muted" style={{ marginTop: 8 }}>
          No threshold changes recorded yet — every section above is serving its code default.
        </p>
      ) : (
        <div className="card" style={{ marginTop: 12, padding: '6px 18px' }}>
          {history.map((change, i) => (
            <div
              key={`${change.config_section}.${change.threshold_field}.${change.effective_at}`}
              className="cfg-row col"
              style={{
                alignItems: 'stretch',
                borderBottom: i < history.length - 1 ? '1px solid var(--line)' : 'none',
              }}
            >
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <span className="mono" style={{ fontSize: 13, fontWeight: 600 }}>
                  {change.config_section}.{change.threshold_field}
                </span>
                <span className="mono" style={{ fontSize: 12, color: 'var(--muted)' }}>
                  {fmtWhen(change.effective_at)}
                </span>
              </div>
              <div style={{ fontSize: 13, marginTop: 4 }}>
                {fmtValue(change.prior_value)} → <b>{fmtValue(change.new_value)}</b>
                <span className="muted"> · {change.justification}</span>
              </div>
              <div className="mono" style={{ fontSize: 11.5, color: 'var(--muted-2)', marginTop: 2 }}>
                {change.dataset_reference}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
