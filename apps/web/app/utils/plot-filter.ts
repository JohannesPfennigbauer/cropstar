import type { LandUseCategory } from './land-use'
import { LAND_USE_CATEGORIES } from './land-use'

/** "active" is everything farmed: all categories except fallow and landscape elements/other. */
export type PlotGroup = 'active' | LandUseCategory

export interface PlotFilter {
  group: PlotGroup | null
  /** Land Use names (as AMA spells them); empty means all of the group. */
  crops: string[]
}

interface FilterablePlot { land_use_name: string, land_use_category: LandUseCategory }

const INACTIVE: LandUseCategory[] = ['fallow', 'other']

export function inGroup(category: LandUseCategory, group: PlotGroup | null): boolean {
  if (group === null) return true
  if (group === 'active') return !INACTIVE.includes(category)
  return category === group
}

export function matchesFilter(plot: FilterablePlot, filter: PlotFilter): boolean {
  return inGroup(plot.land_use_category, filter.group)
    && (filter.crops.length === 0 || filter.crops.includes(plot.land_use_name))
}

/** First row: "active" (if any Plot is active), then every category present, in legend order. */
export function groupPills(plots: FilterablePlot[]): { group: PlotGroup, count: number }[] {
  const count = (group: PlotGroup) => plots.filter(p => inGroup(p.land_use_category, group)).length
  const pills: { group: PlotGroup, count: number }[] = []
  const active = count('active')
  if (active) pills.push({ group: 'active', count: active })
  for (const category of LAND_USE_CATEGORIES) {
    const n = count(category)
    if (n) pills.push({ group: category, count: n })
  }
  return pills
}

/** Second row: the crops within the chosen group, most frequent first. */
export function cropPills(plots: FilterablePlot[], group: PlotGroup | null): { name: string, category: LandUseCategory, count: number }[] {
  const byName = new Map<string, { name: string, category: LandUseCategory, count: number }>()
  for (const plot of plots) {
    if (!inGroup(plot.land_use_category, group)) continue
    const entry = byName.get(plot.land_use_name) ?? { name: plot.land_use_name, category: plot.land_use_category, count: 0 }
    entry.count++
    byName.set(plot.land_use_name, entry)
  }
  return [...byName.values()].sort((a, b) => b.count - a.count || a.name.localeCompare(b.name, 'de-AT'))
}
