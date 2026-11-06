import { expect, test } from '@playwright/test'
import { demoExport, openUpload, registerFarm } from './support'

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
