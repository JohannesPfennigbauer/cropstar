import { execFileSync } from 'node:child_process'
import { mkdtempSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

const apiRoot = fileURLToPath(new URL('../../api', import.meta.url))

/** A synthetic eAMA export (both sets, harvest year 2026) written as loose files. */
function demoExport(variant?: 'reworked'): string[] {
  const dir = mkdtempSync(join(tmpdir(), 'cropstar-eama-'))
  const args = ['run', 'python', '-m', 'tests.eama_export', dir, ...(variant ? [variant] : [])]
  execFileSync('uv', args, { cwd: apiRoot, stdio: 'pipe' })
  return readdirSync(dir).map(name => join(dir, name))
}

async function registerFarm(page: Page) {
  const email = `e2e-areas-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.at`
  await page.goto('/app/sign-in')
  await page.getByRole('link', { name: 'Betrieb anlegen' }).click()
  await page.getByLabel('Name deines Betriebs').fill('Hof Upload')
  await page.getByLabel('E-Mail').fill(email)
  await page.getByLabel('Passwort').fill('correct horse battery')
  await page.getByRole('button', { name: 'Konto und Betrieb anlegen' }).click()
  await expect(page.getByTestId('current-farm')).toHaveText('Hof Upload')
  await page.getByRole('link', { name: 'Schläge', exact: true }).click()
}

async function openUpload(page: Page, files: string[]) {
  await page.getByTestId('upload-areas').first().click()
  const dialog = page.getByRole('dialog', { name: 'Flächen aus eAMA hochladen' })
  await dialog.locator('input[type="file"]').setInputFiles(files)
  await dialog.getByTestId('area-upload-preview-button').click()
  return dialog
}

test('an admin uploads the eAMA export into an empty farm', async ({ page }) => {
  await registerFarm(page)
  const dialog = await openUpload(page, demoExport())

  const preview = dialog.getByTestId('area-upload-preview')
  await expect(preview).toContainText('2026')
  await expect(preview.locator('canvas.maplibregl-canvas')).toBeVisible()
  await dialog.getByTestId('area-upload-confirm').click()

  await expect(page.getByText('Erntejahr 2026 übernommen', { exact: true })).toBeVisible()
  await expect(page.getByTestId('plots-provenance')).toContainText('Wie bei AMA beantragt · Erntejahr 2026')
  await expect(page.getByRole('link', { name: /Winterroggen/ })).toBeVisible()
  await expect(page.locator('canvas.maplibregl-canvas')).toBeVisible()
})

test('a corrected export is assigned to the existing areas before it is applied', async ({ page }) => {
  await registerFarm(page)
  await (await openUpload(page, demoExport())).getByTestId('area-upload-confirm').click()
  await expect(page.getByText('Erntejahr 2026 übernommen', { exact: true })).toBeVisible()

  const dialog = await openUpload(page, demoExport('reworked'))
  const preview = dialog.getByTestId('area-upload-preview')
  await expect(preview.getByTestId('area-upload-counts')).toContainText('1 offen')
  await expect(preview.getByTestId('area-row-plot-1-1')).toContainText('Nutzungsart')
  await expect(preview.getByTestId('area-upload-removed')).toContainText('Schlag 2.2')
  await expect(dialog.getByTestId('area-upload-confirm')).toBeDisabled()

  await preview.getByTestId('area-choice-plot-2-2').click()
  await page.getByRole('option', { name: 'Neu – ohne Vergangenheit' }).click()
  await expect(preview.getByTestId('area-row-plot-2-2')).toContainText('Neu')
  await expect(dialog.getByTestId('area-upload-confirm')).toBeEnabled()
  await dialog.getByTestId('area-upload-confirm').click()

  await expect(page.getByRole('region', { name: /Notifications/ })).toContainText('1 neu, 1 geändert, 1 entfernt.')
  await expect(page.getByRole('link', { name: /Körnermais/ })).toBeVisible()
})
