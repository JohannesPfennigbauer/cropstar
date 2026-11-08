// Geometry of the Activities spiral, in stage pixels (960 × 640, scaled to fit by the component).
// An elliptical spiral growing towards the lower left: it starts left of the centre, turns counter-clockwise
// for about 1.3 rounds, ends at the bottom and runs out horizontally to the right for a short stretch.
// Card size grows along the path, so the back is small and dense and the front large and wide.

export const SPIRAL_W = 960
export const SPIRAL_H = 640
/** Where the horizontal front stretch ends. */
export const SPIRAL_TAIL_END = 690
/** Cards fade in over this stretch at the inner end and fade out over this stretch before the tail end. */
export const SPIRAL_FADE_IN_PX = 140
export const SPIRAL_FADE_OUT_PX = 220

const THETA0 = (175 * Math.PI) / 180
const THETA1 = (630 * Math.PI) / 180
const START = { cx: 439, cy: 204, a: 170, b: 70 }
const END = { cx: 391, cy: 273, a: 272, b: 120 }
const Y_MID = 273
const SCALE_BACK = 0.22
const SCALE_FRONT = 1
/** Tilt of the spiral plane, 0 (from above) to 1 (flattest). The shape is drawn for 0.75 and squashed from there. */
const TILT = 1
const SQUASH = (1 - 0.6 * TILT) / (1 - 0.6 * 0.75)

export interface SpiralPoint { x: number, y: number, s: number, depthScale: number, phase: 'spiral' | 'tail' }

export interface SpiralPath {
  pts: SpiralPoint[]
  spiralEndIndex: number
  /** G(s) = ∫ ds / card size: counts card slots, so equal steps in G give a card equal room. */
  G: number[]
  /** G at the frontmost place where a card is still fully visible. */
  frontG: number
  /** Card size along the path (0.22 at the inner end, 1 at the front), without tilt. */
  sizeAt: (s: number) => number
  /** Index of the path point where G reaches `target`; -1 outside the path. */
  indexAtG: (target: number) => number
}

const lerp = (from: number, to: number, u: number) => from + (to - from) * u

export function buildSpiralPath(): SpiralPath {
  const pts: SpiralPoint[] = []
  let s = 0
  const push = (x: number, y: number, depthScale: number, phase: SpiralPoint['phase']) => {
    const prev = pts[pts.length - 1]
    if (prev) s += Math.hypot(x - prev.x, y - prev.y)
    pts.push({ x, y, s, depthScale, phase })
  }
  for (let i = 0; i <= 1600; i++) {
    const u = i / 1600
    const t = THETA0 + (THETA1 - THETA0) * u
    const y = lerp(START.cy, END.cy, u) - lerp(START.b, END.b, u) * Math.sin(t)
    const depthScale = 1 + 0.15 * TILT * ((y - Y_MID) / END.b)
    push(lerp(START.cx, END.cx, u) + lerp(START.a, END.a, u) * Math.cos(t), Y_MID + (y - Y_MID) * SQUASH, depthScale, 'spiral')
  }
  const spiralEndIndex = pts.length - 1
  const end = pts[spiralEndIndex]!
  for (let i = 1; i <= 160; i++) push(end.x + ((SPIRAL_TAIL_END - end.x) * i) / 160, end.y, end.depthScale, 'tail')

  const spiralEnd = end.s
  const sizeAt = (at: number) => SCALE_BACK + (SCALE_FRONT - SCALE_BACK) * Math.min(1, Math.max(0, at / spiralEnd))

  const G: number[] = [0]
  for (let i = 1; i < pts.length; i++) {
    const mid = (pts[i]!.s + pts[i - 1]!.s) / 2
    G.push(G[i - 1]! + (pts[i]!.s - pts[i - 1]!.s) / sizeAt(mid))
  }

  function indexAtG(target: number): number {
    if (!(target >= 0) || target > G[G.length - 1]!) return -1
    let lo = 0
    let hi = G.length - 1
    while (hi - lo > 1) {
      const mid = (lo + hi) >> 1
      if (G[mid]! < target) lo = mid
      else hi = mid
    }
    return hi
  }

  const frontIndex = pts.findIndex(p => p.phase === 'tail' && p.x >= SPIRAL_TAIL_END - SPIRAL_FADE_OUT_PX)
  const frontG = G[frontIndex < 0 ? G.length - 1 : frontIndex]!

  return { pts, spiralEndIndex, G, frontG, sizeAt, indexAtG }
}
