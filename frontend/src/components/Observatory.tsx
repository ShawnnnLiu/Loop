import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { KnowledgeMapView, MasteryTier } from '../api/types'
import { DUST_FAR, DUST_NEAR, beaconFor, bodyFor, starFor } from '../lib/atlas/bodies'
import { CANONICAL_VIEWPORT, layoutSky } from '../lib/atlas/layout'
import {
  bodyAccessibleName,
  earliestNextSession,
  honedFraction,
  nothingLit,
  panTransform,
  planetLabel,
  plaqueSummary,
  probeGeometry,
  roseNodes,
  statusLine,
  systemAccessibleName,
} from '../lib/atlas/render'
import { readSignals } from '../lib/atlas/signals'
import { fmtWhen } from '../lib/datetime'
import { groupCountLabel, groupNodes } from '../lib/knowledgeMap'
import { AtlasDefs } from './atlas/AtlasDefs'
import { BeaconGlyph, PlanetGlyph, StarGlyph, SvgButton } from './atlas/Glyphs'
import { Bloom, InstrumentEdge, Probe } from './atlas/Ornaments'
import { AddSkillPicker, CreateForm, CreateNodeForm } from './MapForms'

// The desktop Observatory (SA-C): the Star Atlas rendered from a real
// KnowledgeMapView. Structure and tiers come from the deterministic map_state fold
// (server-computed, axiom-11 non-interference); the *sky* is computed by the pure
// SA-B layout engine (layoutSky) and drawn declaratively through the SA-B/SA-C
// descriptor functions (bodyFor / starFor / beaconFor + render helpers). Every
// mutation is an existing route through `onMutate`. The ornament layer is complete
// (SA-E): the drifting probe + one-shot tier-up bloom ride inside the pan group;
// the orrery/bezel-tick/bracket instrument edge sits outside it (never zoomed).
// Deferred by design: chart-body keyboard/SR accessibility → SA-F. The drawer's
// dialog semantics ship now, and every ornament respects reduced motion.

const HINT = 'Study lights a system from its worlds; a confirmed artifact crowns a capstone.'

export function Observatory({
  view,
  pathwayName,
  selectedNodeId,
  onSelectNode,
  onMutate,
  busy,
  resetKey,
}: {
  view: KnowledgeMapView
  pathwayName: string
  selectedNodeId: string | null
  onSelectNode: (nodeId: string) => void
  onMutate: (fn: () => Promise<KnowledgeMapView>) => void
  busy: boolean
  /** Bumped by Pathway when the user clicks empty space around an open drawer
   *  (the backdrop): the sky then returns to the overview (collapse + zoom out)
   *  in the same gesture that closes the drawer. */
  resetKey: number
}) {
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set())
  const [focusId, setFocusId] = useState<string | null>(null)
  // Which map-level action is open: 'add-skill' | 'new-group' | 'new-node'.
  const [panel, setPanel] = useState<string | null>(null)
  const [hover, setHover] = useState<{ title: string; meta: string } | null>(null)
  // The node currently playing the one-shot tier-up bloom (SA-E), or null.
  const [bloomNodeId, setBloomNodeId] = useState<string | null>(null)

  const wrapRef = useRef<HTMLDivElement>(null)
  const skypanRef = useRef<SVGGElement>(null)
  const dustNearRef = useRef<SVGGElement>(null)
  const dustFarRef = useRef<SVGGElement>(null)
  const tooltipRef = useRef<HTMLDivElement>(null)
  const [containerW, setContainerW] = useState(0)
  // Previous snapshot of node tiers — the bloom fires on a strict tier rise
  // between fetches. Null until the first view is seen (no bloom on initial load).
  const prevTiers = useRef<Map<string, MasteryTier> | null>(null)
  const bloomTimer = useRef<number | null>(null)

  const reduced = useMemo(
    () => window.matchMedia('(prefers-reduced-motion: reduce)').matches,
    [],
  )

  // The sky. layoutSky positions systems/capstones/regions independently of the
  // open set (only planetsFor differs), so re-running on expand never reshuffles
  // the stars — but it stays memoized on (view, openGroups) so unrelated renders
  // (hover, selection) don't recompute the force sim.
  const sky = useMemo(
    () => layoutSky(view, CANONICAL_VIEWPORT, openGroups),
    [view, openGroups],
  )

  const nodesById = useMemo(
    () => new Map(view.nodes.map((n) => [n.node_id, n])),
    [view.nodes],
  )
  const groupsById = useMemo(
    () => new Map(view.groups.map((g) => [g.group_id, g])),
    [view.groups],
  )
  const branchBySlot = useMemo(
    () => new Map(view.branches.map((b) => [b.slot_id, b])),
    [view.branches],
  )

  // Keep the pan focus geometrically correct at any width: measure the rendered
  // chart so the CSS transform (in px) matches the viewBox units panTransform emits.
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const ro = new ResizeObserver((entries) => {
      const w = entries[0]?.contentRect.width
      if (w) setContainerW(w)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // Tier-up bloom: when a node rises a tier between fetches (a mark-evidence or a
  // set-point up through the drawer), play the one-shot at that world. The very
  // first view establishes the baseline (no bloom on load); reduced motion skips
  // it entirely (the reward flourish never mounts, mirroring the design page).
  useEffect(() => {
    const current = new Map<string, MasteryTier>(view.nodes.map((n) => [n.node_id, n.tier]))
    const prev = prevTiers.current
    prevTiers.current = current
    if (prev === null || reduced) return
    const risen = roseNodes(prev, view.nodes)
    if (risen.length === 0) return
    // Prefer the node the user is looking at, so the bloom lands where they acted.
    const pick = selectedNodeId && risen.includes(selectedNodeId) ? selectedNodeId : risen[0]
    setBloomNodeId(pick)
    if (bloomTimer.current) window.clearTimeout(bloomTimer.current)
    bloomTimer.current = window.setTimeout(() => setBloomNodeId(null), 1200)
  }, [view, reduced, selectedNodeId])

  useEffect(
    () => () => {
      if (bloomTimer.current) window.clearTimeout(bloomTimer.current)
    },
    [],
  )

  // Return the sky to the overview: collapse every open system and drop the pan
  // focus so the chart zooms back out. Driven both by an empty-sky click (the svg
  // background handler) and, when a drawer is open, by Pathway bumping `resetKey`
  // as it closes the drawer on an outside click — one gesture, full dismiss.
  function resetView() {
    setOpenGroups((prev) => (prev.size === 0 ? prev : new Set()))
    setFocusId(null)
  }

  const firstResetKey = useRef(true)
  useEffect(() => {
    // Skip the initial mount; only react to real bumps from Pathway.
    if (firstResetKey.current) {
      firstResetKey.current = false
      return
    }
    resetView()
    // resetView is stable enough for this purpose; depend only on the signal.
  }, [resetKey])

  function toggleGroup(groupId: string) {
    setOpenGroups((prev) => {
      const next = new Set(prev)
      if (next.has(groupId)) {
        next.delete(groupId)
        if (focusId === groupId) setFocusId(null)
      } else {
        next.add(groupId)
        setFocusId(groupId)
      }
      return next
    })
  }

  function selectNode(nodeId: string) {
    const node = nodesById.get(nodeId)
    onSelectNode(nodeId)
    // Glide the owning system (or the capstone itself) clear of the drawer.
    setFocusId(node && node.kind !== 'capstone' ? (node.group_id ?? nodeId) : nodeId)
    setPanel(null)
  }

  // The focused body's canonical position (a system star or a capstone beacon).
  const focusPos = useMemo(() => {
    if (focusId === null) return null
    const sys = sky.systems.find((s) => s.groupId === focusId)
    if (sys) return { x: sys.x, y: sys.y }
    const cap = sky.capstones.find((c) => c.nodeId === focusId)
    return cap ? { x: cap.x, y: cap.y } : null
  }, [focusId, sky])

  // Where a node draws right now: a capstone at its beacon, an open system's world
  // on its orbit, otherwise the (collapsed) system's star centre. Drives the probe
  // target and the bloom position — both follow the world wherever it sits.
  function nodePos(nodeId: string): { x: number; y: number } | null {
    const node = nodesById.get(nodeId)
    if (!node) return null
    if (node.kind === 'capstone') {
      const cap = sky.capstones.find((c) => c.nodeId === nodeId)
      return cap ? { x: cap.x, y: cap.y } : null
    }
    const gid = node.group_id
    if (gid && openGroups.has(gid)) {
      const p = sky.planetsFor(gid).find((pl) => pl.nodeId === nodeId)
      if (p) return { x: p.x, y: p.y }
    }
    const sys = sky.systems.find((s) => s.groupId === gid)
    return sys ? { x: sys.x, y: sys.y } : null
  }

  // The drifting probe → the earliest scheduled session's world. Omitted when
  // nothing is scheduled (graceful degradation). When its system is open the probe
  // approaches along the orbit radius; collapsed, it uses the default approach.
  const probe = (() => {
    const next = earliestNextSession(view)
    if (!next) return null
    const target = nodePos(next.nodeId)
    if (!target) return null
    const gid = nodesById.get(next.nodeId)?.group_id ?? null
    const centre = gid && openGroups.has(gid) ? sky.systems.find((s) => s.groupId === gid) : null
    const approachFrom = centre ? { x: centre.x, y: centre.y } : null
    return { geo: probeGeometry(target, approachFrom), whenLabel: fmtWhen(next.at) }
  })()

  const bloomPos = bloomNodeId ? nodePos(bloomNodeId) : null

  const pan = panTransform(focusPos, selectedNodeId !== null)
  const unit = containerW > 0 ? containerW / CANONICAL_VIEWPORT.w : 0
  const panStyle: React.CSSProperties = {
    transform: `translate(${(pan.x * unit).toFixed(2)}px, ${(pan.y * unit).toFixed(2)}px) scale(${pan.k})`,
    transformOrigin: '0 0',
    transition: reduced ? 'none' : 'transform .55s cubic-bezier(.3,.9,.3,1)',
  }

  function onMove(e: React.MouseEvent) {
    const el = wrapRef.current
    const tt = tooltipRef.current
    if (el && tt && hover) {
      const r = el.getBoundingClientRect()
      tt.style.left = `${Math.min(e.clientX - r.left + 16, r.width - 280)}px`
      tt.style.top = `${e.clientY - r.top + 14}px`
    }
    if (!reduced && el) {
      const r = el.getBoundingClientRect()
      const nx = (e.clientX - r.left) / r.width - 0.5
      const ny = (e.clientY - r.top) / r.height - 0.5
      if (dustNearRef.current)
        dustNearRef.current.style.transform = `translate(${(-nx * 5).toFixed(1)}px,${(-ny * 4).toFixed(1)}px)`
      if (dustFarRef.current)
        dustFarRef.current.style.transform = `translate(${(-nx * 11).toFixed(1)}px,${(-ny * 9).toFixed(1)}px)`
    }
  }

  const hf = honedFraction(view)
  const plaque = plaqueSummary(view)
  const dark = nothingLit(view)

  const allGroups = view.groups

  return (
    <div>
      <AtlasDefs />

      <div className="km-tools">
        <button
          type="button"
          className="btn btn-ghost sm"
          onClick={() => setPanel(panel === 'add-skill' ? null : 'add-skill')}
        >
          + Add a skill
        </button>
        <button
          type="button"
          className="btn btn-ghost sm"
          onClick={() => setPanel(panel === 'new-group' ? null : 'new-group')}
        >
          + New group
        </button>
        <button
          type="button"
          className="btn btn-ghost sm"
          onClick={() => setPanel(panel === 'new-node' ? null : 'new-node')}
        >
          + New node
        </button>
        <span className="spacer" />
        <span className="muted" style={{ fontSize: 11.5 }}>
          {HINT}
        </span>
      </div>

      {panel === 'add-skill' && <AddSkillPicker onMutate={onMutate} busy={busy} />}
      {panel === 'new-group' && (
        <CreateForm
          title="New group"
          submitLabel="Create group"
          busy={busy}
          onSubmit={(name) => {
            onMutate(() => api.createCustomGroup(name))
            setPanel(null)
          }}
        />
      )}
      {panel === 'new-node' && (
        <CreateNodeForm
          groups={allGroups}
          busy={busy}
          onSubmit={(name, groupId, description) => {
            onMutate(() =>
              api.createCustomNode({ name, groupId, description: description || null }),
            )
            setPanel(null)
          }}
        />
      )}

      <div className="chart-wrap" ref={wrapRef} onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
        <div className="bezel">
          <div className="rim">
            {/* A click that reaches the svg (rather than a body, which stops
                propagation) is an empty-sky click: return to the overview. */}
            <svg
              viewBox="0 0 1180 665"
              xmlns="http://www.w3.org/2000/svg"
              role="group"
              aria-label={`${pathwayName} — knowledge map`}
              onClick={resetView}
            >
              <rect width="1180" height="665" fill="url(#g-sky)" />

              <g ref={skypanRef} style={panStyle}>
                <g ref={dustNearRef} className="atlas-dust" aria-hidden="true">
                  {DUST_NEAR.map((d, i) => (
                    <circle
                      key={i}
                      cx={d.x}
                      cy={d.y}
                      r={d.r}
                      fill={d.gold ? '#e8c07a' : '#cfdae2'}
                      opacity={d.opacity}
                      className={d.twinkle ? 'twinkle' : undefined}
                      style={d.twinkle ? { animationDelay: `-${d.twinkleDelay}s` } : undefined}
                    />
                  ))}
                </g>
                <g ref={dustFarRef} className="atlas-dust" aria-hidden="true">
                  {DUST_FAR.map((d, i) => (
                    <circle
                      key={i}
                      cx={d.x}
                      cy={d.y}
                      r={d.r}
                      fill={d.gold ? '#e8c07a' : '#cfdae2'}
                      opacity={d.opacity}
                      className={d.twinkle ? 'twinkle' : undefined}
                      style={d.twinkle ? { animationDelay: `-${d.twinkleDelay}s` } : undefined}
                    />
                  ))}
                </g>

                {/* Nebulae + mastery light-pollution — pure atmosphere, hidden
                    from AT (`01-…`); the honest counts are the accessible truth. */}
                {sky.regions.map((r) => {
                  const lit = branchBySlot.get(r.branch)?.capstone_tier === 'proven'
                  return (
                    <g key={r.branch} aria-hidden="true">
                      <ellipse cx={r.cx} cy={r.cy} rx={r.rx} ry={r.ry} fill={`url(#${r.grad})`} />
                      {lit && (
                        <ellipse cx={r.cx} cy={r.cy} rx={r.rx * 0.8} ry={r.ry * 0.8} fill="url(#g-lamp)" />
                      )}
                    </g>
                  )
                })}
                {sky.systems.map((s) => {
                  const group = groupsById.get(s.groupId)
                  if (!group || group.is_personal || group.total_count === 0) return null
                  const k = group.honed_count / group.total_count
                  if (k <= 0) return null
                  return (
                    <circle
                      key={`lamp-${s.groupId}`}
                      cx={s.x}
                      cy={s.y}
                      r={(85 + 75 * k).toFixed(0)}
                      fill="url(#g-lamp)"
                      opacity={(k * 0.95).toFixed(2)}
                      aria-hidden="true"
                    />
                  )
                })}
                {hf > 0.5 && (
                  <rect
                    width="1180"
                    height="665"
                    fill="url(#g-lamp)"
                    opacity={((hf - 0.5) * 0.9).toFixed(2)}
                    aria-hidden="true"
                  />
                )}

                {/* Region labels */}
                {sky.regions.map((r) => {
                  const branch = branchBySlot.get(r.branch)
                  const lit = branch?.capstone_tier === 'proven'
                  const label = branch ? branch.title : 'Core — shared ground'
                  return (
                    <text
                      key={`lbl-${r.branch}`}
                      x={r.labelX}
                      y={r.labelY}
                      textAnchor="middle"
                      className={`rlabel${lit ? ' lit' : ''}`}
                    >
                      {label}
                    </text>
                  )
                })}

                {/* Capstone beacons */}
                {sky.capstones.map((c) => {
                  const branch = branchBySlot.get(c.branch)
                  const node = nodesById.get(c.nodeId)
                  if (!branch || !node) return null
                  const proven = branch.capstone_tier === 'proven'
                  return (
                    <g key={c.nodeId}>
                      <SvgButton
                        className="nodeg"
                        transform={`translate(${c.x},${c.y})`}
                        label={bodyAccessibleName(node, branch.capstone_tier, readSignals(node))}
                        onActivate={() => selectNode(c.nodeId)}
                        onMouseEnter={() =>
                          setHover({
                            title: node.title,
                            meta: statusLine(node, branch.capstone_tier, readSignals(node)),
                          })
                        }
                        onMouseLeave={() => setHover(null)}
                      >
                        <BeaconGlyph proven={proven} selected={selectedNodeId === c.nodeId} />
                      </SvgButton>
                      <text
                        x={c.x}
                        y={c.y + 36}
                        textAnchor="middle"
                        className="slab"
                        fontSize="12.5"
                        aria-hidden="true"
                      >
                        {node.title}
                      </text>
                      <text
                        x={c.x}
                        y={c.y + 51}
                        textAnchor="middle"
                        className={`caplab${proven ? ' lit' : ''}`}
                        aria-hidden="true"
                      >
                        {beaconFor(branch).label}
                      </text>
                    </g>
                  )
                })}

                {/* Personal-layer header */}
                {sky.personalHeader && (
                  <g>
                    <text
                      x={sky.personalHeader.x}
                      y={sky.personalHeader.y}
                      textAnchor="middle"
                      className="yourshdr"
                    >
                      YOUR ADDITIONS
                    </text>
                    <line
                      x1={sky.personalHeader.x - 38}
                      y1={sky.personalHeader.y + 8}
                      x2={sky.personalHeader.x + 38}
                      y2={sky.personalHeader.y + 8}
                      stroke="rgba(207,218,226,.25)"
                      strokeDasharray="2 3"
                    />
                  </g>
                )}

                {/* Systems (stars) + their worlds when open */}
                {sky.systems.map((s) => {
                  const group = groupsById.get(s.groupId)
                  if (!group) return null
                  const members = groupNodes(view, group)
                  const star = starFor(group, members)
                  const open = openGroups.has(group.group_id)
                  const warm = !group.is_personal && group.honed_count === group.total_count && group.total_count > 0
                  const hoverMeta = group.is_personal
                    ? `${group.total_count} sketched · yours`
                    : `${groupCountLabel(group)} · click to ${open ? 'close' : 'open'}`

                  if (!open) {
                    return (
                      <g key={group.group_id}>
                        <SvgButton
                          className="sysg"
                          transform={`translate(${s.x},${s.y})`}
                          label={systemAccessibleName(group, false)}
                          onActivate={() => toggleGroup(group.group_id)}
                          onMouseEnter={() => setHover({ title: group.title, meta: hoverMeta })}
                        >
                          <StarGlyph star={star} />
                          <circle className="hit" r="30" />
                        </SvgButton>
                        <text x={s.x} y={s.y + 24} textAnchor="middle" className="slab" aria-hidden="true">
                          {group.title}
                        </text>
                        <text
                          x={s.x}
                          y={s.y + 38}
                          textAnchor="middle"
                          className={`scount${warm ? ' warm' : ''}`}
                          aria-hidden="true"
                        >
                          {group.is_personal
                            ? `${group.total_count} sketched · yours`
                            : `${group.honed_count}/${group.total_count} honed`}
                        </text>
                      </g>
                    )
                  }

                  const planets = sky.planetsFor(group.group_id)
                  const upperY = s.y + 84 > 648 ? s.y - 80 : s.y + 84
                  return (
                    <g key={group.group_id}>
                      <circle
                        cx={s.x}
                        cy={s.y}
                        r="64"
                        fill="none"
                        stroke="rgba(207,218,226,.12)"
                        strokeWidth="1"
                        aria-hidden="true"
                      />
                      {star.allHoned && (
                        <g className="consti" aria-hidden="true">
                          <polygon
                            points={planets.map((p) => `${p.x.toFixed(0)},${p.y.toFixed(0)}`).join(' ')}
                            fill="none"
                            stroke="#e8c07a"
                            strokeWidth="1"
                            opacity=".5"
                          />
                          {planets.map((p) => (
                            <circle key={p.nodeId} cx={p.x} cy={p.y} r="1.6" fill="#e8c07a" opacity=".7" />
                          ))}
                        </g>
                      )}
                      <SvgButton
                        className="sysg"
                        transform={`translate(${s.x},${s.y})`}
                        label={systemAccessibleName(group, true)}
                        onActivate={() => toggleGroup(group.group_id)}
                        onMouseEnter={() => setHover({ title: group.title, meta: hoverMeta })}
                        onMouseLeave={() => setHover(null)}
                      >
                        <StarGlyph star={star} />
                        <circle className="hit" r="16" />
                      </SvgButton>
                      <text
                        x={s.x}
                        y={upperY}
                        textAnchor="middle"
                        className={`scount${warm ? ' warm' : ''}`}
                        aria-hidden="true"
                      >
                        {group.title.toUpperCase()} ·{' '}
                        {group.is_personal ? `${group.total_count} YOURS` : `${group.honed_count}/${group.total_count}`}
                      </text>
                      {/* collapse control */}
                      <SvgButton
                        className="sysg"
                        transform={`translate(${(s.x + 54).toFixed(0)},${(s.y - 54).toFixed(0)})`}
                        label={`Collapse ${group.title}`}
                        onActivate={() => toggleGroup(group.group_id)}
                      >
                        <circle r="8" fill="rgba(11,20,32,.7)" stroke="rgba(207,218,226,.3)" />
                        <text y="3" textAnchor="middle" fontSize="8.5" fill="#cfdae2" aria-hidden="true">
                          ✕
                        </text>
                        <circle className="hit" r="12" />
                      </SvgButton>
                      {/* delete-group affordance (custom groups only) */}
                      {group.is_personal && (
                        <SvgButton
                          label={`Delete group ${group.title}`}
                          onActivate={() => onMutate(() => api.deleteCustomGroup(group.group_id))}
                        >
                          <text x={s.x} y={upperY + 15} textAnchor="middle" className="del-group">
                            Delete group
                          </text>
                        </SvgButton>
                      )}
                      {planets.map((p) => {
                        const node = nodesById.get(p.nodeId)
                        if (!node) return null
                        const body = bodyFor(node, node.tier, readSignals(node))
                        const custom = node.is_personal || node.kind === 'custom'
                        const label = planetLabel(p.angle, p.x, p.y, custom)
                        const dim = node.tier === 'discovered'
                        return (
                          <g key={p.nodeId}>
                            <SvgButton
                              className="nodeg"
                              transform={`translate(${p.x.toFixed(1)},${p.y.toFixed(1)})`}
                              label={bodyAccessibleName(node, node.tier, readSignals(node))}
                              onActivate={() => selectNode(p.nodeId)}
                              onMouseEnter={() =>
                                setHover({
                                  title: node.title,
                                  meta: statusLine(node, node.tier, readSignals(node)),
                                })
                              }
                              onMouseLeave={() => setHover(null)}
                            >
                              <PlanetGlyph body={body} selected={selectedNodeId === p.nodeId} />
                            </SvgButton>
                            <text
                              x={label.x}
                              y={label.y}
                              textAnchor={label.anchor}
                              className={`plab${dim ? ' dim' : ''}`}
                              aria-hidden="true"
                            >
                              {node.title}
                            </text>
                          </g>
                        )
                      })}
                    </g>
                  )
                })}

                {/* Motion ornaments ride inside the pan group so they glide with
                    the sky (SA-E): the probe toward the next session, the one-shot
                    tier-up bloom. Both aria-hidden — the drawer carries the truth. */}
                {probe && <Probe geo={probe.geo} whenLabel={probe.whenLabel} />}
                {bloomPos && <Bloom x={bloomPos.x} y={bloomPos.y} />}
              </g>

              {/* Instrument edge (SA-E): bezel ticks, corner brackets, orrery —
                  fixed to the rim, never zoomed with the sky. Decorative. */}
              <InstrumentEdge />

              {/* Mission-plaque cartouche — the accessible textual truth (instrument
                  layer, outside the pan group so it never zooms). */}
              <g>
                <rect x="30" y="584" width="312" height="68" rx="6" fill="rgba(20,29,41,.88)" stroke="#8a6f3f" />
                <rect x="35" y="589" width="302" height="58" rx="3" fill="none" stroke="rgba(138,111,63,.35)" />
                <text x="186" y="606" textAnchor="middle" className="plaq-n">
                  {pathwayName.toUpperCase()}
                </text>
                <text x="186" y="622" textAnchor="middle" className="plaq-c">
                  {plaque.branches} branches · {plaque.systems} systems · {plaque.worlds} worlds ·{' '}
                  {plaque.capstones} capstones
                </text>
                <text x="186" y="637" textAnchor="middle" className="plaq-c">
                  {plaque.honed} honed · {plaque.proven} proven · {plaque.capstonesProven} of{' '}
                  {plaque.capstones} capstones proven
                </text>
              </g>

              <rect width="1180" height="665" fill="url(#g-vig)" pointerEvents="none" aria-hidden="true" />
            </svg>

            {dark && (
              <div className="atlas-empty card">
                <h3>Nothing lit yet</h3>
                <p>
                  The sky before first light. Every world is already on the map and yours to study —
                  schedule your first session and first light follows.
                </p>
                <Link to="/today" className="btn btn-primary sm">
                  Light one star
                </Link>
              </div>
            )}
          </div>
        </div>

        <div ref={tooltipRef} className={`atlas-tt${hover ? ' show' : ''}`} aria-hidden="true">
          {hover && (
            <>
              <div className="tname">{hover.title}</div>
              <div className="tmeta">{hover.meta}</div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
