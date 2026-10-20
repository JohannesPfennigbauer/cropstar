// Same-origin proxy to the Cropstar API: the browser never talks to the API directly, so
// session cookies need no CORS and self-hosters need only one domain.
export default defineEventHandler((event) => {
  const { apiBaseUrl } = useRuntimeConfig()
  return proxyRequest(event, `${apiBaseUrl.replace(/\/+$/, '')}${event.path}`)
})
