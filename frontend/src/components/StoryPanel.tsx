import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, api, errorMessage } from '../api/client'
import type { EvidenceKind, PathwaysResult, StorySummaryResult, UserProfile } from '../api/types'
import { EVIDENCE_KINDS } from '../api/types'
import { MAX_THEME_TAGS } from '../lib/intake'
import { kindLabel } from '../lib/story'
import { PathwayCardView } from './PathwayCard'

// The Progress screen's story panel (NP-E): once a pathway is selected, the
// user's pillars with their deterministic coverage state, plus the "mark
// evidence" gate — the story-layer analog of the approval gate. Completing study
// tasks never fills a pillar; only confirming a real artifact here does. Every
// state shown is the narrative kernel's output over confirmed evidence, no LLM.
// Choosing / changing a pathway (which triggers a replan) lives on Tuning; this
// panel is view + mark-evidence, whose profile edit invalidates nothing.

interface EvidenceForm {
  title: string
  organization: string
  summary: string
  kind: EvidenceKind
  theme_tags: string[]
}

const EMPTY_FORM: EvidenceForm = {
  title: '',
  organization: '',
  summary: '',
  kind: 'work',
  theme_tags: [],
}

export function StoryPanel() {
  const [pathways, setPathways] = useState<PathwaysResult | null>(null)
  const [themes, setThemes] = useState<string[]>([])
  const [experienceTitles, setExperienceTitles] = useState<string[]>([])
  const [fitNotes, setFitNotes] = useState<Record<string, string>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Story summary (NP-F): user-initiated, display-only. Kept out of `load` so a
  // slow LLM call never blocks the deterministic panel; cleared on reload.
  const [summary, setSummary] = useState<StorySummaryResult | null>(null)
  const [summaryBusy, setSummaryBusy] = useState(false)
  const [summaryError, setSummaryError] = useState<string | null>(null)

  const [form, setForm] = useState<EvidenceForm>(EMPTY_FORM)
  const [adding, setAdding] = useState(false)
  const [busy, setBusy] = useState(false)
  const [markError, setMarkError] = useState<string | null>(null)

  function load(initial = false) {
    if (initial) setLoading(true)
    setSummary(null) // stale evidence => stale summary; the user re-requests it
    setSummaryError(null)
    Promise.all([api.pathways(), api.evidenceVocabulary(), api.me()])
      .then(([p, vocab, me]) => {
        setPathways(p)
        setThemes(vocab.themes)
        setExperienceTitles((me.profile?.experience ?? []).map((e: UserProfile['experience'][number]) => e.title))
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) return
        setError(errorMessage(err))
        setLoading(false)
      })
    // Fit notes are supplementary LLM prose over the stored profile: fetched
    // separately so the deterministic cards never wait on them, and a failure
    // just leaves the cards note-less.
    api
      .pathwayFitNotes()
      .then((res) => setFitNotes(res.status === 'ok' ? res.notes : {}))
      .catch(() => setFitNotes({}))
  }

  async function refreshSummary() {
    setSummaryBusy(true)
    setSummaryError(null)
    try {
      setSummary(await api.storySummary())
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) setSummaryError(errorMessage(err))
    } finally {
      setSummaryBusy(false)
    }
  }

  useEffect(() => {
    load(true)
  }, [])

  const toggleTheme = (theme: string) =>
    setForm((prev) => {
      const has = prev.theme_tags.includes(theme)
      if (!has && prev.theme_tags.length >= MAX_THEME_TAGS) return prev
      return {
        ...prev,
        theme_tags: has ? prev.theme_tags.filter((t) => t !== theme) : [...prev.theme_tags, theme],
      }
    })

  async function submitEvidence() {
    setBusy(true)
    setMarkError(null)
    try {
      await api.markEvidence({
        title: form.title.trim(),
        organization: form.organization.trim() || null,
        summary: form.summary.trim() || null,
        kind: form.kind,
        theme_tags: form.theme_tags,
      })
      setForm(EMPTY_FORM)
      setAdding(false)
      load() // recompute coverage from the new evidence
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) setMarkError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  async function reconfirmVersion(pathwayId: string) {
    setBusy(true)
    try {
      await api.selectPathway(pathwayId) // re-pins the current registry version
      load()
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return null // the panel is supplementary; stay quiet until ready
  if (error) {
    return (
      <section style={{ marginTop: 28, maxWidth: 600 }}>
        <span className="label">Your story</span>
        <p className="muted" style={{ marginTop: 8 }}>
          Couldn&rsquo;t load your story — {error}
        </p>
      </section>
    )
  }

  const selected = pathways?.cards.find((c) => c.selected) ?? null

  return (
    <section style={{ marginTop: 28, maxWidth: 600 }}>
      <span className="label">Your story</span>

      {pathways?.version_mismatch && selected && (
        <div className="card" style={{ marginTop: 10, padding: '12px 16px', borderColor: 'var(--clay)' }}>
          <span style={{ fontSize: 13.5 }}>
            Your chosen pathway is pinned to an older registry version. Re-confirm to refresh its
            pillars against the current one — your evidence and plan stay as they are.
          </span>
          <div className="row" style={{ marginTop: 10 }}>
            <button
              className="btn btn-primary sm"
              type="button"
              disabled={busy}
              onClick={() => void reconfirmVersion(selected.pathway_id)}
            >
              Re-confirm
            </button>
          </div>
        </div>
      )}

      {!selected ? (
        <>
          <p className="muted" style={{ marginTop: 8, lineHeight: 1.5 }}>
            You haven&rsquo;t chosen a story yet. These are the pathways for your track, ranked by how
            many pillars your evidence already carries. Choose one from{' '}
            <Link to="/thresholds">Tuning</Link> to start tracking your pillars (it regenerates your
            plan around the gaps).
          </p>
          {(pathways?.cards ?? []).map((card) => (
            <PathwayCardView
              key={card.pathway_id}
              card={card}
              experienceTitles={experienceTitles}
              fitNote={fitNotes[card.pathway_id]}
            />
          ))}
        </>
      ) : (
        <>
          <p className="muted" style={{ marginTop: 8, lineHeight: 1.5 }}>
            Your pillars fill from confirmed evidence only. Finishing study tasks never claims an
            artifact — mark a pillar filled here when you actually have the work to show.
          </p>
          <PathwayCardView card={selected} experienceTitles={experienceTitles} fitNote={fitNotes[selected.pathway_id]} />

          <div className="card" style={{ marginTop: 12, padding: '12px 16px' }}>
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline', gap: 10 }}>
              <span className="label">Where your package stands</span>
              <button
                className="btn btn-quiet sm"
                type="button"
                disabled={summaryBusy}
                onClick={() => void refreshSummary()}
              >
                {summaryBusy ? 'Writing…' : summary ? 'Refresh' : 'Summarize'}
              </button>
            </div>
            {summary?.status === 'ok' && summary.summary && (
              <>
                <p style={{ fontSize: 13.5, marginTop: 8, lineHeight: 1.5 }}>{summary.summary}</p>
                {summary.detail.length > 0 && (
                  <ul className="muted" style={{ fontSize: 12.5, marginTop: 6, paddingLeft: 18, lineHeight: 1.5 }}>
                    {summary.detail.map((line, i) => (
                      <li key={i}>{line}</li>
                    ))}
                  </ul>
                )}
              </>
            )}
            {summary?.status === 'failed' && (
              <p className="muted" style={{ fontSize: 12.5, marginTop: 8 }}>
                Couldn&rsquo;t write a summary just now — your pillars above are unaffected. Try again in a moment.
              </p>
            )}
            {summaryError && (
              <div className="banner-error" style={{ marginTop: 8 }}>
                {summaryError}
              </div>
            )}
            {!summary && !summaryError && !summaryBusy && (
              <p className="muted" style={{ fontSize: 12.5, marginTop: 8, lineHeight: 1.5 }}>
                A short written recap of your package, from the pillars above. Generated only when you ask.
              </p>
            )}
          </div>

          {!adding ? (
            <button className="btn btn-primary sm" type="button" style={{ marginTop: 12 }} onClick={() => setAdding(true)}>
              + Mark evidence
            </button>
          ) : (
            <div className="card" style={{ marginTop: 12, padding: '14px 16px' }}>
              <div className="label" style={{ marginBottom: 8 }}>
                Mark evidence
              </div>
              <input
                className="input"
                style={{ width: '100%', boxSizing: 'border-box' }}
                aria-label="evidence title"
                placeholder="Title — e.g. Shipped billing dashboard"
                value={form.title}
                onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
              />
              <input
                className="input"
                style={{ width: '100%', boxSizing: 'border-box', marginTop: 8 }}
                aria-label="evidence organization"
                placeholder="Where / for whom (optional)"
                value={form.organization}
                onChange={(e) => setForm((p) => ({ ...p, organization: e.target.value }))}
              />
              <input
                className="input"
                style={{ width: '100%', boxSizing: 'border-box', marginTop: 8 }}
                aria-label="evidence summary"
                placeholder="One-line summary or artifact link (optional)"
                value={form.summary}
                onChange={(e) => setForm((p) => ({ ...p, summary: e.target.value }))}
              />
              <div className="row" style={{ gap: 10, marginTop: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <label className="cs" htmlFor="evidence-kind">
                  Kind
                </label>
                <select
                  id="evidence-kind"
                  className="input"
                  style={{ maxWidth: 150, padding: '6px 8px', fontSize: 13 }}
                  value={form.kind}
                  onChange={(e) => setForm((p) => ({ ...p, kind: e.target.value as EvidenceKind }))}
                >
                  {EVIDENCE_KINDS.map((k) => (
                    <option key={k} value={k}>
                      {kindLabel(k)}
                    </option>
                  ))}
                </select>
                {themes.length > 0 && (
                  <span className="cs">
                    Themes ({form.theme_tags.length}/{MAX_THEME_TAGS})
                  </span>
                )}
              </div>
              {themes.length > 0 && (
                <div className="chip-row" style={{ marginTop: 6 }}>
                  {themes.map((theme) => {
                    const on = form.theme_tags.includes(theme)
                    const atCap = !on && form.theme_tags.length >= MAX_THEME_TAGS
                    return (
                      <button
                        key={theme}
                        type="button"
                        className={`chip sm${on ? ' on' : ''}`}
                        disabled={atCap}
                        aria-pressed={on}
                        onClick={() => toggleTheme(theme)}
                      >
                        {theme}
                      </button>
                    )
                  })}
                </div>
              )}
              {markError && (
                <div className="banner-error" style={{ marginTop: 10 }}>
                  {markError}
                </div>
              )}
              <div className="row" style={{ gap: 8, marginTop: 12 }}>
                <button
                  className="btn btn-primary sm"
                  type="button"
                  disabled={busy || form.title.trim().length === 0}
                  onClick={() => void submitEvidence()}
                >
                  {busy ? 'Saving…' : 'Add evidence'}
                </button>
                <button
                  className="btn btn-quiet sm"
                  type="button"
                  disabled={busy}
                  onClick={() => {
                    setAdding(false)
                    setForm(EMPTY_FORM)
                    setMarkError(null)
                  }}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  )
}
