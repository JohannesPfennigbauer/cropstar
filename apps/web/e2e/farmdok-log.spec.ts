import { expect, test } from '@playwright/test'
import { farmdokCropLog, farmdokFieldList, registerFarm } from './support'

test('a year\'s work comes from the farmdok crop production log, with open questions answered', async ({ page }) => {
  await registerFarm(page)
  await page.getByRole('link', { name: 'Betrieb', exact: true }).click()

  // The year's areas first: from the field list, without an eAMA year to borrow from.
  await page.getByTestId('farmdok-import').click()
  const fieldList = page.getByRole('dialog', { name: 'Feldstücksliste aus farmdok importieren' })
  await fieldList.locator('input[type="file"]').setInputFiles(farmdokFieldList(2025))
  await fieldList.getByTestId('farmdok-preview-button').click()
  await fieldList.getByTestId('farmdok-confirm').click()
  await expect(page.getByTestId('import-batch-row')).toHaveCount(1)

  await page.getByTestId('farmdok-log-import').click()
  const dialog = page.getByRole('dialog', { name: 'Pflanzenbaujournal aus farmdok importieren' })
  await dialog.locator('input[type="file"]').setInputFiles(farmdokCropLog(2025))
  await dialog.getByTestId('farmdok-log-preview-button').click()

  const preview = dialog.getByTestId('farmdok-log-preview')
  await expect(preview.getByTestId('farmdok-log-unresolved')).toContainText('Unbekanntes Produkt „Rindermist“')
  await expect(dialog.getByTestId('farmdok-log-confirm')).toBeDisabled()
  await preview.getByTestId('farmdok-product-Rindermist').click()
  await page.getByRole('option', { name: '„Rindermist“ neu anlegen' }).click()
  await preview.getByTestId('farmdok-product-Winterroggen').click()
  await page.getByRole('option', { name: '„Winterroggen“ neu anlegen' }).click()
  await expect(preview.getByTestId('farmdok-log-unresolved')).toHaveCount(0)
  await expect(preview.getByTestId('farmdok-log-task-count')).toHaveText('5 mit 5 Maßnahmen')
  await expect(preview.getByTestId('farmdok-log-task').first()).toContainText('Rindermist · 25 m³/ha')
  await dialog.getByTestId('farmdok-log-confirm').click()

  const batch = page.getByTestId('import-batch-row').filter({ hasText: 'Pflanzenbaujournal' })
  await expect(batch).toContainText('5 Aufgaben')

  await page.getByRole('link', { name: 'Aufgaben', exact: true }).click()
  await page.getByRole('tab', { name: 'Erledigt' }).click()
  await page.getByText('Mähdrusch').first().click()
  await expect(page.getByTestId('task-imported')).toContainText('Importiert aus farmdok am')
  await page.keyboard.press('Escape')

  await page.getByRole('link', { name: 'Betrieb', exact: true }).click()
  await batch.getByTestId('undo-import').click()
  await expect(batch).toHaveCount(0)
})
