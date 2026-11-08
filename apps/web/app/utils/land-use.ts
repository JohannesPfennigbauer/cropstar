import type { Schemas } from '@cropstar/api-client'

export type LandUseCategory = Schemas['LandUseCategory']

/**
 * AMA delivers Land Use names in capitals ("WINTERROGGEN"). Shown in sentence case, which
 * reads naturally for the usual one-word names; the code stays the exact reference.
 */
export function landUseLabel(name: string): string {
  const lower = name.toLocaleLowerCase('de-AT')
  return lower.charAt(0).toLocaleUpperCase('de-AT') + lower.slice(1)
}

// One colour per category, readable on orthophoto and map alike.
const CATEGORY_COLORS: Record<LandUseCategory, string> = {
  cereals: '#d4a72c',
  legumes: '#8e6aa8',
  root_crops: '#9a6b4d',
  oilseeds: '#d9772f',
  fodder: '#3f8f7a',
  vegetables: '#4f7fa8',
  fallow: '#a9c46c',
  grassland: '#5f8a3a',
  permanent: '#b04f6c',
  other: '#8a8a80'
}

export const LAND_USE_CATEGORIES = Object.keys(CATEGORY_COLORS) as LandUseCategory[]

export function landUseColor(category: LandUseCategory): string {
  return CATEGORY_COLORS[category]
}

// Common abbreviations of crops in a rotation, by the start of the AMA name.
const ABBREVIATIONS: [string, string][] = [
  ['WINTERWEICHWEIZEN', 'WW'],
  ['WINTERWEIZEN', 'WW'],
  ['WINTERDURUM', 'WDu'],
  ['WINTERGERSTE', 'WG'],
  ['WINTERROGGEN', 'WRo'],
  ['WINTERRAPS', 'WRa'],
  ['WINTERTRITICALE', 'WT'],
  ['WINTERDINKEL', 'Di'],
  ['DINKEL', 'Di'],
  ['SOMMERGERSTE', 'SG'],
  ['SOMMERWEICHWEIZEN', 'SW'],
  ['SOMMERWEIZEN', 'SW'],
  ['SOMMERDURUM', 'SDu'],
  ['HAFER', 'Ha'],
  ['KÖRNERMAIS', 'KM'],
  ['SILOMAIS', 'SM'],
  ['ZUCKERRÜBE', 'ZR'],
  ['SPEISEKARTOFFEL', 'Ka'],
  ['KARTOFFEL', 'Ka'],
  ['SONNENBLUME', 'SB'],
  ['SOJA', 'Soja'],
  ['KÖRNERERBSE', 'Erb'],
  ['ACKERBOHNE', 'AB'],
  ['KLEEGRAS', 'KG'],
  ['LUZERNE', 'Lu'],
  ['GRÜNBRACHE', 'GB'],
  ['ÖLKÜRBIS', 'ÖK']
]

/** A short label for a Land Use in a crop rotation, e.g. "WW" for Winterweichweizen. */
export function landUseAbbreviation(name: string): string {
  const upper = name.toLocaleUpperCase('de-AT').trim()
  const known = ABBREVIATIONS.find(([prefix]) => upper.startsWith(prefix))
  if (known) return known[1]
  const word = upper.split(/[\s(-]/)[0] ?? upper
  // Winter and summer forms: W/S and the first letter of the crop.
  const season = /^(WINTER|SOMMER)(.+)$/.exec(word)
  if (season) return `${season[1]![0]}${season[2]![0]}`
  return landUseLabel(word).slice(0, 3)
}

/** Charcoal or white, whichever reads better on a category colour. */
export function textOnColor(hex: string): string {
  const [r, g, b] = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
  const luminance = 0.2126 * r! + 0.7152 * g! + 0.0722 * b!
  return luminance > 0.5 ? 'var(--color-charcoal)' : '#ffffff'
}
