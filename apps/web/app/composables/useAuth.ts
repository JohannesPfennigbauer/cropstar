import type { Schemas } from '@cropstar/api-client'
import type { ApiErrorCode } from '~/utils/api-error'

export type Me = Schemas['Me']
type Result = { ok: true } | { ok: false, code: ApiErrorCode }

/**
 * The signed-in user, shared across the app. `undefined` means "not asked yet",
 * `null` means "nobody is signed in".
 */
export function useAuth() {
  const api = useApi()
  const me = useState<Me | null | undefined>('auth:me', () => undefined)

  const membership = computed(() => me.value?.memberships[0] ?? null)
  const farm = computed(() => membership.value?.farm ?? null)

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

  return { me, membership, farm, refresh, ensure, signIn, register, signOut }
}
