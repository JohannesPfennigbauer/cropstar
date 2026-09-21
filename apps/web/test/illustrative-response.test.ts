import { describe, expect, it } from 'vitest'
import {
  MANURE_INPUT,
  MANURE_N_CEILING,
  RAINFALL_INPUT,
  availableNitrogenFrom,
  illustrativeOutcome,
  totalNitrogenFrom
} from '../app/utils/illustrative-response'

/** Manure rate in t/ha that lands exactly on a nitrogen node of the table. */
function tonnesForAvailableN(kgN: number): number {
  return kgN / 1.6
}

describe('manure to nitrogen conversion', () => {
  it('releases about a third of the total nitrogen in the first season', () => {
    expect(totalNitrogenFrom(30)).toBeCloseTo(150, 6)
    expect(availableNitrogenFrom(30)).toBeCloseTo(48, 6)
  })

  it('crosses the livestock-manure ceiling at 34 t/ha', () => {
    expect(illustrativeOutcome(450, 34).exceedsManureCeiling).toBe(false)
    expect(illustrativeOutcome(450, 35).exceedsManureCeiling).toBe(true)
    expect(totalNitrogenFrom(34)).toBeCloseTo(MANURE_N_CEILING, 6)
  })
})

describe('illustrativeOutcome', () => {
  it('reproduces the table exactly at its nodes', () => {
    expect(illustrativeOutcome(450, tonnesForAvailableN(40)).grainYield.value)
      .toBeCloseTo(3.9, 6)
    expect(illustrativeOutcome(150, 0).grainYield.value).toBeCloseTo(0.9, 6)
    expect(illustrativeOutcome(750, tonnesForAvailableN(80)).grainProtein.value)
      .toBeCloseTo(10.9, 6)
  })

  it('interpolates between nodes', () => {
    const middle = illustrativeOutcome(525, tonnesForAvailableN(40)).grainYield.value
    expect(middle).toBeGreaterThan(3.9)
    expect(middle).toBeLessThan(4.4)
  })

  it('clamps inputs to the table range instead of extrapolating', () => {
    expect(illustrativeOutcome(-100, 20).grainYield.value)
      .toBeCloseTo(illustrativeOutcome(RAINFALL_INPUT.min, 20).grainYield.value, 6)
    expect(illustrativeOutcome(450, 9999).grainYield.value)
      .toBeCloseTo(illustrativeOutcome(450, MANURE_INPUT.max).grainYield.value, 6)
  })

  it('never yields more with less manure at a fixed water supply', () => {
    let previous = 0
    for (let t = MANURE_INPUT.min; t <= MANURE_INPUT.max; t += MANURE_INPUT.step) {
      const current = illustrativeOutcome(450, t).grainYield.value
      expect(current).toBeGreaterThanOrEqual(previous - 1e-9)
      previous = current
    }
  })

  it('always brackets the value with a non-negative band', () => {
    for (let r = RAINFALL_INPUT.min; r <= RAINFALL_INPUT.max; r += 50) {
      for (let t = MANURE_INPUT.min; t <= MANURE_INPUT.max; t += 5) {
        const { grainYield } = illustrativeOutcome(r, t)
        expect(grainYield.low).toBeGreaterThanOrEqual(0)
        expect(grainYield.low).toBeLessThanOrEqual(grainYield.value)
        expect(grainYield.high).toBeGreaterThanOrEqual(grainYield.value)
      }
    }
  })

  it('widens the band towards the corners of the table', () => {
    const centre = illustrativeOutcome(450, tonnesForAvailableN(40)).grainYield
    const corner = illustrativeOutcome(150, MANURE_INPUT.max).grainYield
    const relative = (e: { low: number, high: number, value: number }) =>
      (e.high - e.low) / e.value

    expect(relative(corner)).toBeGreaterThan(relative(centre))
  })

  it('draws on the soil stock when no manure is applied', () => {
    expect(illustrativeOutcome(450, 0).nRemaining).toBeLessThan(0)
  })

  it('leaves more nitrogen in the system once yield stops responding', () => {
    const responsive = illustrativeOutcome(450, 20).nRemaining
    const saturated = illustrativeOutcome(450, 50).nRemaining
    expect(saturated).toBeGreaterThan(responsive)
  })

  it('splits every estimate into driver shares that sum to one', () => {
    const { grainYield, grainProtein } = illustrativeOutcome(380, 23)
    for (const estimate of [grainYield, grainProtein]) {
      const total = estimate.drivers.reduce((sum, driver) => sum + driver.share, 0)
      expect(total).toBeCloseTo(1, 6)
    }
  })

  it('keeps the drawing indices inside their unit range', () => {
    for (const [r, t] of [[150, 0], [450, 25], [750, 50]] as const) {
      const outcome = illustrativeOutcome(r, t)
      for (const index of [outcome.canopyIndex, outcome.waterIndex, outcome.nitrogenIndex]) {
        expect(index).toBeGreaterThanOrEqual(0)
        expect(index).toBeLessThanOrEqual(1)
      }
    }
  })
})
