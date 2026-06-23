import { useEffect, useState } from 'react'

import { ApiError, api, errorMessage } from '../api/client'
import type { ThresholdsResult } from '../api/types'
import { fmtWhen } from '../lib/datetime'

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
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api
      .thresholds()
      .then((r) => active && (setResult(r), setLoading(false)))
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
        The effective deterministic tuning the system serves from, and every change to it. This page
        is <b>read-only</b>: tuning values change only via <span className="mono">tuning.toml</span>,
        which journals each effective change here (axiom 07). All values are heuristic priors pending
        calibration.
      </p>

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
