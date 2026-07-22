import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { ApiError, api, errorMessage } from '../api/client'
import type { KnowledgeMapView, PathwayCard } from '../api/types'
import { MobileSky } from '../components/MobileSky'
import { NodeDrawer } from '../components/NodeDrawer'
import { Observatory } from '../components/Observatory'

// One Star Atlas screen, two renderers: desktop gets the force-directed Observatory
// (SA-C), phones get the scrolling MobileSky (SA-D). The breakpoint keeps the
// desktop-only layoutSky off small screens (02-…) so a phone never runs the force
// sim. Tracks the media query live so a resize across the breakpoint re-renders the
// right surface.
function useIsDesktop(): boolean {
  const [desktop, setDesktop] = useState(
    () => typeof window !== 'undefined' && window.matchMedia('(min-width: 900px)').matches,
  )
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 900px)')
    const onChange = () => setDesktop(mq.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return desktop
}

// The Pathway screen (KT-D): the account's full knowledge map. Structure comes
// from the pathway registry + the append-only overlay; every tier is the
// narrative map_state fold recomputed server-side on each read/mutation — no LLM,
// reproducible by calling the kernel on stored data (axiom 00 / 11). The map is a
// presentation/memory layer that gates nothing (axiom-11 non-interference). Empty
// until a pathway is selected; personal custom content is a display-only layer
// that counts toward nothing and never enters a prompt.

export function PathwayScreen() {
  const [view, setView] = useState<KnowledgeMapView | null>(null)
  const [card, setCard] = useState<PathwayCard | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState<string | null>(null)
  // Bumped when the user clicks the backdrop (empty space) around the drawer, so
  // the desktop Observatory returns to the overview in the same gesture. The ✕ and
  // Esc close the drawer only (they leave the system open), so they don't bump it.
  const [viewResetKey, setViewResetKey] = useState(0)
  const isDesktop = useIsDesktop()

  function load(initial = false) {
    if (initial) setLoading(true)
    // The map is the source of truth; the pathways card only decorates the header
    // (display name + spine), so its failure never blocks the map.
    Promise.all([api.knowledgeMap(), api.pathways()])
      .then(([map, pathways]) => {
        setView(map)
        setCard(pathways.cards.find((c) => c.selected) ?? null)
        setLoading(false)
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.status === 401) return
        setError(errorMessage(err))
        setLoading(false)
      })
  }

  useEffect(() => {
    load(true)
  }, [])

  function mutate(fn: () => Promise<KnowledgeMapView>) {
    setBusy(true)
    setActionError(null)
    fn()
      .then((next) => setView(next))
      .catch((err: unknown) => {
        if (!(err instanceof ApiError && err.status === 401)) setActionError(errorMessage(err))
      })
      .finally(() => setBusy(false))
  }

  async function reconfirmVersion(pathwayId: string) {
    setBusy(true)
    try {
      await api.selectPathway(pathwayId) // re-pins the current registry version
      load()
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) setActionError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <div className="screen-center muted">Loading your map…</div>
  if (error || !view) {
    return (
      <div className="screen">
        <span className="eyebrow">Pathway</span>
        <p className="muted" style={{ marginTop: 8 }}>
          Couldn&rsquo;t load your knowledge map — {error ?? 'unknown error'}.
        </p>
      </div>
    )
  }

  const selectedNode = selectedNodeId
    ? view.nodes.find((n) => n.node_id === selectedNodeId) ?? null
    : null

  // Close the drawer only (✕ / Esc): keep the system open so the user can stay in
  // context or pick another world.
  function closeDrawer() {
    setSelectedNodeId(null)
    setActionError(null)
  }

  // Click-away dismiss (the drawer backdrop): close the drawer and return the sky
  // to the overview (collapse open systems + zoom out) in one gesture.
  function dismissDrawer() {
    closeDrawer()
    setViewResetKey((k) => k + 1)
  }

  return (
    <div className="screen">
      <div className="row" style={{ alignItems: 'flex-end', gap: 18 }}>
        <div>
          <span className="eyebrow">Pathway</span>
          <h1 className="t-h1" style={{ marginTop: 2 }}>
            {card?.display_name ?? 'Your knowledge map'}
          </h1>
          {card?.spine && (
            <div className="muted" style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 14.5, marginTop: 3 }}>
              &ldquo;{card.spine}&rdquo;
            </div>
          )}
        </div>
        <span className="spacer" />
        <Link to="/accountability" className="btn btn-quiet sm">
          ← Back to Progress
        </Link>
      </div>

      {view.version_mismatch && view.pathway_id && (
        <div className="card" style={{ marginTop: 16, padding: '12px 16px', borderColor: 'var(--clay)', maxWidth: 620 }}>
          <span style={{ fontSize: 13.5 }}>
            Your chosen pathway is pinned to an older registry version. Re-confirm to refresh its map
            against the current one — your progress and notes stay as they are.
          </span>
          <div className="row" style={{ marginTop: 10 }}>
            <button
              className="btn btn-primary sm"
              type="button"
              disabled={busy}
              onClick={() => void reconfirmVersion(view.pathway_id as string)}
            >
              Re-confirm
            </button>
          </div>
        </div>
      )}

      {!view.has_selection ? (
        <div className="card" style={{ marginTop: 20, padding: '28px 26px', maxWidth: 460, textAlign: 'center' }}>
          <span className="eyebrow">Pathway map</span>
          <h3 className="t-h3" style={{ marginTop: 8 }}>
            No pathway charted yet
          </h3>
          <p className="muted" style={{ marginTop: 8, lineHeight: 1.55 }}>
            Pick a pathway and Loop lays out its knowledge map — every group, every pillar, and the
            artifacts that prove them.
          </p>
          <div className="row" style={{ justifyContent: 'center', marginTop: 14 }}>
            <Link to="/thresholds" className="btn btn-primary sm">
              Choose a pathway
            </Link>
          </div>
        </div>
      ) : isDesktop ? (
        <div style={{ marginTop: 20, maxWidth: 1080 }}>
          <Observatory
            view={view}
            pathwayName={card?.display_name ?? 'Your knowledge map'}
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
            onMutate={mutate}
            busy={busy}
            resetKey={viewResetKey}
          />
        </div>
      ) : (
        <div style={{ marginTop: 20, maxWidth: 760 }}>
          <MobileSky
            view={view}
            pathwayName={card?.display_name ?? 'Your knowledge map'}
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
            onMutate={mutate}
            busy={busy}
          />
        </div>
      )}

      {selectedNode && (
        <NodeDrawer
          node={selectedNode}
          onMutate={mutate}
          onClose={closeDrawer}
          onDismiss={isDesktop ? dismissDrawer : closeDrawer}
          busy={busy}
          error={actionError}
        />
      )}
    </div>
  )
}
