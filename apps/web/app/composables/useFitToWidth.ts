/** Scale factor (≤ 1) that fits a stage of `width` pixels into the observed element. */
export function useFitToWidth(width: number) {
  const frame = ref<HTMLElement | null>(null)
  const fit = ref(1)
  let observer: ResizeObserver | null = null
  onMounted(() => {
    observer = new ResizeObserver(([entry]) => {
      if (entry) fit.value = Math.min(1, entry.contentRect.width / width)
    })
    if (frame.value) observer.observe(frame.value)
  })
  onBeforeUnmount(() => observer?.disconnect())
  return { frame, fit }
}
