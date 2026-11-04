import type { Schemas } from '@cropstar/api-client'

/** Planned or Actual Details: one shape per Operation Type, told apart by `type`. */
export type OperationDetails
  = | Schemas['TillageDetails']
    | Schemas['MechanicalWeedControlDetails']
    | Schemas['MulchingDetails']
    | Schemas['SowingDetails']
    | Schemas['FertilisationDetails']
    | Schemas['HarvestDetails']
export type OperationTypeCode = OperationDetails['type']

export interface ChoiceField { key: string, kind: 'choice', options: readonly string[], group: string }
interface NumberField { key: string, kind: 'number', max?: number, step: number, unitKey?: string }
export type DetailField = ChoiceField | NumberField

// The structured fields of each Operation Type, in form order. A number with `unitKey`
// is shown together with that choice. Values mirror the API's enums.
export const DETAIL_FIELDS: Record<OperationTypeCode, DetailField[]> = {
  tillage: [
    { key: 'implement', kind: 'choice', group: 'tillageImplement', options: ['plough', 'cultivator', 'disc_harrow', 'subsoiler', 'seedbed_combination', 'power_harrow', 'roller', 'other'] },
    { key: 'depth_cm', kind: 'number', max: 100, step: 1 }
  ],
  mechanical_weed_control: [
    { key: 'implement', kind: 'choice', group: 'weedControlImplement', options: ['tine_weeder', 'hoe', 'finger_weeder', 'rotary_hoe', 'other'] }
  ],
  mulching: [
    { key: 'material', kind: 'choice', group: 'mulchedMaterial', options: ['cover_crop', 'crop_residues', 'grassland', 'other'] }
  ],
  sowing: [
    { key: 'purpose', kind: 'choice', group: 'sowingPurpose', options: ['main_crop', 'cover_crop', 'undersown_crop'] },
    { key: 'rate', kind: 'number', step: 0.1, unitKey: 'unit' },
    { key: 'unit', kind: 'choice', group: 'sowingUnit', options: ['kg_per_ha', 'seeds_per_m2', 'seeds_per_ha'] }
  ],
  fertilisation: [
    { key: 'amount', kind: 'number', step: 0.1, unitKey: 'unit' },
    { key: 'unit', kind: 'choice', group: 'fertilisationUnit', options: ['kg_per_ha', 't_per_ha', 'm3_per_ha', 'l_per_ha'] }
  ],
  harvest: [
    { key: 'product', kind: 'choice', group: 'harvestedProduct', options: ['grain', 'straw', 'whole_crop', 'forage', 'other'] },
    { key: 'yield_t_per_ha', kind: 'number', step: 0.01 },
    { key: 'moisture_percent', kind: 'number', max: 100, step: 0.1 },
    { key: 'crude_protein_percent', kind: 'number', max: 100, step: 0.1 }
  ]
}

export function emptyDetails(type: OperationTypeCode): OperationDetails {
  return { type } as OperationDetails
}

type Values = Record<string, unknown>

/** What to send: only what was filled in, and null when nothing was. */
export function cleanDetails(details: OperationDetails | null | undefined): OperationDetails | null {
  if (!details) return null
  const kept: Values = {}
  for (const [key, value] of Object.entries(details)) {
    if (value === null || value === undefined) continue
    if (typeof value === 'string' && value.trim() === '') continue
    if (typeof value === 'number' && Number.isNaN(value)) continue
    kept[key] = typeof value === 'string' ? value.trim() : value
  }
  return Object.keys(kept).length > 1 ? kept as OperationDetails : null
}

/** The first implausible value, as a translation key under `app.details.errors`; null if fine. */
export function detailsProblem(details: OperationDetails | null | undefined): string | null {
  if (!details) return null
  const values = details as Values
  for (const field of DETAIL_FIELDS[details.type] ?? []) {
    if (field.kind !== 'number') continue
    const value = values[field.key]
    if (typeof value !== 'number' || Number.isNaN(value)) continue
    if (value < 0) return 'negative'
    if (field.max !== undefined && value > field.max) return field.max === 100 && field.key.endsWith('percent') ? 'percent' : 'tooLarge'
    if (field.unitKey && !values[field.unitKey]) return 'unitMissing'
  }
  return null
}
