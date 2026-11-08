import type { Schemas } from '@cropstar/api-client'

export type ActivityPriority = Schemas['Priority']

/**
 * One line of a Plot's Activities: an Open Task or a Done Operation from the Operation Log.
 * `date` is the due date of a Task or the day an Operation was performed; null for undated Tasks.
 */
export interface Activity {
  key: string
  done: boolean
  date: string | null
  title: string
  detail: string
  operationType: string | null
  priority: ActivityPriority
  task?: Schemas['TaskOut']
  applied?: Schemas['AppliedInput'] | null
}

const PRIORITY_RANK: Record<ActivityPriority, number> = { high: 0, normal: 1, low: 2, none: 3 }

const byPriority = (a: Activity, b: Activity) => PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority]

/** Oldest first, then undated Tasks by priority: the order along the spiral. */
export function chronological(activities: Activity[]): Activity[] {
  const dated = activities.filter(a => a.date).sort((a, b) => a.date!.localeCompare(b.date!) || Number(b.done) - Number(a.done))
  return [...dated, ...activities.filter(a => !a.date).sort(byPriority)]
}

/** Undated Tasks by priority on top, then newest first: the order of the table. */
export function newestFirst(activities: Activity[]): Activity[] {
  const dated = activities.filter(a => a.date).sort((a, b) => b.date!.localeCompare(a.date!) || Number(a.done) - Number(b.done))
  return [...activities.filter(a => !a.date).sort(byPriority), ...dated]
}

// ---------------------------------------------------------------------------------------------
// Ground cover, derived from Operations: green from sowing, darkening and ripening to yellow
// towards the harvest; stubble yellow after the harvest; brown from tillage until the next sowing.
// It describes what the Operations imply. It is not a measurement.
// ---------------------------------------------------------------------------------------------

export type CoverPhase = 'unknown' | 'crop' | 'catchCrop' | 'stubble' | 'soil'

export interface CoverEvent { title: string, date: string }

export interface Cover {
  phase: CoverPhase
  /** rgb() colour of the band at that day. */
  color: string
  /** The Activity the phase starts with; null before the first one. */
  since: CoverEvent | null
  /** The harvest a crop ripens towards, and how far along it is (0–1). */
  harvest?: CoverEvent
  progress?: number
}

type Rgb = readonly [number, number, number]
const LIGHT: Rgb = [181, 214, 143]
const DARK: Rgb = [79, 122, 58]
const RIPE: Rgb = [226, 194, 90]
const SOIL: Rgb = [166, 124, 91]
// Before the first recorded Activity the cover is unknown: a neutral grey, not a guess.
const UNKNOWN: Rgb = [196, 192, 180]
// A crop is darkest at this share of the time between sowing and harvest, then ripens.
const DARKEST_AT = 0.65
// A sowing without a following harvest or tillage (e.g. a catch crop) greens over this many days.
const GREENING_DAYS = 120

const DAY = 86_400_000
export const isoToDay = (iso: string) => Date.parse(`${iso}T00:00:00Z`) / DAY
export const dayToIso = (day: number) => new Date(Math.round(day) * DAY).toISOString().slice(0, 10)

function mix(from: Rgb, to: Rgb, u: number): string {
  const t = Math.max(0, Math.min(1, u))
  return `rgb(${from.map((c, k) => Math.round(c + (to[k]! - c) * t)).join(' ')})`
}

/** The colour lightened towards the paper background, for card and row backgrounds. */
export function tint(color: string, percent = 50): string {
  return `color-mix(in srgb, ${color} ${percent}%, var(--color-paper))`
}

/** Builds a lookup from day to ground cover for one Plot's Activities. */
export function coverTimeline(activities: Activity[]): (day: number) => Cover {
  const events = activities
    .filter(a => a.date && (a.operationType === 'sowing' || a.operationType === 'harvest' || a.operationType === 'tillage'))
    .sort((a, b) => a.date!.localeCompare(b.date!))
    .map(a => ({ day: isoToDay(a.date!), type: a.operationType!, event: { title: a.title, date: a.date! } }))
    // A sowing into a standing crop (undersowing) does not start a new crop.
    .filter((e, i, all) => !(e.type === 'sowing' && all[i - 1]?.type === 'sowing'))

  return (day: number): Cover => {
    const last = [...events].reverse().find(e => e.day <= day)
    if (!last) return { phase: 'unknown', color: mix(UNKNOWN, UNKNOWN, 0), since: null }
    if (last.type === 'harvest') return { phase: 'stubble', color: mix(RIPE, RIPE, 0), since: last.event }
    if (last.type === 'tillage') return { phase: 'soil', color: mix(SOIL, SOIL, 0), since: last.event }
    const later = events.filter(e => e.day > last.day)
    const harvest = later.find(e => e.type === 'harvest')
    const tillage = later.find(e => e.type === 'tillage')
    if (harvest && (!tillage || harvest.day <= tillage.day)) {
      const u = (day - last.day) / (harvest.day - last.day)
      const color = u < DARKEST_AT ? mix(LIGHT, DARK, u / DARKEST_AT) : mix(DARK, RIPE, (u - DARKEST_AT) / (1 - DARKEST_AT))
      return { phase: 'crop', color, since: last.event, harvest: harvest.event, progress: u }
    }
    const end = tillage ? tillage.day : last.day + GREENING_DAYS
    return { phase: 'catchCrop', color: mix(LIGHT, DARK, (day - last.day) / (end - last.day)), since: last.event }
  }
}

/** Background of undated Tasks: soil tint by priority. */
export function priorityBackground(priority: ActivityPriority): string {
  const soil = { high: 34, normal: 18, low: 8, none: 0 }[priority]
  return `color-mix(in srgb, var(--color-soil) ${soil}%, var(--color-paper))`
}

// ---------------------------------------------------------------------------------------------
// Timeline layout: every Activity gets at least one card slot; a pause adds a logarithmic,
// capped extra. In between, time runs piecewise linearly: stretched where much happens,
// compressed in long pauses. A sense of time, not a day-accurate scale.
// ---------------------------------------------------------------------------------------------

const GAP_MIN = 0.85
const GAP_SCALE = 0.4
const GAP_DAYS = 30
const GAP_MAX_EXTRA = 0.7
// Before the first and after the last dated Activity, time runs on at this rate.
const DAYS_PER_SLOT_OUTSIDE = 45

/** Distance in card slots between two Activities that are `days` apart. */
export function gapFor(days: number): number {
  return GAP_MIN + Math.min(GAP_MAX_EXTRA, GAP_SCALE * Math.log2(1 + Math.max(0, days) / GAP_DAYS))
}

export interface TimelineLayout {
  /** Slot of every Activity, keyed by Activity key. */
  slotOf: Map<string, number>
  firstSlot: number
  lastSlot: number
  /** Beyond this slot the band ends and the undated Tasks follow. */
  bandEndSlot: number
  dayAtSlot: (slot: number) => number
  slotAtDay: (day: number) => number
}

/** Lays out Activities in chronological order (see `chronological`) along the timeline. */
export function layoutTimeline(ordered: Activity[]): TimelineLayout {
  const dated = ordered.filter(a => a.date)
  const undated = ordered.filter(a => !a.date)
  const days = dated.map(a => isoToDay(a.date!))
  const slots: number[] = []
  days.forEach((day, i) => slots.push(i === 0 ? 0 : slots[i - 1]! + gapFor(day - days[i - 1]!)))
  const lastDated = slots.length ? slots[slots.length - 1]! : -1
  const undatedSlots = undated.map((_, j) => lastDated + 1.1 + j * GAP_MIN)

  const slotOf = new Map<string, number>()
  dated.forEach((a, i) => slotOf.set(a.key, slots[i]!))
  undated.forEach((a, j) => slotOf.set(a.key, undatedSlots[j]!))

  function dayAtSlot(slot: number): number {
    if (!days.length) return NaN
    if (slot <= 0) return days[0]! + slot * DAYS_PER_SLOT_OUTSIDE
    if (slot >= lastDated) return days[days.length - 1]! + (slot - lastDated) * DAYS_PER_SLOT_OUTSIDE
    const i = slots.findIndex(s => s > slot) - 1
    const span = slots[i + 1]! - slots[i]!
    return days[i]! + ((slot - slots[i]!) / span) * (days[i + 1]! - days[i]!)
  }

  function slotAtDay(day: number): number {
    if (!days.length) return NaN
    if (day <= days[0]!) return (day - days[0]!) / DAYS_PER_SLOT_OUTSIDE
    if (day >= days[days.length - 1]!) return lastDated + (day - days[days.length - 1]!) / DAYS_PER_SLOT_OUTSIDE
    const i = days.findIndex(d => d > day) - 1
    const span = days[i + 1]! - days[i]!
    return slots[i]! + (span ? (day - days[i]!) / span : 0) * (slots[i + 1]! - slots[i]!)
  }

  const allSlots = [...slotOf.values()]
  return {
    slotOf,
    firstSlot: allSlots.length ? Math.min(...allSlots) : 0,
    lastSlot: allSlots.length ? Math.max(...allSlots) : 0,
    bandEndSlot: days.length ? lastDated + 0.6 : -Infinity,
    dayAtSlot,
    slotAtDay
  }
}

const OPERATION_ICONS: Record<string, string> = {
  tillage: 'i-lucide-tractor',
  mechanical_weed_control: 'i-lucide-shovel',
  mulching: 'i-lucide-scissors',
  sowing: 'i-lucide-sprout',
  fertilisation: 'i-lucide-droplets',
  harvest: 'i-lucide-wheat'
}

/** Icon of an Operation Type; a Task without one shows an eye (observation, check, errand). */
export function operationIcon(operationType: string | null): string {
  return (operationType && OPERATION_ICONS[operationType]) || 'i-lucide-eye'
}

/** Priority as a symbol: ⇈ high, ↑ normal, ↓ low, nothing for none. */
export function priorityIcon(priority: ActivityPriority): string | null {
  return { high: 'i-lucide-chevrons-up', normal: 'i-lucide-chevron-up', low: 'i-lucide-chevron-down', none: null }[priority]
}
