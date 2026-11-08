<script setup lang="ts">
import type { Activity } from '~/utils/activities'
import type { SpiralPoint } from '~/utils/activity-spiral'

/**
 * A Plot's Activities on a spiral: past inside, future outside, undated Tasks at the front end.
 * Cards keep a minimum distance; the band between them is a timeline coloured by the ground cover,
 * stretched where much happens and compressed in long pauses. Month ticks give a sense of time, not a scale.
 */
const props = defineProps<{ activities: Activity[] }>()
const emit = defineEmits<{ select: [activity: Activity] }>()

const { t, locale } = useI18n()
const { coverAt, look } = useActivityCover(() => props.activities)

// The part of the 960 × 640 stage the spiral actually uses, so it shrinks less in a narrow panel.
const VIEW = { x: 30, y: 135, w: 780, h: 360 }
const { frame, fit } = useFitToWidth(VIEW.w)
// 17 cards fit on the spiral at full size. In a narrow panel cards are partly enlarged again and
// fewer of them fit, keeping the ratio of card size to spacing.
const CARDS_ON_SPIRAL = 17
const boost = computed(() => Math.min(1.6, Math.max(1, 1 / Math.sqrt(fit.value))))
const slots = computed(() => Math.max(8, Math.round(CARDS_ON_SPIRAL / boost.value)))

const geo = buildSpiralPath()
const spiralG = geo.G[geo.spiralEndIndex]!
const perSlot = computed(() => spiralG / (slots.value - 1))

const ordered = computed(() => chronological(props.activities))
const layout = computed(() => layoutTimeline(ordered.value))
const today = isoToDay(todayIso())

// Starts with today a little past the middle of the spiral, or with the latest Activity in front.
const initialOffset = () => layout.value.slotAtDay(today) - slots.value * 0.6 || Infinity
const { offset, nudge, reset } = useSmoothOffset(
  initialOffset(),
  // From the earliest to the latest Activity standing at the front, fully visible.
  () => [layout.value.firstSlot - geo.frontG / perSlot.value, layout.value.lastSlot - geo.frontG / perSlot.value]
)
// The number of slots follows the panel width; start over once it is known.
watch(slots, () => reset(initialOffset()))

function onWheel(event: WheelEvent) {
  if (nudge(event.deltaY / 120)) event.preventDefault()
}

const slotToG = (slot: number) => (slot - offset.value) * perSlot.value
const gToSlot = (g: number) => g / perSlot.value + offset.value

const bandWidth = (p: SpiralPoint) => (3 + 14 * geo.sizeAt(p.s)) * p.depthScale
const backFade = (p: SpiralPoint) => Math.max(0, Math.min(1, p.s / SPIRAL_FADE_IN_PX))
const frontFade = (p: SpiralPoint) => (p.phase === 'tail' ? Math.max(0, Math.min(1, (SPIRAL_TAIL_END - p.x) / SPIRAL_FADE_OUT_PX)) : 1)
const fade = (p: SpiralPoint) => Math.min(backFade(p), frontFade(p))

const bandEndIndex = computed(() => {
  const g = slotToG(layout.value.bandEndSlot)
  const index = geo.indexAtG(g)
  if (index >= 0) return index
  return g < 0 ? 0 : geo.pts.length - 1
})

const band = computed(() => {
  const out = []
  for (let i = 0; i < bandEndIndex.value; i += 3) {
    const a = geo.pts[i]!
    const b = geo.pts[Math.min(i + 3, bandEndIndex.value)]!
    out.push({
      x1: a.x, y1: a.y, x2: b.x, y2: b.y,
      width: bandWidth(a),
      color: coverAt.value(layout.value.dayAtSlot(gToSlot(geo.G[i]!))).color,
      opacity: fade(a)
    })
  }
  return out
})

const leash = computed(() => geo.pts
  .slice(bandEndIndex.value)
  .filter((_, i) => i % 6 === 0)
  .map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
  .join(' '))

// Outward normal at a path index, so labels sit outside the band.
function normalAt(index: number) {
  const a = geo.pts[Math.max(0, index - 2)]!
  const b = geo.pts[Math.min(geo.pts.length - 1, index + 2)]!
  const length = Math.hypot(b.x - a.x, b.y - a.y) || 1
  let nx = -(b.y - a.y) / length
  let ny = (b.x - a.x) / length
  const p = geo.pts[index]!
  if (nx * (p.x - 420) + ny * (p.y - 260) < 0) {
    nx = -nx
    ny = -ny
  }
  return { nx, ny }
}

function indexAtDay(day: number): number {
  const index = geo.indexAtG(slotToG(layout.value.slotAtDay(day)))
  return index > bandEndIndex.value ? -1 : index
}

const monthName = computed(() => new Intl.DateTimeFormat(locale.value === 'en' ? 'en-GB' : 'de-AT', { month: 'short', timeZone: 'UTC' }))

interface Tick {
  key: string
  x1: number
  y1: number
  x2: number
  y2: number
  quarter: boolean
  opacity: number
  label: string | null
  lx: number
  ly: number
  fontSize: number
  month: { x: number, y: number, text: string, fontSize: number } | null
}

const ticks = computed(() => {
  const out: Tick[] = []
  if (!Number.isFinite(layout.value.bandEndSlot)) return out
  const first = new Date(layout.value.dayAtSlot(offset.value) * 86_400_000)
  const lastDay = layout.value.dayAtSlot(Math.min(layout.value.bandEndSlot, gToSlot(geo.G[geo.G.length - 1]!)))
  let year = first.getUTCFullYear()
  let month = first.getUTCMonth() + 1
  // Bounded loop: a window never spans more than a few years.
  for (let guard = 0; guard < 120; guard++, month++) {
    if (month > 11) {
      month = 0
      year++
    }
    const day = Date.UTC(year, month, 1) / 86_400_000
    if (!(day <= lastDay)) break
    const index = indexAtDay(day)
    if (index < 0) continue
    const p = geo.pts[index]!
    const { nx, ny } = normalAt(index)
    const quarter = month % 3 === 0
    const half = (bandWidth(p) / 2) * (quarter ? 1.7 : 1.15)
    const size = geo.sizeAt(p.s)
    const mid = indexAtDay(day + 15)
    const next = indexAtDay(Date.UTC(year, month + 1, 1) / 86_400_000)
    const roomy = mid >= 0 && next >= 0 && bandWidth(geo.pts[mid]!) >= 11 && geo.pts[next]!.s - p.s > 34
    out.push({
      key: `${year}-${month}`,
      x1: p.x - nx * half, y1: p.y - ny * half, x2: p.x + nx * half, y2: p.y + ny * half,
      quarter,
      opacity: fade(p),
      label: quarter ? `Q${month / 3 + 1}${month === 0 ? ` ${year}` : ''}` : null,
      lx: p.x + nx * (half + 4 + 8 * size),
      ly: p.y + ny * (half + 4 + 8 * size),
      fontSize: 8 + 6 * size,
      month: roomy
        ? { x: geo.pts[mid]!.x, y: geo.pts[mid]!.y, text: monthName.value.format(new Date(day * 86_400_000)), fontSize: bandWidth(geo.pts[mid]!) * 0.62 }
        : null
    })
  }
  return out
})

const placed = computed(() => ordered.value
  .map((activity) => {
    const slot = layout.value.slotOf.get(activity.key)!
    const index = geo.indexAtG(slotToG(slot))
    if (index < 0) return null
    const p = geo.pts[index]!
    const opacity = fade(p)
    if (opacity <= 0) return null
    const onBand = slot <= layout.value.bandEndSlot
    return {
      activity,
      x: p.x,
      y: p.y + (onBand ? bandWidth(p) / 2 : 0),
      scale: geo.sizeAt(p.s) * p.depthScale * boost.value,
      opacity,
      ...look(activity)
    }
  })
  .filter(p => p !== null)
  .sort((a, b) => a.scale - b.scale))

// Harvest Year transitions, marked like the start of a calendar year but dashed and labelled inside.
const harvestYearMarks = computed(() => harvestYearTransitions(ordered.value, layout.value).flatMap(({ slot, harvestYear }) => {
  const index = geo.indexAtG(slotToG(slot))
  if (index < 0 || index > bandEndIndex.value) return []
  const p = geo.pts[index]!
  const { nx, ny } = normalAt(index)
  const half = (bandWidth(p) / 2) * 1.9
  const size = geo.sizeAt(p.s)
  return [{
    key: harvestYear,
    x1: p.x - nx * half, y1: p.y - ny * half, x2: p.x + nx * half, y2: p.y + ny * half,
    lx: p.x - nx * (half + 4 + 8 * size),
    ly: p.y - ny * (half + 4 + 8 * size),
    fontSize: 8 + 6 * size,
    label: t('app.activities.harvestYear', { year: harvestYear }),
    opacity: fade(p)
  }]
}))

const todayMark = computed(() => {
  if (!Number.isFinite(layout.value.bandEndSlot)) return null
  const index = indexAtDay(today)
  if (index < 0) return null
  const p = geo.pts[index]!
  const { nx, ny } = normalAt(index)
  const half = bandWidth(p) / 2 + 6
  return { x1: p.x - nx * half, y1: p.y - ny * half, x2: p.x + nx * half, y2: p.y + ny * half, lx: p.x + nx * (half + 4), ly: p.y + ny * (half + 4), opacity: fade(p) }
})
</script>

<template>
  <div class="mt-2">
    <div
      ref="frame"
      class="relative w-full overflow-hidden rounded-md border border-default bg-paper select-none"
      :style="{ height: `${VIEW.h * fit}px` }"
      data-testid="plot-activities-spiral"
      @wheel="onWheel"
    >
      <div
        class="absolute top-0 left-0"
        :style="{
          width: `${SPIRAL_W}px`,
          height: `${SPIRAL_H}px`,
          transform: `scale(${fit}) translate(${-VIEW.x}px, ${-VIEW.y}px)`,
          transformOrigin: 'top left'
        }"
      >
        <svg
          :width="SPIRAL_W"
          :height="SPIRAL_H"
          class="absolute inset-0"
          style="pointer-events: none"
          aria-hidden="true"
        >
          <line
            v-for="(seg, i) in band"
            :key="`b${i}`"
            :x1="seg.x1"
            :y1="seg.y1"
            :x2="seg.x2"
            :y2="seg.y2"
            :stroke="seg.color"
            :stroke-width="seg.width"
            :stroke-opacity="seg.opacity"
            stroke-linecap="round"
          />
          <path
            :d="leash"
            fill="none"
            stroke="var(--color-soil-500)"
            stroke-width="2"
            stroke-dasharray="1 5"
            stroke-linecap="round"
          />
          <g
            v-for="tick in ticks"
            :key="`t${tick.key}`"
            :opacity="tick.opacity"
          >
            <text
              v-if="tick.month"
              :x="tick.month.x"
              :y="tick.month.y"
              :font-size="tick.month.fontSize"
              fill="var(--color-charcoal)"
              fill-opacity="0.55"
              text-anchor="middle"
              dominant-baseline="central"
            >{{ tick.month.text }}</text>
            <line
              :x1="tick.x1"
              :y1="tick.y1"
              :x2="tick.x2"
              :y2="tick.y2"
              stroke="var(--color-charcoal)"
              :stroke-width="tick.quarter ? 2.2 : 1"
              :stroke-opacity="tick.quarter ? 0.85 : 0.45"
            />
            <text
              v-if="tick.label"
              :x="tick.lx"
              :y="tick.ly"
              :font-size="tick.fontSize"
              fill="var(--color-charcoal)"
              text-anchor="middle"
              dominant-baseline="central"
              class="font-display font-semibold"
            >{{ tick.label }}</text>
          </g>
          <g
            v-for="mark in harvestYearMarks"
            :key="`h${mark.key}`"
            :opacity="mark.opacity"
            data-testid="harvest-year-mark"
          >
            <line
              :x1="mark.x1"
              :y1="mark.y1"
              :x2="mark.x2"
              :y2="mark.y2"
              stroke="var(--color-soil-800)"
              stroke-width="2.5"
              stroke-dasharray="4 3"
            />
            <text
              :x="mark.lx"
              :y="mark.ly"
              :font-size="mark.fontSize"
              fill="var(--color-soil-800)"
              text-anchor="middle"
              dominant-baseline="central"
              class="font-display font-semibold"
            >{{ mark.label }}</text>
          </g>
          <g
            v-if="todayMark"
            :opacity="todayMark.opacity"
          >
            <line
              :x1="todayMark.x1"
              :y1="todayMark.y1"
              :x2="todayMark.x2"
              :y2="todayMark.y2"
              stroke="var(--color-charcoal)"
              stroke-width="3.5"
              stroke-linecap="round"
            />
            <text
              :x="todayMark.lx"
              :y="todayMark.ly"
              fill="var(--color-charcoal)"
              dominant-baseline="central"
              class="font-display text-sm font-semibold"
            >{{ t('app.activities.today') }}</text>
          </g>
        </svg>
        <div
          v-for="p in placed"
          :key="p.activity.key"
          class="absolute top-0 left-0"
          :style="{
            transform: `translate(${p.x}px, ${p.y}px) translate(-50%, 0) scale(${p.scale})`,
            transformOrigin: 'top center',
            opacity: p.opacity
          }"
        >
          <AppActivityCard
            :activity="p.activity"
            :background="p.background"
            :why="p.why"
            @select="emit('select', p.activity)"
          />
        </div>
      </div>
    </div>
    <p class="mt-1 text-xs text-muted">
      {{ t('app.activities.scrollHint') }}
    </p>
  </div>
</template>
