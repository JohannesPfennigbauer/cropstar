/**
 * A scroll position that glides towards its target. Components re-place their content from it on every
 * frame instead of relying on CSS transitions, so things moving along a curve stay on the curve.
 */
export function useSmoothOffset(initial: number, bounds: () => [number, number]) {
  const clamp = (value: number) => {
    const [lo, hi] = bounds()
    return Math.max(lo, Math.min(Math.max(lo, hi), value))
  }
  const target = ref(clamp(initial))
  const offset = ref(target.value)
  let frame = 0

  function step() {
    const delta = target.value - offset.value
    if (Math.abs(delta) < 0.002) {
      offset.value = target.value
      frame = 0
      return
    }
    offset.value += delta * 0.2
    frame = requestAnimationFrame(step)
  }

  /** Moves the target; returns false when already at the bound, so the caller can let the page scroll on. */
  function nudge(delta: number): boolean {
    const next = clamp(target.value + delta)
    if (next === target.value) return false
    target.value = next
    if (!frame) frame = requestAnimationFrame(step)
    return true
  }

  /** Jumps to a position without gliding, e.g. after the layout changed. */
  function reset(value: number) {
    target.value = clamp(value)
    offset.value = target.value
  }

  // Bounds move when the layout changes; keep the position inside them.
  watch(bounds, () => reset(target.value))

  onBeforeUnmount(() => cancelAnimationFrame(frame))
  return { offset, nudge, reset }
}
