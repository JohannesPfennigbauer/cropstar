import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export type { components, paths }
export type Schemas = components['schemas']

/**
 * A typed client for the Cropstar API. Paths include their `/api` prefix, so `baseUrl` is
 * the web origin the API is proxied behind, e.g. `https://cropstar.at`.
 */
export function createApiClient(baseUrl: string) {
  return createClient<paths>({ baseUrl, credentials: 'same-origin' })
}

export type ApiClient = ReturnType<typeof createApiClient>
