import { describe, expect, it } from 'vitest'
import { cleanDetails, detailsProblem, emptyDetails } from '../app/utils/operation-details'

describe('cleanDetails', () => {
  it('keeps only what was filled in', () => {
    expect(cleanDetails({ type: 'fertilisation', amount: 20, unit: 'm3_per_ha', note: '  Gülle ' }))
      .toEqual({ type: 'fertilisation', amount: 20, unit: 'm3_per_ha', note: 'Gülle' })
    expect(cleanDetails({ type: 'tillage', implement: null, depth_cm: Number.NaN, note: '' }))
      .toBeNull()
  })

  it('treats empty details as none', () => {
    expect(cleanDetails(emptyDetails('harvest'))).toBeNull()
    expect(cleanDetails(null)).toBeNull()
  })
})

describe('detailsProblem', () => {
  it('accepts plausible values', () => {
    expect(detailsProblem({ type: 'harvest', yield_t_per_ha: 6.2, crude_protein_percent: 12 })).toBeNull()
  })

  it('names the first implausible value', () => {
    expect(detailsProblem({ type: 'tillage', depth_cm: -3 })).toBe('negative')
    expect(detailsProblem({ type: 'tillage', depth_cm: 120 })).toBe('tooLarge')
    expect(detailsProblem({ type: 'harvest', moisture_percent: 101 })).toBe('percent')
    expect(detailsProblem({ type: 'sowing', rate: 80 })).toBe('unitMissing')
  })
})
