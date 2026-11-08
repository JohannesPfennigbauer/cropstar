import { expect, test } from '@playwright/test'
import { demoExport, farmdokFieldList, openUpload, registerFarm } from './support'

test('an older year comes from the farmdok field list with borrowed geometry, and can be undone', async ({ page }) => {
  await registerFarm(page)
  await (await openUpload(page, demoExport())).getByTestId('area-upload-confirm').click()
  await expect(page.getByText('Erntejahr 2026 übernommen', { exact: true })).toBeVisible()

  await page.getByRole('link', { name: 'Betrieb', exact: true }).click()
  await page.getByTestId('farmdok-import').click()
  const dialog = page.getByRole('dialog', { name: 'Feldstücksliste aus farmdok importieren' })
  await dialog.locator('input[type="file"]').setInputFiles(farmdokFieldList(2025))
  await dialog.getByTestId('farmdok-preview-button').click()

  const preview = dialog.getByTestId('farmdok-preview')
  await expect(preview).toContainText('2025')
  await expect(preview.getByTestId('farmdok-reference-year')).toHaveText('2026')
  await expect(preview.getByTestId('farmdok-geometry-counts')).toContainText('4 Schläge über Feldstück- und Schlagnummer, 0 über die Fläche')
  await dialog.getByTestId('farmdok-confirm').click()
  await expect(page.getByText('Erntejahr 2025 importiert', { exact: true })).toBeVisible()
  const batch = page.getByTestId('import-batch-row')
  await expect(batch).toContainText('farmdok-Feldstücksliste · 2025')

  await page.getByRole('link', { name: 'Übersicht', exact: true }).click()
  await page.getByTestId('harvest-year').click()
  await page.getByRole('option', { name: '2025' }).click()
  await expect(page.getByTestId('plots-provenance')).toContainText('Vorläufige Geometrie, übernommen aus Erntejahr 2026')
  await expect(page.getByTestId('plot-row').first()).toContainText('vorläufig')

  await page.getByRole('link', { name: 'Betrieb', exact: true }).click()
  await batch.getByTestId('undo-import').click()
  await expect(page.getByRole('region', { name: /Notifications/ })).toContainText('Import rückgängig gemacht.')
  await expect(batch).toHaveCount(0)
})
