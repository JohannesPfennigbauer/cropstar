// Liveness probe for the container orchestrator; intentionally does no I/O.
export default defineEventHandler(() => ({
  status: 'ok',
  service: 'cropstar-web'
}))
