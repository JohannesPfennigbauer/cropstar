import { execFileSync } from 'node:child_process'
import { mkdtempSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
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

const apiRoot = fileURLToPath(new URL('../../api', import.meta.url))

/** A synthetic eAMA export (both sets, harvest year 2026) written as loose files. */
export function demoExport(variant?: 'reworked'): string[] {
  const dir = mkdtempSync(join(tmpdir(), 'cropstar-eama-'))
  const args = ['run', 'python', '-m', 'tests.eama_export', dir, ...(variant ? [variant] : [])]
  execFileSync('uv', args, { cwd: apiRoot, stdio: 'pipe' })
  return readdirSync(dir).map(name => join(dir, name))
}

/** A synthetic farmdok field list (Feldstücksliste) for `year`. */
export function farmdokFieldList(year: number): string {
  const path = join(mkdtempSync(join(tmpdir(), 'cropstar-farmdok-')), `Feldstücksliste_${year}.xls`)
  execFileSync('uv', ['run', 'python', '-m', 'tests.farmdok_export', path, String(year)], { cwd: apiRoot, stdio: 'pipe' })
  return path
}

/** A synthetic farmdok crop production log (Pflanzenbaujournal) for `year`. */
export function farmdokCropLog(year: number): string {
  const path = join(mkdtempSync(join(tmpdir(), 'cropstar-farmdok-')), `Pflanzenbaujournal_${year}.xls`)
  execFileSync('uv', ['run', 'python', '-m', 'tests.farmdok_export', path, String(year), 'crop_log'], { cwd: apiRoot, stdio: 'pipe' })
  return path
}

export async function registerFarm(page: Page) {
  const email = `e2e-areas-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.at`
  await page.goto('/app/sign-in')
  await page.getByRole('link', { name: 'Betrieb anlegen' }).click()
  await page.getByLabel('Name deines Betriebs').fill('Hof Upload')
  await page.getByLabel('E-Mail').fill(email)
  await page.getByLabel('Passwort').fill('correct horse battery')
  await page.getByRole('button', { name: 'Konto und Betrieb anlegen' }).click()
  await expect(page.getByTestId('current-farm')).toHaveText('Hof Upload')
  await page.getByRole('link', { name: 'Übersicht', exact: true }).click()
}

export async function openUpload(page: Page, files: string[]) {
  await page.getByTestId('upload-areas').first().click()
  const dialog = page.getByRole('dialog', { name: 'Flächen aus eAMA hochladen' })
  await dialog.locator('input[type="file"]').setInputFiles(files)
  await dialog.getByTestId('area-upload-preview-button').click()
  return dialog
}
