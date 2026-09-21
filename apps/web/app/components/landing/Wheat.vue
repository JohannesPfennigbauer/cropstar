<script setup lang="ts">
import type { Outcome } from '~/utils/illustrative-response'

const props = defineProps<{ outcome: Outcome }>()

const { t } = useI18n()

const GROUND_Y = 258
const CENTRE_X = 150
const CANVAS_HEIGHT = 420

const STEM_OFFSETS = [0, -32, 26, -54, 48]
const STEM_LEANS = [-6, -18, 14, -26, 22]
const STEM_SCALES = [1, 0.93, 0.88, 0.8, 0.74]
const ROOT_FAN = [-28, -12, 12, 28]

const LEAF_STARVED = '#c9c364'
const LEAF_FED = '#2f6b2f'
const LEAF_PARCHED = '#a8905f'
const EAR_STRAW = '#dcc47e'
const ROOT_PALE = '#efdcb9'
const NITRATE = '#9fd8ef'

/** Deterministic so server and client render identical markup. */
function makeRandom(seed: number): () => number {
  let state = seed
  return () => {
    state = (state * 1664525 + 1013904223) % 4294967296
    return state / 4294967296
  }
}

const random = makeRandom(20260921)
const NITROGEN_SLOTS = Array.from({ length: 24 }, () => ({
  x: 16 + random() * 268,
  depth: 0.08 + random() * 0.84,
  r: 2.6 + random() * 2.4
}))

function toChannels(hex: string): [number, number, number] {
  const value = Number.parseInt(hex.slice(1), 16)
  return [(value >> 16) & 255, (value >> 8) & 255, value & 255]
}

// Returns hex so the result can be fed straight back in as an input.
function mix(from: string, to: string, weight: number): string {
  const w = Math.min(1, Math.max(0, weight))
  const a = toChannels(from)
  const b = toChannels(to)
  const channel = (i: number) => Math.round((a[i] ?? 0) + (((b[i] ?? 0) - (a[i] ?? 0)) * w))
  return `#${[0, 1, 2].map(i => channel(i).toString(16).padStart(2, '0')).join('')}`
}

const droop = computed(() => 1 - props.outcome.waterIndex)

const canopyColour = computed(() => {
  const fed = mix(LEAF_STARVED, LEAF_FED, props.outcome.nitrogenIndex)
  return mix(fed, LEAF_PARCHED, droop.value * 0.6)
})

const earColour = computed(() => mix(canopyColour.value, EAR_STRAW, 0.55))

const stemHeightPx = computed(() => {
  const cm = props.outcome.plantHeight.value
  return 60 + ((cm - 40) / (98 - 40)) * (175 - 60)
})

const rootDepthPx = computed(() => {
  const cm = props.outcome.rootDepthCm
  return 42 + ((cm - 50) / (140 - 50)) * (150 - 42)
})

interface Stem {
  baseX: number
  stem: string
  leaves: string[]
  roots: string[]
  tapRoot: string
  tipX: number
  tipY: number
  angle: number
  earLength: number
}

function quadraticPoint(
  x0: number, y0: number, cx: number, cy: number, x1: number, y1: number, t: number
): [number, number] {
  const u = 1 - t
  return [
    u * u * x0 + 2 * u * t * cx + t * t * x1,
    u * u * y0 + 2 * u * t * cy + t * t * y1
  ]
}

function leafPath(sx: number, sy: number, direction: number, size: number, sag: number): string {
  const tipX = sx + direction * size
  const tipY = sy + 6 + sag * 36
  const upperCx = sx + direction * size * 0.45
  const upperCy = sy - 16 + sag * 28
  const lowerCx = sx + direction * size * 0.5
  const lowerCy = sy + 16 + sag * 30
  return `M ${sx} ${sy} Q ${upperCx} ${upperCy} ${tipX} ${tipY} Q ${lowerCx} ${lowerCy} ${sx} ${sy + 7} Z`
}

const tillerCount = computed(() => 1 + Math.round(props.outcome.canopyIndex * 4))

const stems = computed<Stem[]>(() => {
  const sag = droop.value
  const spread = 0.5 + 0.5 * props.outcome.canopyIndex

  return Array.from({ length: tillerCount.value }, (_, i) => {
    const baseX = CENTRE_X + (STEM_OFFSETS[i] ?? 0) * spread
    const scale = STEM_SCALES[i] ?? 0.8
    const height = stemHeightPx.value * scale
    const lean = (STEM_LEANS[i] ?? 0) * (0.6 + 0.6 * sag)
    const tipX = baseX + lean
    const tipY = GROUND_Y - height
    const cx = baseX + lean * 0.3
    const cy = GROUND_Y - height * 0.55

    const leaves = [0.34, 0.62].map((position, k) => {
      const [lx, ly] = quadraticPoint(baseX, GROUND_Y, cx, cy, tipX, tipY, position)
      const direction = k % 2 === 0 ? 1 : -1
      const size = (40 - k * 8) * (0.6 + 0.4 * props.outcome.canopyIndex)
      return leafPath(lx, ly, direction, size, sag)
    })

    // Each tiller carries its own root system, shorter on the weaker tillers.
    const depth = rootDepthPx.value * (0.55 + 0.45 * scale)
    const roots = ROOT_FAN.map((offset, k) => {
      const end = depth * (0.55 + (k % 2) * 0.25)
      return `M ${baseX} ${GROUND_Y} Q ${baseX + offset * 0.7} ${GROUND_Y + end * 0.5} ${baseX + offset} ${GROUND_Y + end}`
    })

    return {
      baseX,
      stem: `M ${baseX} ${GROUND_Y} Q ${cx} ${cy} ${tipX} ${tipY}`,
      leaves,
      roots,
      tapRoot: `M ${baseX} ${GROUND_Y} Q ${baseX + lean * 0.2} ${GROUND_Y + depth * 0.6} ${baseX - lean * 0.15} ${GROUND_Y + depth}`,
      tipX,
      tipY,
      angle: (Math.atan2(lean, height) * 180) / Math.PI,
      earLength: 30 + 22 * props.outcome.canopyIndex
    }
  })
})

const grainRows = [0, 1, 2, 3, 4, 5]

const nitrogenBubbles = computed(() => {
  const share = Math.min(1, props.outcome.availableN / 80)
  const visible = Math.round(share * NITROGEN_SLOTS.length)
  const soilDepth = CANVAS_HEIGHT - GROUND_Y

  return NITROGEN_SLOTS.slice(0, visible).map((slot, i) => ({
    key: i,
    cx: slot.x,
    cy: GROUND_Y + 10 + slot.depth * (soilDepth - 18),
    r: slot.r
  }))
})

const coverRadius = computed(() => 26 + 92 * props.outcome.canopyIndex)
const coverOpacity = computed(() => 0.08 + 0.2 * props.outcome.canopyIndex)
</script>

<template>
  <svg
    :viewBox="`0 0 300 ${CANVAS_HEIGHT}`"
    class="h-full w-full"
    role="img"
    :aria-label="t('explore.drawingAria')"
  >
    <defs>
      <linearGradient
        id="sky"
        x1="0"
        y1="0"
        x2="0"
        y2="1"
      >
        <stop
          offset="0%"
          stop-color="#eef4f7"
        />
        <stop
          offset="100%"
          stop-color="#f7f6f1"
        />
      </linearGradient>
      <linearGradient
        id="soil"
        x1="0"
        y1="0"
        x2="0"
        y2="1"
      >
        <stop
          offset="0%"
          stop-color="#c7a878"
        />
        <stop
          offset="100%"
          stop-color="#6d4f2e"
        />
      </linearGradient>
    </defs>

    <rect
      x="0"
      y="0"
      width="300"
      :height="CANVAS_HEIGHT"
      fill="url(#sky)"
      rx="12"
    />
    <rect
      x="0"
      :y="GROUND_Y"
      width="300"
      :height="CANVAS_HEIGHT - GROUND_Y"
      fill="url(#soil)"
    />

    <!-- Ground-level shading stands in for fCover. -->
    <ellipse
      :cx="CENTRE_X"
      :cy="GROUND_Y + 4"
      :rx="coverRadius"
      ry="9"
      fill="#3a2a14"
      :opacity="coverOpacity"
      style="transition: all 200ms"
    />

    <!-- Plant-available nitrogen still in the soil. -->
    <g
      :fill="NITRATE"
      stroke="#2b4a5c"
      stroke-width="0.8"
      opacity="0.9"
    >
      <circle
        v-for="bubble in nitrogenBubbles"
        :key="`n-${bubble.key}`"
        :cx="bubble.cx"
        :cy="bubble.cy"
        :r="bubble.r"
      />
    </g>

    <g
      :stroke="ROOT_PALE"
      fill="none"
      stroke-linecap="round"
      opacity="0.7"
    >
      <template
        v-for="(stem, i) in stems"
        :key="`roots-${i}`"
      >
        <path
          v-for="(root, k) in stem.roots"
          :key="`root-${i}-${k}`"
          :d="root"
          stroke-width="1.8"
        />
        <path
          :d="stem.tapRoot"
          stroke-width="2.6"
        />
      </template>
    </g>

    <g
      v-for="(stem, i) in stems"
      :key="`stem-${i}`"
    >
      <path
        v-for="(leaf, k) in stem.leaves"
        :key="`leaf-${i}-${k}`"
        :d="leaf"
        :fill="canopyColour"
        opacity="0.92"
        style="transition: fill 200ms"
      />
      <path
        :d="stem.stem"
        :stroke="canopyColour"
        stroke-width="3.2"
        stroke-linecap="round"
        fill="none"
        style="transition: stroke 200ms"
      />

      <g :transform="`translate(${stem.tipX} ${stem.tipY}) rotate(${stem.angle})`">
        <line
          v-for="awn in [-7, -3.5, 0, 3.5, 7]"
          :key="`awn-${i}-${awn}`"
          :x1="awn * 0.4"
          :y1="-stem.earLength"
          :x2="awn * 2.2"
          :y2="-stem.earLength - 26"
          :stroke="earColour"
          stroke-width="1"
          opacity="0.75"
        />
        <ellipse
          v-for="row in grainRows"
          :key="`grain-l-${i}-${row}`"
          cx="-3.6"
          :cy="-6 - row * (stem.earLength / 6.5)"
          rx="4"
          ry="5.2"
          :fill="earColour"
          style="transition: fill 200ms"
        />
        <ellipse
          v-for="row in grainRows"
          :key="`grain-r-${i}-${row}`"
          cx="3.6"
          :cy="-10 - row * (stem.earLength / 6.5)"
          rx="4"
          ry="5.2"
          :fill="earColour"
          style="transition: fill 200ms"
        />
      </g>
    </g>

    <line
      x1="0"
      :y1="GROUND_Y"
      x2="300"
      :y2="GROUND_Y"
      stroke="#4a3a22"
      stroke-width="1.5"
      opacity="0.5"
    />
  </svg>
</template>
