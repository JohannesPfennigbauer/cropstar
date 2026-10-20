import type { Schemas } from '@cropstar/api-client'
import type { ApiErrorCode } from '~/utils/api-error'

export type Me = Schemas['Me']

const FARM_KEY = 'cropstar:farm'
type Result = { ok: true } | { ok: false, code: ApiErrorCode }

/**
 * The signed-in user, shared across the app. `undefined` means "not asked yet",
 * `null` means "nobody is signed in".
 */
export function useAuth() {
  const api = useApi()
  const me = useState<Me | null | undefined>('auth:me', () => undefined)
  // The Farm being worked on; remembered in this browser across visits.
  const selectedFarmId = useState<string | null>('auth:farm', () =>
    import.meta.client ? localStorage.getItem(FARM_KEY) : null)

  const membership = computed(() => {
    const memberships = me.value?.memberships ?? []
    return memberships.find(m => m.farm.id === selectedFarmId.value) ?? memberships[0] ?? null
  })
  const farm = computed(() => membership.value?.farm ?? null)

  function selectFarm(farmId: string) {
    selectedFarmId.value = farmId
    if (import.meta.client) localStorage.setItem(FARM_KEY, farmId)
  }

  async function refresh(): Promise<Me | null> {
    const { data, response } = await api.GET('/api/me')
    if (response.status === 401) {
      me.value = null
    }
    else if (!data) {
      throw createError({ statusCode: response.status, statusMessage: response.statusText })
    }
    else {
      me.value = data
    }
    return me.value
  }

  async function ensure(): Promise<Me | null> {
    return me.value === undefined ? refresh() : me.value
  }

  async function signIn(email: string, password: string): Promise<Result> {
    const { data, error } = await api.POST('/api/auth/sign-in', { body: { email, password } })
    if (!data) return { ok: false, code: apiErrorCode(error) }
    me.value = data
    return { ok: true }
  }

  async function createFarm(name: string): Promise<Result> {
    const before = new Set(me.value?.memberships.map(m => m.farm.id))
    const { data, error } = await api.POST('/api/farms', { body: { name } })
    if (!data) return { ok: false, code: apiErrorCode(error) }
    me.value = data
    const created = data.memberships.find(m => !before.has(m.farm.id))
    if (created) selectFarm(created.farm.id)
    return { ok: true }
  }

  async function register(body: Schemas['RegisterRequest']): Promise<Result> {
    const { data, error } = await api.POST('/api/auth/register', { body })
    if (!data) return { ok: false, code: apiErrorCode(error) }
    me.value = data
    return { ok: true }
  }

  async function signOut(): Promise<void> {
    await api.POST('/api/auth/sign-out')
    me.value = null
  }

  return { me, membership, farm, selectFarm, refresh, ensure, signIn, register, createFarm, signOut }
}
