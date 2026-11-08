import { describe, expect, it } from 'vitest'
import { cropPills, groupPills, matchesFilter } from '../app/utils/plot-filter'
import type { LandUseCategory } from '../app/utils/land-use'

const plot = (land_use_name: string, land_use_category: LandUseCategory) => ({ land_use_name, land_use_category })

const plots = [
  plot('GRÜNBRACHE', 'fallow'),
  plot('GRÜNBRACHE', 'fallow'),
  plot('WINTERROGGEN', 'cereals'),
  plot('WINTERWEICHWEIZEN', 'cereals'),
  plot('WINTERROGGEN', 'cereals'),
  plot('SONNENBLUMEN', 'oilseeds'),
  plot('HECKE', 'other'),
  plot('KLEEGRAS', 'fodder'),
  plot('DAUERWEIDE', 'grassland')
]

describe('plot filter', () => {
  it('counts active Plots without fallow and landscape elements, then each category, fallow and other last', () => {
    expect(groupPills(plots)).toEqual([
      { group: 'active', count: 6 },
      { group: 'cereals', count: 3 },
      { group: 'oilseeds', count: 1 },
      { group: 'fodder', count: 1 },
      { group: 'grassland', count: 1 },
      { group: 'fallow', count: 2 },
      { group: 'other', count: 1 }
    ])
  })

  it('offers the crops of the chosen group, most frequent first', () => {
    expect(cropPills(plots, 'cereals').map(c => [c.name, c.count])).toEqual([
      ['WINTERROGGEN', 2],
      ['WINTERWEICHWEIZEN', 1]
    ])
    expect(cropPills(plots, null).map(c => c.name).slice(-2)).toEqual(['GRÜNBRACHE', 'HECKE'])
  })

  it('narrows by group and then by crops', () => {
    expect(plots.filter(p => matchesFilter(p, { group: 'active', crops: [] }))).toHaveLength(6)
    expect(plots.filter(p => matchesFilter(p, { group: 'cereals', crops: ['WINTERROGGEN'] }))).toHaveLength(2)
    expect(plots.filter(p => matchesFilter(p, { group: null, crops: [] }))).toHaveLength(9)
  })
})
