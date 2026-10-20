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
