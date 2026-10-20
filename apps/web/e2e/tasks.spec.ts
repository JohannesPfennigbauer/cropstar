import { expect, test } from '@playwright/test'

test('plan a task, tick it off, find it under done', async ({ page }) => {
  await page.goto('/app/register')
  await page.getByLabel('Name deines Betriebs').fill('Hof Aufgaben')
  await page.getByLabel('E-Mail').fill(`e2e-tasks-${Date.now()}@example.at`)
  await page.getByLabel('Passwort').fill('correct horse battery')
  await page.getByRole('button', { name: 'Konto und Betrieb anlegen' }).click()
  await expect(page.getByTestId('current-farm')).toHaveText('Hof Aufgaben')

  await page.getByRole('link', { name: 'Aufgaben' }).click()
  await expect(page.getByText('Keine Aufgaben')).toBeVisible()

  await page.getByTestId('new-task').click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Titel').fill('Hecke am Kellerberg schneiden')
  await dialog.getByRole('combobox', { name: 'Priorität' }).click()
  await page.getByRole('option', { name: 'Hoch' }).click()
  await dialog.getByRole('button', { name: 'Anlegen' }).click()

  const row = page.getByTestId('task-row').filter({ hasText: 'Hecke am Kellerberg schneiden' })
  await expect(row).toContainText('Hoch')

  await row.getByTestId('task-toggle').click()
  await expect(page.getByTestId('task-row')).toHaveCount(0)

  await page.getByRole('tab', { name: 'Erledigt' }).click()
  await expect(page.getByTestId('task-row').filter({ hasText: 'Hecke am Kellerberg schneiden' }))
    .toBeVisible()
})
