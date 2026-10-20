import { createApiClient } from '@cropstar/api-client'

/** Typed client for the Cropstar API, reached through this origin's `/api` proxy. */
export function useApi() {
  return createApiClient(useRequestURL().origin)
}
