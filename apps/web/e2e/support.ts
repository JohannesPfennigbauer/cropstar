import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { expect, type Page } from '@playwright/test'

const repoRoot = fileURLToPath(new URL('../../..', import.meta.url))

/** A fresh Admin of a fresh demo Farm with the seeded Fields and Plots of 2026. */
export function seedDemoAdmin(prefix: string) {
  const email = `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.at`
  const password = 'correct horse battery'
  // The seed refuses production; the browser tests run against a throwaway database.
  const env = { ...process.env, CROPSTAR_ENVIRONMENT: 'development' }
  if (process.env.CROPSTAR_E2E_DATABASE_URL) {
    env.CROPSTAR_DATABASE_URL = process.env.CROPSTAR_E2E_DATABASE_URL
  }
  execFileSync('uv', ['run', 'cropstar-api', 'seed-demo', '--email', email, '--password', password], {
    cwd: repoRoot,
    env,
    stdio: 'pipe'
  })
  return { email, password }
}

export async function signIn(page: Page, email: string, password: string) {
  await page.goto('/app/sign-in')
  await page.getByLabel('E-Mail').fill(email)
  await page.getByLabel('Passwort').fill(password)
  await page.getByRole('button', { name: 'Anmelden' }).click()
  await expect(page.getByTestId('current-farm')).toHaveText('Demo-Betrieb Weinviertel')
}
