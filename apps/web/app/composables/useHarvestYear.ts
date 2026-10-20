/** The Harvest Year the farm app currently shows, shared across views. */
export function useHarvestYear() {
  const api = useApi()
  const { farm } = useAuth()
  const years = useState<number[]>('harvest-year:years', () => [])
  const selected = useState<number | null>('harvest-year:selected', () => null)

  async function load(): Promise<void> {
    if (!farm.value) {
      years.value = []
      selected.value = null
      return
    }
    const { data } = await api.GET('/api/farms/{farm_id}/harvest-years', {
      params: { path: { farm_id: farm.value.id } }
    })
    years.value = data ?? []
    // Default: the most recent Harvest Year that has Plots.
    if (selected.value === null || !years.value.includes(selected.value)) {
      selected.value = years.value[0] ?? null
    }
  }

  return { years, selected, load }
}
