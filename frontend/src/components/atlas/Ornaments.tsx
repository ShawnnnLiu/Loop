// Star Atlas (SA-E) — the instrument dressing and the two motion ornaments. All
// stylistic, never semantic (`01-visual-language.md`, "Ornaments"). Ported
// verbatim from docs/design-reference/Loop - Star Atlas.html. The math lives in
// pure, vitest-covered helpers (bezelTicks / probeGeometry); these components are
// thin declarative SVG over them. Every animation has a reduced-motion no-op in
// tokens.css, and the bloom is additionally not rendered under reduced motion.
//
// Placement contract (mirrors the reference): InstrumentEdge draws on the fixed
// instrument layer *outside* the pan group, so it never zooms with the sky; Probe
// and Bloom draw *inside* the pan group, so they ride the focus glide. All three
// are aria-hidden — decorative; the mission plaque + count chips are the accessible
// truth (`01-…`).

import { bezelTicks, type ProbeGeometry } from '../../lib/atlas/render'

const TICKS = bezelTicks()

/** The engraved instrument edge: bezel ticks, corner brackets, and the orrery
 *  armillary in the corner. Fixed to the rim (never panned). Pure decoration. */
export function InstrumentEdge() {
  return (
    <g aria-hidden="true">
      <g stroke="rgba(138,111,63,.4)">
        {TICKS.map((t, i) => (
          <line key={i} x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2} />
        ))}
      </g>
      <g stroke="rgba(138,111,63,.55)" fill="none" strokeWidth="1.2">
        <path d="M14 30V14H30" />
        <path d="M1150 14H1166V30" />
        <path d="M14 635V651H30" />
        <path d="M1166 635V651H1150" />
      </g>
      {/* Orrery — a decorative armillary; its two dots orbit under motion. */}
      <g transform="translate(1122,614)" opacity=".75">
        <circle r="5" fill="none" stroke="rgba(138,111,63,.5)" />
        <circle r="11" fill="none" stroke="rgba(138,111,63,.45)" />
        <circle r="17" fill="none" stroke="rgba(138,111,63,.4)" />
        <circle r="1.8" fill="#e8c07a" opacity=".8" />
        <g className="orr1">
          <circle cx="11" cy="0" r="1.3" fill="#cfdae2" opacity=".7" />
        </g>
        <g className="orr2">
          <circle cx="-17" cy="0" r="1.1" fill="#c96f45" opacity=".7" />
        </g>
        <text y="28" textAnchor="middle" className="probelab" opacity=".7">
          ORRERY
        </text>
      </g>
    </g>
  )
}

/** The probe: a small craft drifting toward the next scheduled session's world,
 *  with a `next session · <when>` label. Geometry is precomputed (probeGeometry);
 *  `whenLabel` is the localized session time. Rendered inside the pan group so it
 *  glides with the sky. Omitted entirely by the caller when nothing is scheduled. */
export function Probe({ geo, whenLabel }: { geo: ProbeGeometry; whenLabel: string }) {
  return (
    <g className="drift" aria-hidden="true">
      <g transform={`translate(${geo.x},${geo.y}) rotate(${geo.angle})`}>
        <circle cx="-13" cy="0" r=".9" fill="#cfdae2" opacity=".35" />
        <circle cx="-19" cy="0" r=".8" fill="#cfdae2" opacity=".22" />
        <circle cx="-25" cy="0" r=".7" fill="#cfdae2" opacity=".12" />
        <rect x="-8" y="-1.4" width="4" height="2.8" fill="#8ea1b5" />
        <path d="M-4 -3 L4 0 L-4 3 Z" fill="#cfdae2" />
      </g>
      <text x={geo.labelX} y={geo.labelY} textAnchor="middle" className="probelab">
        next session · {whenLabel}
      </text>
    </g>
  )
}

/** The one-shot tier-up bloom — three expanding rings at a world that just rose a
 *  tier while the view was open. The caller renders this only when motion is
 *  allowed (it is a reward flourish; the reduced-motion path never mounts it, and
 *  the CSS fallback stills it to nothing as a second guard). */
export function Bloom({ x, y }: { x: number; y: number }) {
  return (
    <g className="bloom" pointerEvents="none" aria-hidden="true">
      <circle cx={x} cy={y} r="24" fill="none" stroke="#e8c07a" strokeWidth="2.5" />
      <circle cx={x} cy={y} r="24" fill="none" stroke="#fff3da" strokeWidth="1.2" />
      <circle cx={x} cy={y} r="24" fill="none" stroke="#7abeb6" strokeWidth="1" />
    </g>
  )
}
