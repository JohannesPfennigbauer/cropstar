import { expect, test } from '@playwright/test'

test('a task moves across the board with clicks, and back with undo', async ({ page }) => {
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

  const board = page.getByTestId('task-board')
  await expect(board.getByTestId('board-column')).toHaveText(['Geplant', 'Offen', 'In Arbeit', 'Erledigt'])
  await expect(board.getByTestId('board-lane')).toHaveText(['Ohne Datum'])
  const card = board.getByTestId('task-card').filter({ hasText: 'Hecke am Kellerberg schneiden' })
  await expect(card).toContainText('Hoch')

  // Each click moves it one status on; the last one records it as done.
  const toasts = page.getByRole('region', { name: /Notifications/ })
  await card.click()
  await expect(toasts).toContainText('→ Offen')
  await card.click()
  await expect(toasts).toContainText('→ In Arbeit')
  await card.click()
  await expect(toasts).toContainText('„Hecke am Kellerberg schneiden“ erledigt')
  await expect(card).toHaveClass(/opacity-70/)

  await toasts.getByRole('button', { name: 'Rückgängig' }).last().click()
  await expect(card).not.toHaveClass(/opacity-70/)

  // A double click opens it.
  await card.dblclick()
  await expect(page.getByRole('dialog', { name: 'Aufgabe' })).toBeVisible()
  await expect(page.getByTestId('task-stage')).toHaveText('In Arbeit')
})
