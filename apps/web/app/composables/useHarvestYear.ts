import type { Schemas } from '@cropstar/api-client'

type HarvestYear = Schemas['HarvestYearOut']

/** The Harvest Year the farm app currently shows, shared across views, with its lock. */
export function useHarvestYear() {
  const api = useApi()
  const { farm } = useAuth()
  const entries = useState<HarvestYear[]>('harvest-year:entries', () => [])
  const selected = useState<number | null>('harvest-year:selected', () => null)
  const years = computed(() => entries.value.map(entry => entry.year))

  async function load(): Promise<void> {
    if (!farm.value) {
      entries.value = []
      selected.value = null
      return
    }
    const { data } = await api.GET('/api/farms/{farm_id}/harvest-years', {
      params: { path: { farm_id: farm.value.id } }
    })
    entries.value = data ?? []
    // Default: the most recent Harvest Year that has Plots.
    if (selected.value === null || !years.value.includes(selected.value)) {
      selected.value = years.value[0] ?? null
    }
  }

  /** The lock on `year`, or null when it is open (or not a Harvest Year at all). */
  function lockOf(year: number | null | undefined) {
    return entries.value.find(entry => entry.year === year)?.lock ?? null
  }

  return { entries, years, selected, load, lockOf }
}
