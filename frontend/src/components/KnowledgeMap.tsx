import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type {
  AddableSkill,
  KnowledgeGroupView,
  KnowledgeMapView,
  KnowledgeNodeView,
} from '../api/types'
import {
  branchCountLabel,
  branchGroups,
  coreGroups,
  groupCountLabel,
  groupNodes,
  isMastered,
  partitionGroups,
  tierLabel,
} from '../lib/knowledgeMap'

// The knowledge map (KT-D): branches (one per evidence slot) → group waypoints
// that expand inline (accordion) into their skill nodes on the gilding ramp, then
// the personal "Your additions" layer. Honest counts only, never percentages —
// every count and tier is the narrative kernel's output carried on the view. The
// personal layer counts toward nothing and never enters a prompt (06-…): "Add a
// skill" (pathway content, placed deterministically by our grouping) is map-level;
// custom groups/nodes are the user's own placement.

/** A member skill/custom node row. */
function NodeRow({
  node,
  selected,
  onSelect,
}: {
  node: KnowledgeNodeView
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      className={`km-node km-t-${node.tier}${node.is_personal ? ' custom' : ''}${selected ? ' sel' : ''}`}
      onClick={onSelect}
    >
      <span className="km-dot" />
      <span className="km-nname">{node.title}</span>
      <span className="km-ntier">{tierLabel(node.tier)}</span>
    </button>
  )
}

function waypointClass(group: KnowledgeGroupView): string {
  if (group.total_count === 0 || group.honed_count === 0) return 'km-wp-0'
  return group.honed_count >= group.total_count ? 'km-wp-full' : 'km-wp-part'
}

/** The "Add a skill" picker — the closed add-vocabulary (track slice ∩ placeable −
 *  already-present). Loaded on open; a pick calls add-node (server places it by its
 *  grouping row) and hands back the refreshed map. */
function AddSkillPicker({
  onMutate,
  busy,
}: {
  onMutate: (fn: () => Promise<KnowledgeMapView>) => void
  busy: boolean
}) {
  const [skills, setSkills] = useState<AddableSkill[] | null>(null)
  const [query, setQuery] = useState('')
  const [loadError, setLoadError] = useState(false)

  useEffect(() => {
    api
      .addVocabulary()
      .then((res) => setSkills(res.skills))
      .catch(() => setLoadError(true))
  }, [])

  const filtered = (skills ?? []).filter((s) =>
    s.title.toLowerCase().includes(query.trim().toLowerCase()),
  )

  return (
    <div className="km-inline-form">
      <div className="label" style={{ color: 'var(--clay-deep)' }}>
        Add a skill
      </div>
      <p className="muted" style={{ fontSize: 11.5, margin: '6px 0 0', lineHeight: 1.5 }}>
        Pick from your track&rsquo;s vocabulary; we place it in the right group. It becomes a
        first-class planning target next time you regenerate.
      </p>
      {loadError ? (
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          Couldn&rsquo;t load the skill list — try again in a moment.
        </p>
      ) : skills === null ? (
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          Loading…
        </p>
      ) : skills.length === 0 ? (
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          Every skill in your track&rsquo;s vocabulary is already on your map.
        </p>
      ) : (
        <>
          <input
            className="input"
            style={{ marginTop: 8 }}
            aria-label="search skills to add"
            placeholder="Search skills…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <div className="km-pick">
            {filtered.map((s) => (
              <button
                key={s.skill_id}
                type="button"
                disabled={busy}
                onClick={() => onMutate(() => api.addKnowledgeNode(s.skill_id))}
              >
                {s.title}
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="muted" style={{ fontSize: 12 }}>
                No match.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  )
}

/** A small named-entity form (custom group / custom node). */
function CreateForm({
  title,
  withDescription,
  submitLabel,
  busy,
  onSubmit,
}: {
  title: string
  withDescription?: boolean
  submitLabel: string
  busy: boolean
  onSubmit: (name: string, description: string) => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  return (
    <div className="km-inline-form">
      <div className="label" style={{ color: 'var(--clay-deep)' }}>
        {title}
      </div>
      <input
        className="input"
        style={{ marginTop: 8 }}
        aria-label={`${title} name`}
        placeholder="Name"
        maxLength={60}
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      {withDescription && (
        <input
          className="input"
          style={{ marginTop: 8 }}
          aria-label={`${title} description`}
          placeholder="Description (optional)"
          maxLength={500}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
      )}
      <button
        type="button"
        className="btn btn-primary sm"
        style={{ marginTop: 10 }}
        disabled={busy || name.trim().length === 0}
        onClick={() => onSubmit(name.trim(), description.trim())}
      >
        {submitLabel}
      </button>
    </div>
  )
}

export function KnowledgeMap({
  view,
  selectedNodeId,
  onSelectNode,
  onMutate,
  busy,
}: {
  view: KnowledgeMapView
  selectedNodeId: string | null
  onSelectNode: (nodeId: string) => void
  onMutate: (fn: () => Promise<KnowledgeMapView>) => void
  busy: boolean
}) {
  const [openGroups, setOpenGroups] = useState<Set<string>>(new Set())
  // Which inline affordance is open: 'add-skill', 'new-group', or `node:<groupId>`.
  const [panel, setPanel] = useState<string | null>(null)

  const toggleGroup = (id: string) =>
    setOpenGroups((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const closePanels = () => setPanel(null)
  const { personalGroups } = partitionGroups(view)
  const core = coreGroups(view)

  function renderGroup(group: KnowledgeGroupView, personal: boolean) {
    const open = openGroups.has(group.group_id)
    const nodes = groupNodes(view, group)
    const nodePanel = `node:${group.group_id}`
    return (
      <div key={group.group_id} className={`km-gw${open ? ' open' : ''}`}>
        <div className="row" style={{ gap: 0 }}>
          <button
            type="button"
            className="km-ghead"
            style={{ flex: 1 }}
            aria-expanded={open}
            onClick={() => toggleGroup(group.group_id)}
          >
            <span className={`km-waypoint ${personal ? 'km-wp-0' : waypointClass(group)}`}>
              {personal ? '✎' : `${group.honed_count}/${group.total_count}`}
            </span>
            <span>
              <span className="km-gtitle">{group.title}</span>
              <span className="km-gcount" style={{ display: 'block' }}>
                {personal ? 'personal · counts toward nothing' : groupCountLabel(group)}
                {!personal && group.blurb ? ` · ${group.blurb}` : ''}
              </span>
            </span>
            {!personal && <span className="km-caret">›</span>}
          </button>
          {personal && (
            <button
              type="button"
              aria-label={`delete group ${group.title}`}
              className="btn btn-quiet sm"
              style={{ flex: 'none', marginRight: 8 }}
              disabled={busy}
              onClick={() => onMutate(() => api.deleteCustomGroup(group.group_id))}
            >
              ✕
            </button>
          )}
        </div>
        {open && (
          <div className="km-members">
            {nodes.map((n) => (
              <NodeRow
                key={n.node_id}
                node={n}
                selected={selectedNodeId === n.node_id}
                onSelect={() => onSelectNode(n.node_id)}
              />
            ))}
            {nodes.length === 0 && (
              <p className="muted" style={{ fontSize: 12, padding: '4px 0' }}>
                No nodes yet.
              </p>
            )}
            {panel === nodePanel ? (
              <CreateForm
                title="New node"
                withDescription
                submitLabel="Create node"
                busy={busy}
                onSubmit={(name, description) => {
                  onMutate(() =>
                    api.createCustomNode({ name, groupId: group.group_id, description: description || null }),
                  )
                  closePanels()
                }}
              />
            ) : (
              <button
                type="button"
                className="btn btn-soft sm"
                style={{ marginTop: 4, alignSelf: 'flex-start' }}
                onClick={() => setPanel(nodePanel)}
              >
                + New node
              </button>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <div>
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
        <span className="spacer" />
        <span className="muted" style={{ fontSize: 11.5 }}>
          Study lights a branch from the roots; proof crowns it.
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
            closePanels()
          }}
        />
      )}

      {view.branches.map((branch) => (
        <div key={branch.slot_id} className="km-branch">
          <div className="km-bhead">
            <div className={`km-shield ${branch.capstone_tier === 'proven' ? 'proven' : 'unproven'}`}>
              {branch.capstone_tier === 'proven' ? '✦' : '◇'}
            </div>
            <div>
              <div className="km-bname">{branch.title}</div>
              <div className="km-bmeta">{branchCountLabel(branch)}</div>
            </div>
          </div>
          <div className="km-groups">
            {branchGroups(view, branch.slot_id).map((g) => renderGroup(g, false))}
          </div>
        </div>
      ))}

      {core.length > 0 && (
        <div className="km-branch">
          <div className="km-bhead">
            <div className="km-shield unproven">⌂</div>
            <div>
              <div className="km-bname">Core foundations</div>
              <div className="km-bmeta">Shared across pillars — no single capstone</div>
            </div>
          </div>
          <div className="km-groups">{core.map((g) => renderGroup(g, false))}</div>
        </div>
      )}

      {personalGroups.length > 0 && (
        <div className="km-additions">
          <div className="km-ahead">
            <span className="label" style={{ color: 'var(--ink-soft)' }}>
              Your additions
            </span>
            <span className="muted" style={{ fontSize: 11.5 }}>
              Personal groups &amp; nodes — never counted, never in a prompt.
            </span>
          </div>
          <div className="km-groups" style={{ border: 'none', borderRadius: 'var(--r-sm)' }}>
            {personalGroups.map((g) => renderGroup(g, true))}
          </div>
        </div>
      )}

      {view.nodes.filter((n) => isMastered(n.tier)).length > 0 && (
        <p className="muted" style={{ fontSize: 11.5, marginTop: 14 }}>
          Honed nodes are done — the next plan won&rsquo;t re-assign them as primary study.
        </p>
      )}
    </div>
  )
}
