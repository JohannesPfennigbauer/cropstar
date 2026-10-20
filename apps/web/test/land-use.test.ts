import { describe, expect, it } from 'vitest'
import { LAND_USE_CATEGORIES, landUseColor, landUseLabel } from '../app/utils/land-use'

describe('landUseLabel', () => {
  it('turns AMA capitals into sentence case, keeping umlauts', () => {
    expect(landUseLabel('WINTERROGGEN')).toBe('Winterroggen')
    expect(landUseLabel('GRÜNBRACHE')).toBe('Grünbrache')
    expect(landUseLabel('ÖLKÜRBISSE')).toBe('Ölkürbisse')
  })
})

describe('landUseColor', () => {
  it('gives every category its own colour', () => {
    const colours = LAND_USE_CATEGORIES.map(landUseColor)
    expect(new Set(colours).size).toBe(LAND_USE_CATEGORIES.length)
    for (const colour of colours) expect(colour).toMatch(/^#[0-9a-f]{6}$/)
  })
})
