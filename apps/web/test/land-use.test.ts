import { describe, expect, it } from 'vitest'
import { LAND_USE_CATEGORIES, landUseAbbreviation, landUseColor, landUseLabel, textOnColor } from '../app/utils/land-use'

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

describe('landUseAbbreviation', () => {
  it('uses the common abbreviations of a crop rotation', () => {
    expect(landUseAbbreviation('WINTERWEICHWEIZEN')).toBe('WW')
    expect(landUseAbbreviation('WINTERROGGEN')).toBe('WRo')
    expect(landUseAbbreviation('SONNENBLUMEN')).toBe('SB')
    expect(landUseAbbreviation('KÖRNERMAIS')).toBe('KM')
  })

  it('derives one for other crops', () => {
    expect(landUseAbbreviation('WINTERMOHN')).toBe('WM')
    expect(landUseAbbreviation('MAIS CORN-COB-MIX (CCM)')).toBe('Mai')
  })
})

describe('textOnColor', () => {
  it('picks dark text on light colours and white on dark ones', () => {
    expect(textOnColor('#d4a72c')).toBe('var(--color-charcoal)')
    expect(textOnColor('#5f8a3a')).toBe('#ffffff')
  })
})
