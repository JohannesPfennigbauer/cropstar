import { describe, expect, it } from 'vitest'
import { cropPills, groupPills, matchesFilter } from '../app/utils/plot-filter'
import type { LandUseCategory } from '../app/utils/land-use'

const plot = (land_use_name: string, land_use_category: LandUseCategory) => ({ land_use_name, land_use_category })

const plots = [
  plot('WINTERROGGEN', 'cereals'),
  plot('WINTERWEICHWEIZEN', 'cereals'),
  plot('WINTERROGGEN', 'cereals'),
  plot('SONNENBLUMEN', 'oilseeds'),
  plot('GRÜNBRACHE', 'fallow'),
  plot('HECKE', 'other')
]

describe('plot filter', () => {
  it('counts active Plots without fallow and landscape elements, then each category present', () => {
    expect(groupPills(plots)).toEqual([
      { group: 'active', count: 4 },
      { group: 'cereals', count: 3 },
      { group: 'oilseeds', count: 1 },
      { group: 'fallow', count: 1 },
      { group: 'other', count: 1 }
    ])
  })

  it('offers the crops of the chosen group, most frequent first', () => {
    expect(cropPills(plots, 'cereals').map(c => [c.name, c.count])).toEqual([
      ['WINTERROGGEN', 2],
      ['WINTERWEICHWEIZEN', 1]
    ])
    expect(cropPills(plots, null)).toHaveLength(5)
  })

  it('narrows by group and then by crops', () => {
    expect(plots.filter(p => matchesFilter(p, { group: 'active', crops: [] }))).toHaveLength(4)
    expect(plots.filter(p => matchesFilter(p, { group: 'cereals', crops: ['WINTERROGGEN'] }))).toHaveLength(2)
    expect(plots.filter(p => matchesFilter(p, { group: null, crops: [] }))).toHaveLength(6)
  })
})
