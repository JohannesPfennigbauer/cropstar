/**
 * The landing-page teaching toy reads from this hard-coded response surface.
 * It is not a model, it is a table with an interpolator. Every consumer must render the
 * "illustrative, not a simulation" provenance next to the numbers.
 *
 * Calibrated loosely on organically managed winter wheat on a silt loam in the Pannonian
 * lowland: nitrogen arrives as rotted cattle manure, not as mineral fertiliser.
 */

export type DriverId = 'water' | 'nitrogen'

export interface Driver {
  id: DriverId
  /** Share of the explained spread, 0..1. Shares of one estimate sum to 1. */
  share: number
  direction: 'raises' | 'lowers'
  /** Absolute difference against the low end of that driver's range. */
  magnitude: number
}

export interface Estimate {
  value: number
  low: number
  high: number
  precision: number
  drivers: Driver[]
}

export interface Outcome {
  grainYield: Estimate
  grainProtein: Estimate
  groundCover: Estimate
  plantHeight: Estimate
  /** Days with plant-available water below 40 % of total available water. */
  waterStressDays: number
  /** Days on which crop N demand exceeded supply. */
  nDeficitDays: number
  /** N released from the manure within this season, kg N/ha. */
  availableN: number
  /** Total N applied with the manure, kg N/ha. */
  totalN: number
  /** N leaving the field in the grain, kg N/ha. */
  nExportedInGrain: number
  /** Total N applied minus N exported in grain. Negative means the soil stock paid. */
  nRemaining: number
  /** True once total manure N passes the ceiling in the nitrate action programme. */
  exceedsManureCeiling: boolean
  /** 0..1 indices the drawing reads; not displayed as numbers. */
  canopyIndex: number
  waterIndex: number
  nitrogenIndex: number
  rootDepthCm: number
}

export const PROVENANCE_REVISION = 'toy-2026-09'

export const RAINFALL_INPUT = { min: 150, max: 750, step: 10 } as const
export const MANURE_INPUT = { min: 0, max: 50, step: 1 } as const

/** Rotted cattle manure, fresh matter. */
export const MANURE_TOTAL_N_PER_TONNE = 5.0
export const MANURE_FIRST_YEAR_AVAILABILITY = 0.32
/** kg N/ha from livestock manure, the ceiling in the Austrian nitrate action programme. */
export const MANURE_N_CEILING = 170

const RAINFALL_NODES = [150, 300, 450, 600, 750]
/** Plant-available N in the season, kg N/ha. */
const NITROGEN_NODES = [0, 20, 40, 60, 80]

// Rows: precipitation nodes. Columns: available-N nodes.
const YIELD_GRID = [
  [0.9, 1.2, 1.4, 1.5, 1.6],
  [1.7, 2.3, 2.7, 3.0, 3.1],
  [2.3, 3.2, 3.9, 4.4, 4.6],
  [2.6, 3.6, 4.4, 5.0, 5.3],
  [2.6, 3.6, 4.4, 4.9, 5.1]
]

const PROTEIN_GRID = [
  [9.6, 10.8, 11.8, 12.5, 13.0],
  [9.0, 10.1, 11.0, 11.7, 12.2],
  [8.6, 9.6, 10.4, 11.1, 11.6],
  [8.3, 9.2, 10.0, 10.6, 11.1],
  [8.2, 9.0, 9.8, 10.4, 10.9]
]

const COVER_GRID = [
  [0.20, 0.27, 0.32, 0.35, 0.36],
  [0.35, 0.48, 0.57, 0.63, 0.66],
  [0.43, 0.61, 0.73, 0.81, 0.85],
  [0.47, 0.66, 0.79, 0.87, 0.91],
  [0.48, 0.67, 0.80, 0.88, 0.92]
]

const HEIGHT_GRID = [
  [40, 47, 52, 55, 57],
  [55, 64, 70, 74, 77],
  [64, 75, 83, 88, 91],
  [68, 80, 88, 94, 97],
  [69, 81, 89, 95, 98]
]

// More nitrogen builds more canopy, which transpires more and runs out of water sooner.
const WATER_STRESS_GRID = [
  [50, 55, 59, 62, 64],
  [28, 33, 38, 42, 45],
  [13, 17, 21, 25, 28],
  [5, 7, 10, 13, 16],
  [2, 3, 5, 7, 9]
]

const N_DEFICIT_GRID = [
  [40, 24, 13, 6, 3],
  [55, 36, 21, 11, 5],
  [64, 45, 29, 17, 9],
  [69, 50, 34, 21, 12],
  [71, 52, 36, 23, 13]
]

/** Nitrogen-to-protein conversion factor for cereal grain. */
const PROTEIN_TO_N = 5.7

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value))
}

export function availableNitrogenFrom(manureTonnes: number): number {
  return manureTonnes * MANURE_TOTAL_N_PER_TONNE * MANURE_FIRST_YEAR_AVAILABILITY
}

export function totalNitrogenFrom(manureTonnes: number): number {
  return manureTonnes * MANURE_TOTAL_N_PER_TONNE
}

function axisPosition(nodes: number[], value: number): { index: number, weight: number } {
  const first = nodes[0] ?? 0
  const last = nodes[nodes.length - 1] ?? 0
  const bounded = clamp(value, first, last)

  for (let i = 0; i < nodes.length - 1; i++) {
    const lower = nodes[i] ?? 0
    const upper = nodes[i + 1] ?? 0
    if (bounded <= upper) {
      const span = upper - lower
      return { index: i, weight: span === 0 ? 0 : (bounded - lower) / span }
    }
  }

  return { index: nodes.length - 2, weight: 1 }
}

function interpolate(grid: number[][], rainfall: number, nitrogen: number): number {
  const r = axisPosition(RAINFALL_NODES, rainfall)
  const n = axisPosition(NITROGEN_NODES, nitrogen)

  const rowLow = grid[r.index] ?? []
  const rowHigh = grid[r.index + 1] ?? rowLow

  const lowLeft = rowLow[n.index] ?? 0
  const lowRight = rowLow[n.index + 1] ?? lowLeft
  const highLeft = rowHigh[n.index] ?? lowLeft
  const highRight = rowHigh[n.index + 1] ?? highLeft

  const low = lowLeft + (lowRight - lowLeft) * n.weight
  const high = highLeft + (highRight - highLeft) * n.weight

  return low + (high - low) * r.weight
}

/**
 * How far the inputs sit from the middle of the table, 0..1. The table is coarsest at its
 * corners, so the band widens there.
 */
function extremity(rainfall: number, nitrogen: number): number {
  const nMax = NITROGEN_NODES[NITROGEN_NODES.length - 1] ?? 1
  const r = (rainfall - RAINFALL_INPUT.min) / (RAINFALL_INPUT.max - RAINFALL_INPUT.min)
  const n = clamp(nitrogen / nMax, 0, 1)
  return clamp(Math.max(Math.abs(r - 0.5), Math.abs(n - 0.5)) * 2, 0, 1)
}

function driversFor(grid: number[][], rainfall: number, nitrogen: number): Driver[] {
  const value = interpolate(grid, rainfall, nitrogen)
  const rainEffect = value - interpolate(grid, RAINFALL_INPUT.min, nitrogen)
  const nEffect = value - interpolate(grid, rainfall, 0)
  const total = Math.abs(rainEffect) + Math.abs(nEffect)

  return [
    {
      id: 'water',
      share: total === 0 ? 0.5 : Math.abs(rainEffect) / total,
      direction: rainEffect >= 0 ? 'raises' : 'lowers',
      magnitude: Math.abs(rainEffect)
    },
    {
      id: 'nitrogen',
      share: total === 0 ? 0.5 : Math.abs(nEffect) / total,
      direction: nEffect >= 0 ? 'raises' : 'lowers',
      magnitude: Math.abs(nEffect)
    }
  ]
}

function estimate(
  grid: number[][],
  rainfall: number,
  nitrogen: number,
  options: { precision: number, baseSpread: number }
): Estimate {
  const value = interpolate(grid, rainfall, nitrogen)
  const spread = options.baseSpread * (1 + 0.8 * extremity(rainfall, nitrogen) ** 2)

  return {
    value,
    low: Math.max(0, value * (1 - spread)),
    high: value * (1 + spread),
    precision: options.precision,
    drivers: driversFor(grid, rainfall, nitrogen)
  }
}

export function illustrativeOutcome(rainfallMm: number, manureTonnes: number): Outcome {
  const rain = clamp(rainfallMm, RAINFALL_INPUT.min, RAINFALL_INPUT.max)
  const manure = clamp(manureTonnes, MANURE_INPUT.min, MANURE_INPUT.max)

  const availableN = availableNitrogenFrom(manure)
  const totalN = totalNitrogenFrom(manure)

  const grainYield = estimate(YIELD_GRID, rain, availableN, { precision: 1, baseSpread: 0.13 })
  const grainProtein = estimate(PROTEIN_GRID, rain, availableN, { precision: 1, baseSpread: 0.06 })
  const groundCover = estimate(COVER_GRID, rain, availableN, { precision: 2, baseSpread: 0.08 })
  const plantHeight = estimate(HEIGHT_GRID, rain, availableN, { precision: 0, baseSpread: 0.09 })

  const waterStressDays = Math.round(interpolate(WATER_STRESS_GRID, rain, availableN))
  const nDeficitDays = Math.round(interpolate(N_DEFICIT_GRID, rain, availableN))

  const nExportedInGrain
    = (grainYield.value * 1000 * (grainProtein.value / 100)) / PROTEIN_TO_N

  const waterIndex = 1 - clamp(waterStressDays / 70, 0, 1)
  const nitrogenIndex = 1 - clamp(nDeficitDays / 70, 0, 1)
  const canopyIndex = clamp(groundCover.value / 0.92, 0, 1)
  const heightIndex = clamp(plantHeight.value / 98, 0, 1)

  return {
    grainYield,
    grainProtein,
    groundCover,
    plantHeight,
    waterStressDays,
    nDeficitDays,
    availableN,
    totalN,
    nExportedInGrain,
    nRemaining: totalN - nExportedInGrain,
    exceedsManureCeiling: totalN > MANURE_N_CEILING,
    canopyIndex,
    waterIndex,
    nitrogenIndex,
    // Drought drives roots deeper, but a small plant cannot fund a deep root system.
    rootDepthCm: (55 + waterStressDays * 0.9) * (0.65 + 0.35 * heightIndex)
  }
}
