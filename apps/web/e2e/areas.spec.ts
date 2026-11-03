import { execFileSync } from 'node:child_process'
import { mkdtempSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { expect, test } from '@playwright/test'

const apiRoot = fileURLToPath(new URL('../../api', import.meta.url))

/** A synthetic eAMA export (both sets, harvest year 2026) written as loose files. */
function demoExport(): string[] {
  const dir = mkdtempSync(join(tmpdir(), 'cropstar-eama-'))
  execFileSync('uv', ['run', 'python', '-m', 'tests.eama_export', dir], { cwd: apiRoot, stdio: 'pipe' })
  return readdirSync(dir).map(name => join(dir, name))
}

test('an admin uploads the eAMA export into an empty farm', async ({ page }) => {
  const email = `e2e-areas-${Date.now()}-${Math.random().toString(36).slice(2, 6)}@example.at`

  await page.goto('/app/sign-in')
  await page.getByRole('link', { name: 'Betrieb anlegen' }).click()
  await page.getByLabel('Name deines Betriebs').fill('Hof Upload')
  await page.getByLabel('E-Mail').fill(email)
  await page.getByLabel('Passwort').fill('correct horse battery')
  await page.getByRole('button', { name: 'Konto und Betrieb anlegen' }).click()
  await expect(page.getByTestId('current-farm')).toHaveText('Hof Upload')

  await page.getByRole('link', { name: 'Schläge', exact: true }).click()
  await page.getByTestId('upload-areas').click()

  const dialog = page.getByRole('dialog', { name: 'Flächen aus eAMA hochladen' })
  await dialog.locator('input[type="file"]').setInputFiles(demoExport())
  await dialog.getByTestId('area-upload-preview-button').click()

  const preview = dialog.getByTestId('area-upload-preview')
  await expect(preview).toContainText('2026')
  await expect(preview.locator('canvas.maplibregl-canvas')).toBeVisible()
  await dialog.getByTestId('area-upload-confirm').click()

  await expect(page.getByText('Erntejahr 2026 übernommen', { exact: true })).toBeVisible()
  await expect(page.getByTestId('plots-provenance')).toContainText('Wie bei AMA beantragt · Erntejahr 2026')
  await expect(page.getByRole('link', { name: /Winterroggen/ })).toBeVisible()
  await expect(page.locator('canvas.maplibregl-canvas')).toBeVisible()
})
