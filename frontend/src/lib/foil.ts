/* Holographic foil button effect — engine.
   One window-level mousemove listener and one requestAnimationFrame loop drive
   every registered element. Per frame each element lerps toward a target
   computed from the cursor's distance to it, so the shine eases in before the
   cursor arrives and eases out past the falloff radius — never snapping at
   enter/leave boundaries. The engine writes only compositor-friendly state:
   a perspective transform plus the --fx/--fy/--fi custom properties that the
   .btn-foil CSS layers (tokens.css) consume. React binding: components/FoilButton. */

export type FoilShape = 'spot' | 'bar' | 'conic' | 'diamond'
export type FoilPalette = 'iridescent' | 'gold' | 'silver'

export interface FoilOptions {
  /** Base coat + rainbow hue set. */
  palette?: FoilPalette
  /** Geometry of the moving glare layer. */
  shape?: FoilShape
  /** Max tilt in degrees at full strength. */
  maxTilt?: number
  /** Distance in px beyond the element edge where the effect eases to zero. */
  falloff?: number
  /** 0..1 scale on shine opacity. */
  intensity?: number
  /** Per-frame lerp factor toward the target (0..1; higher = snappier). */
  smoothing?: number
  /** bar shape: streak angle in degrees. */
  barAngle?: number
  /** bar shape: streak half-width in % of the face. */
  barWidth?: number
  /** spot shape: % stop where the glare fades out (higher = softer). */
  spotSoftness?: number
}

const DEFAULTS: Required<FoilOptions> = {
  palette: 'iridescent',
  shape: 'spot',
  maxTilt: 10,
  falloff: 260,
  intensity: 1,
  smoothing: 0.1,
  barAngle: 115,
  barWidth: 18,
  spotSoftness: 55,
}

/* ——— Pure math (unit-tested in foil.test.ts) ——— */

export interface FoilFrame {
  /** rotateX / rotateY in degrees. */
  rx: number
  ry: number
  /** Shine position in % of the face (50 = center). */
  px: number
  py: number
  /** Effect strength 0..1 after distance falloff. */
  strength: number
}

export const FOIL_REST: FoilFrame = { rx: 0, ry: 0, px: 50, py: 50, strength: 0 }

export interface RectLike {
  left: number
  top: number
  width: number
  height: number
}

export function clamp(v: number, min: number, max: number): number {
  return v < min ? min : v > max ? max : v
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t
}

/** Hermite ease of x across [edge0, edge1], returning 0..1. */
export function smoothstep(edge0: number, edge1: number, x: number): number {
  const t = clamp((x - edge0) / (edge1 - edge0), 0, 1)
  return t * t * (3 - 2 * t)
}

/** Distance from a point to the rectangle's nearest edge (0 inside). */
export function edgeDistance(rect: RectLike, x: number, y: number): number {
  const dx = Math.max(rect.left - x, 0, x - (rect.left + rect.width))
  const dy = Math.max(rect.top - y, 0, y - (rect.top + rect.height))
  return Math.hypot(dx, dy)
}

/** Target frame for one element given the cursor (null = cursor gone → rest). */
export function computeFoilTarget(
  rect: RectLike,
  mouse: { x: number; y: number } | null,
  opts: { maxTilt: number; falloff: number },
): FoilFrame {
  if (!mouse || rect.width <= 0 || rect.height <= 0) return FOIL_REST
  const dist = edgeDistance(rect, mouse.x, mouse.y)
  const strength = 1 - smoothstep(0, opts.falloff, dist)
  if (strength <= 0) return FOIL_REST
  // Offset from center, normalized so ±1 is the element edge. Tilt clamps at
  // the edge; the shine position overshoots slightly so the glare keeps
  // drifting in the cursor's direction just past the face.
  const nx = (mouse.x - (rect.left + rect.width / 2)) / (rect.width / 2)
  const ny = (mouse.y - (rect.top + rect.height / 2)) / (rect.height / 2)
  return {
    rx: -clamp(ny, -1, 1) * opts.maxTilt * strength,
    ry: clamp(nx, -1, 1) * opts.maxTilt * strength,
    px: 50 + clamp(nx, -1.2, 1.2) * 50,
    py: 50 + clamp(ny, -1.2, 1.2) * 50,
    strength,
  }
}

/* ——— Singleton registry + animation loop ——— */

interface Instance {
  el: HTMLElement
  opts: Required<FoilOptions>
  cur: FoilFrame
  rect: RectLike
}

const EPS = 0.005
const instances = new Set<Instance>()
let mouse: { x: number; y: number } | null = null
let rafId = 0
let listening = false
let reducedMotion: MediaQueryList | null = null

function wake(): void {
  if (rafId === 0 && instances.size > 0) rafId = requestAnimationFrame(frame)
}

function onMouseMove(ev: MouseEvent): void {
  mouse = { x: ev.clientX, y: ev.clientY }
  wake()
}

function onMouseGone(): void {
  mouse = null
  wake()
}

function onScroll(): void {
  if (mouse) wake()
}

function frame(): void {
  rafId = 0
  const reduce = reducedMotion?.matches ?? false
  // Read every rect first, then write, so writes never interleave with layout reads.
  for (const inst of instances) inst.rect = inst.el.getBoundingClientRect()
  let settled = true
  for (const inst of instances) {
    const disabled = inst.el.matches(':disabled')
    const target =
      reduce || disabled ? FOIL_REST : computeFoilTarget(inst.rect, mouse, inst.opts)
    const t = inst.opts.smoothing
    const c = inst.cur
    c.rx = lerp(c.rx, target.rx, t)
    c.ry = lerp(c.ry, target.ry, t)
    c.px = lerp(c.px, target.px, t)
    c.py = lerp(c.py, target.py, t)
    c.strength = lerp(c.strength, target.strength, t)
    if (
      Math.abs(c.rx - target.rx) > EPS ||
      Math.abs(c.ry - target.ry) > EPS ||
      Math.abs(c.px - target.px) > EPS * 10 ||
      Math.abs(c.py - target.py) > EPS * 10 ||
      Math.abs(c.strength - target.strength) > EPS
    ) {
      settled = false
    }
    apply(inst)
  }
  if (!settled) rafId = requestAnimationFrame(frame)
}

function apply(inst: Instance): void {
  const { el, cur, opts } = inst
  const style = el.style
  if (Math.abs(cur.rx) > EPS || Math.abs(cur.ry) > EPS) {
    style.transform = `perspective(700px) rotateX(${cur.rx.toFixed(3)}deg) rotateY(${cur.ry.toFixed(3)}deg)`
  } else {
    style.transform = ''
  }
  style.setProperty('--fx', `${cur.px.toFixed(2)}%`)
  style.setProperty('--fy', `${cur.py.toFixed(2)}%`)
  style.setProperty('--fi', (cur.strength * opts.intensity).toFixed(3))
}

function startListening(): void {
  if (listening) return
  listening = true
  window.addEventListener('mousemove', onMouseMove, { passive: true })
  window.addEventListener('blur', onMouseGone)
  document.documentElement.addEventListener('mouseleave', onMouseGone)
  // Capture so scrolls inside nested containers (which do not bubble) also
  // refresh cached rects while the cursor is stationary.
  window.addEventListener('scroll', onScroll, { passive: true, capture: true })
  reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
  reducedMotion.addEventListener('change', wake)
}

function stopListening(): void {
  if (!listening) return
  listening = false
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('blur', onMouseGone)
  document.documentElement.removeEventListener('mouseleave', onMouseGone)
  window.removeEventListener('scroll', onScroll, { capture: true })
  reducedMotion?.removeEventListener('change', wake)
  reducedMotion = null
  if (rafId !== 0) {
    cancelAnimationFrame(rafId)
    rafId = 0
  }
}

/** Attach the foil effect to an element. Returns the unregister function.
    Adds the .btn-foil class plus data-foil-* attributes; underlying behavior
    (clicks, focus, keyboard, disabled) is untouched. */
export function registerFoil(el: HTMLElement, options: FoilOptions = {}): () => void {
  const opts = { ...DEFAULTS, ...options }
  el.classList.add('btn-foil')
  el.dataset.foilShape = opts.shape
  el.dataset.foilPalette = opts.palette
  el.style.setProperty('--foil-bar-angle', `${opts.barAngle}deg`)
  el.style.setProperty('--foil-bar-width', `${opts.barWidth}%`)
  el.style.setProperty('--foil-spot-soft', `${opts.spotSoftness}%`)
  const inst: Instance = {
    el,
    opts,
    cur: { ...FOIL_REST },
    rect: el.getBoundingClientRect(),
  }
  apply(inst)
  instances.add(inst)
  startListening()
  return () => {
    instances.delete(inst)
    el.classList.remove('btn-foil')
    delete el.dataset.foilShape
    delete el.dataset.foilPalette
    for (const prop of [
      '--fx',
      '--fy',
      '--fi',
      '--foil-bar-angle',
      '--foil-bar-width',
      '--foil-spot-soft',
    ]) {
      el.style.removeProperty(prop)
    }
    el.style.transform = ''
    if (instances.size === 0) stopListening()
  }
}
