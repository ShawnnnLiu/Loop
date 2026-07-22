import { useState } from 'react'
import { Link } from 'react-router-dom'

import { api } from '../api/client'
import type { KnowledgeGroupView, KnowledgeMapView, KnowledgeNodeView } from '../api/types'
import { bodyFor, starFor } from '../lib/atlas/bodies'
import { nothingLit, plaqueSummary, statusLine } from '../lib/atlas/render'
import { readSignals } from '../lib/atlas/signals'
import { branchGroups, coreGroups, groupNodes, partitionGroups } from '../lib/knowledgeMap'
import { AtlasDefs } from './atlas/AtlasDefs'
import { BeaconGlyph, PlanetGlyph, StarGlyph } from './atlas/Glyphs'
import { AddSkillPicker, CreateForm, CreateNodeForm } from './MapForms'

// The mobile Star Atlas (SA-D): the scrolling sky. Mobile is not a shrunk
// Observatory — the desktop force-directed chart (layoutSky) never runs on phones
// (Pathway's matchMedia switch). Instead the same KnowledgeMapView renders as a
// vertically scrolling dark sky of accordion system cards, and the drawer becomes
// a bottom sheet (NodeDrawer's max-width sheet styling). Same data, same tiers,
// same mutation routes — a thumb-first layout that reuses the shared celestial
// glyphs (decision B: a comet is a comet on both platforms), the SA-B/SA-C
// descriptor + render helpers, and lib/knowledgeMap.ts view-model. Normative
// source: docs/implementation-plans/knowledge-map-atlas/04-mobile-atlas.md.

const HINT = 'Study lights a system from its worlds; a confirmed artifact crowns a capstone.'

/** A celestial glyph rendered small, in a mini viewBox centred on the origin (the
 *  glyphs draw at 0,0). aria-hidden — the row's text carries the meaning (`04-…`).
 *  The `.mglyph` scope neutralizes the glyph's hit circle / selring, which are
 *  otherwise styled only under `.rim` on desktop. */
function Mini({
  size,
  viewBox,
  children,
}: {
  size: number
  viewBox: string
  children: React.ReactNode
}) {
  return (
    <svg className="mglyph" width={size} height={size} viewBox={viewBox} aria-hidden="true">
      {children}
    </svg>
  )
}

/** One system's member world/comet — a mini glyph + honest status line, opening the
 *  bottom sheet on tap. A native button with a composed accessible name. */
function MemberCard({
  node,
  selected,
  onSelect,
}: {
  node: KnowledgeNodeView
  selected: boolean
  onSelect: () => void
}) {
  const signals = readSignals(node)
  const status = statusLine(node, node.tier, signals)
  return (
    <button type="button" className={`m-card${selected ? ' sel' : ''}`} onClick={onSelect}>
      <Mini size={40} viewBox="-27 -27 54 54">
        <PlanetGlyph body={bodyFor(node, node.tier, signals)} selected={false} />
      </Mini>
      <span>
        <span className="mc-t" style={{ fontSize: 14 }}>
          {node.title}
        </span>
        <span className="mc-s">{status}</span>
      </span>
    </button>
  )
}

/** A star system as an inline accordion card: the star glyph + honest count chip +
 *  chevron; expanding reveals its member worlds (client state, no fetch) and — on a
 *  personal group — the delete affordance. Mirrors the KT-D accordion's information
 *  architecture, re-skinned to the dark sky. */
function SystemCard({
  view,
  group,
  open,
  onToggle,
  selectedNodeId,
  onSelectNode,
  onMutate,
  busy,
}: {
  view: KnowledgeMapView
  group: KnowledgeGroupView
  open: boolean
  onToggle: () => void
  selectedNodeId: string | null
  onSelectNode: (nodeId: string) => void
  onMutate: (fn: () => Promise<KnowledgeMapView>) => void
  busy: boolean
}) {
  const members = groupNodes(view, group)
  const star = starFor(group, members)
  const warm = !group.is_personal && group.total_count > 0 && group.honed_count === group.total_count
  const count = group.is_personal
    ? `${group.total_count} sketched · yours`
    : `${group.honed_count}/${group.total_count} honed`

  return (
    <div className={`m-sys${open ? ' open' : ''}`}>
      <button type="button" className="m-srow" aria-expanded={open} onClick={onToggle}>
        <Mini size={36} viewBox="-24 -24 48 48">
          <StarGlyph star={star} />
        </Mini>
        <span>
          <span className="mc-t">{group.title}</span>
          <span className={`mc-s${warm ? ' warm' : ''}`}>{count}</span>
        </span>
        <span className="chev" aria-hidden="true">
          ▾
        </span>
      </button>
      {open && (
        <div className="m-acc">
          {members.map((n) => (
            <MemberCard
              key={n.node_id}
              node={n}
              selected={selectedNodeId === n.node_id}
              onSelect={() => onSelectNode(n.node_id)}
            />
          ))}
          {members.length === 0 && (
            <p className="mc-s" style={{ margin: '2px 0 6px' }}>
              No worlds here yet.
            </p>
          )}
          {group.is_personal && (
            <button
              type="button"
              className="m-del"
              disabled={busy}
              onClick={() => onMutate(() => api.deleteCustomGroup(group.group_id))}
            >
              Delete group
            </button>
          )}
        </div>
      )}
    </div>
  )
}

/** The capstone at a branch head — a beacon card (caged ember → supernova) opening
 *  the sheet. State is slot coverage, never study minutes (`06-…`). */
function CapstoneCard({
  node,
  proven,
  onSelect,
}: {
  node: KnowledgeNodeView
  proven: boolean
  onSelect: () => void
}) {
  return (
    <button type="button" className="m-cap" onClick={onSelect}>
      <Mini size={40} viewBox="-30 -30 60 60">
        <BeaconGlyph proven={proven} selected={false} />
      </Mini>
      <span>
        <span className="mc-t">{node.title}</span>
        <span className={`mc-s${proven ? ' warm' : ''}`}>
          {statusLine(node, node.tier, readSignals(node))}
        </span>
      </span>
    </button>
  )
}

export function MobileSky({
  view,
  pathwayName,
  selectedNodeId,
  onSelectNode,
  onMutate,
  busy,
}: {
  view: KnowledgeMapView
  pathwayName: string
  selectedNodeId: string | null
  onSelectNode: (nodeId: string) => void
  onMutate: (fn: () => Promise<KnowledgeMapView>) => void
  busy: boolean
}) {
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set())
  // Which map-level action is open: 'add-skill' | 'new-group' | 'new-node'.
  const [panel, setPanel] = useState<string | null>(null)

  function toggleGroup(groupId: string) {
    setOpenGroups((prev) => {
      const next = new Set(prev)
      if (next.has(groupId)) next.delete(groupId)
      else next.add(groupId)
      return next
    })
  }

  function selectNode(nodeId: string) {
    onSelectNode(nodeId)
    setPanel(null)
  }

  const nodesById = new Map(view.nodes.map((n) => [n.node_id, n]))
  const { personalGroups } = partitionGroups(view)
  const core = coreGroups(view)
  const plaque = plaqueSummary(view)
  const dark = nothingLit(view)
  const allGroups = view.groups

  const renderSystem = (group: KnowledgeGroupView) => (
    <SystemCard
      key={group.group_id}
      view={view}
      group={group}
      open={openGroups.has(group.group_id)}
      onToggle={() => toggleGroup(group.group_id)}
      selectedNodeId={selectedNodeId}
      onSelectNode={selectNode}
      onMutate={onMutate}
      busy={busy}
    />
  )

  return (
    <div>
      <AtlasDefs />

      {/* Map-level actions live on the light chrome above the sky, exactly as the
          desktop Observatory (never hover-revealed; `04-…`). */}
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
      </div>
      <p className="muted" style={{ fontSize: 11.5, margin: '2px 2px 0', lineHeight: 1.5 }}>
        {HINT}
      </p>

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
            onMutate(() => api.createCustomNode({ name, groupId, description: description || null }))
            setPanel(null)
          }}
        />
      )}

      <div className="msky">
        <div className="msky-dust" aria-hidden="true" />
        <div className="msky-in">
          <div className="msky-hint">Scroll the sky</div>

          {view.branches.map((branch) => {
            const groups = branchGroups(view, branch.slot_id)
            const capNode = nodesById.get(branch.capstone_node_id)
            const proven = branch.capstone_tier === 'proven'
            return (
              <section key={branch.slot_id}>
                <div className="m-region">
                  <h3 className={`m-rlabel${proven ? ' lit' : ''}`}>{branch.title}</h3>
                </div>
                {capNode && (
                  <CapstoneCard
                    node={capNode}
                    proven={proven}
                    onSelect={() => selectNode(capNode.node_id)}
                  />
                )}
                {groups.map(renderSystem)}
              </section>
            )
          })}

          {core.length > 0 && (
            <section>
              <div className="m-region">
                <h3 className="m-rlabel">Core — shared ground</h3>
              </div>
              {core.map(renderSystem)}
            </section>
          )}

          {personalGroups.length > 0 && (
            <section>
              <h3 className="m-yours">Your additions</h3>
              {personalGroups.map(renderSystem)}
            </section>
          )}

          <div className="m-plaq">
            <div className="n">{pathwayName.toUpperCase()}</div>
            <div className="c">
              {plaque.branches} branches · {plaque.systems} systems · {plaque.worlds} worlds ·{' '}
              {plaque.capstones} capstones
            </div>
            <div className="c">
              {plaque.honed} honed · {plaque.proven} proven · {plaque.capstonesProven} of{' '}
              {plaque.capstones} capstones proven
            </div>
          </div>
        </div>

        {dark && (
          <div className="m-empty card">
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
  )
}
