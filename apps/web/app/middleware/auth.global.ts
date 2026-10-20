// Guards the farm app. Pages opt out with `definePageMeta({ auth: 'guest' | 'public' })`:
// guest pages (sign-in, register, ...) are for signed-out visitors, public pages for anyone.
export default defineNuxtRouteMiddleware(async (to) => {
  if (!/^\/(en\/)?app(\/|$)/.test(to.path) || to.meta.auth === 'public') return

  const localePath = useLocalePath()
  const me = await useAuth().ensure()

  if (to.meta.auth === 'guest') {
    if (me) return navigateTo(localePath('/app'))
    return
  }
  if (!me) {
    return navigateTo({ path: localePath('/app/sign-in'), query: { redirect: to.fullPath } })
  }
})
