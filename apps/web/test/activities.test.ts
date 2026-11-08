import { describe, expect, it } from 'vitest'
import {
  type Activity,
  chronological,
  coverTimeline,
  gapFor,
  isoToDay,
  layoutTimeline,
  newestFirst,
  operationIcon,
  priorityIcon
} from '../app/utils/activities'

function activity(key: string, date: string | null, operationType: string | null = null, extra: Partial<Activity> = {}): Activity {
  return { key, done: date !== null && date < '2026-11-08', date, title: key, detail: '', operationType, priority: 'none', ...extra }
}

const season: Activity[] = [
  activity('harvest-spelt', '2026-07-18', 'harvest'),
  activity('stubble', '2026-07-24', 'tillage'),
  activity('catch-crop', '2026-08-05', 'sowing'),
  activity('cultivate', '2026-10-14', 'tillage'),
  activity('wheat', '2026-10-21', 'sowing'),
  activity('undersow', '2027-05-05', 'sowing'),
  activity('harvest-wheat', '2027-07-20', 'harvest')
]

describe('activity order', () => {
  const mixed = [
    activity('later', '2027-03-10'),
    activity('low', null, null, { priority: 'low' }),
    activity('earlier', '2026-09-01'),
    activity('high', null, null, { priority: 'high' })
  ]

  it('runs oldest first along the spiral, undated Tasks last by priority', () => {
    expect(chronological(mixed).map(a => a.key)).toEqual(['earlier', 'later', 'high', 'low'])
  })

  it('puts undated Tasks on top of the table, then newest first', () => {
    expect(newestFirst(mixed).map(a => a.key)).toEqual(['high', 'low', 'later', 'earlier'])
  })
})

describe('ground cover', () => {
  const coverAt = coverTimeline(season)
  const at = (iso: string) => coverAt(isoToDay(iso))

  it('is unknown before the first recorded Activity', () => {
    expect(at('2026-06-01')).toMatchObject({ phase: 'unknown', since: null })
  })

  it('is stubble after a harvest and bare soil after tillage', () => {
    expect(at('2026-07-20')).toMatchObject({ phase: 'stubble', since: { title: 'harvest-spelt' } })
    expect(at('2026-08-01')).toMatchObject({ phase: 'soil', since: { title: 'stubble' } })
  })

  it('greens a sowing without harvest until the next tillage', () => {
    expect(at('2026-09-01')).toMatchObject({ phase: 'catchCrop', since: { title: 'catch-crop' } })
    expect(at('2026-10-18').phase).toBe('soil')
  })

  it('ripens a crop towards its harvest, ignoring an undersowing', () => {
    const spring = at('2027-05-10')
    expect(spring).toMatchObject({ phase: 'crop', since: { title: 'wheat' }, harvest: { title: 'harvest-wheat' } })
    expect(spring.progress).toBeGreaterThan(0.7)
    expect(at('2026-10-21').color).toBe('rgb(181 214 143)')
    expect(at('2027-07-19').color).not.toBe(at('2027-03-01').color)
  })
})

describe('timeline layout', () => {
  it('keeps a minimum distance and compresses long pauses', () => {
    expect(gapFor(0)).toBeCloseTo(0.85)
    expect(gapFor(30)).toBeGreaterThan(gapFor(6))
    expect(gapFor(110)).toBeCloseTo(gapFor(400))
    expect(gapFor(400)).toBeCloseTo(1.55)
  })

  it('maps days and slots onto each other, monotonically', () => {
    const ordered = chronological([...season, activity('soil-sample', null, null, { priority: 'high' })])
    const layout = layoutTimeline(ordered)
    const slots = ordered.map(a => layout.slotOf.get(a.key)!)
    expect(slots).toEqual([...slots].sort((a, b) => a - b))
    expect(layout.slotOf.get('soil-sample')).toBe(layout.lastSlot)
    expect(layout.bandEndSlot).toBeLessThan(layout.lastSlot)
    for (const iso of ['2026-06-01', '2026-09-20', '2027-01-15', '2027-09-01']) {
      expect(layout.dayAtSlot(layout.slotAtDay(isoToDay(iso)))).toBeCloseTo(isoToDay(iso))
    }
  })

  it('has no band without dated Activities', () => {
    const layout = layoutTimeline([activity('only', null)])
    expect(layout.bandEndSlot).toBe(-Infinity)
    expect(layout.slotOf.get('only')).toBe(layout.lastSlot)
  })
})

describe('symbols', () => {
  it('show the Operation Type, or an eye for Tasks without one', () => {
    expect(operationIcon('sowing')).toBe('i-lucide-sprout')
    expect(operationIcon(null)).toBe('i-lucide-eye')
  })

  it('show priority without a symbol for none', () => {
    expect(priorityIcon('high')).toBe('i-lucide-chevrons-up')
    expect(priorityIcon('none')).toBeNull()
  })
})
