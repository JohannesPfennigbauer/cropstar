import { expect, test } from '@playwright/test'
import { seedDemoAdmin, signIn } from './support'

test('plan an Operation on two Plots, record one, find it in the Plot\'s log', async ({ page }) => {
  const { email, password } = seedDemoAdmin('e2e-operations')
  await signIn(page, email, password)

  await page.getByRole('link', { name: 'Aufgaben' }).click()
  await page.getByTestId('new-task').click()
  const editor = page.getByRole('dialog', { name: 'Neue Aufgabe' })
  await editor.getByLabel('Titel').fill('Gülle ausbringen')
  await editor.getByTestId('operation-type').click()
  await page.getByRole('option', { name: 'Düngung' }).click()
  await editor.getByTestId('task-areas').click()
  await page.getByRole('option', { name: 'Schlag 1.1 · Winterroggen' }).click()
  await page.getByRole('option', { name: 'Schlag 2.1 · Sonnenblumen' }).click()
  // A click outside closes the multi-select once its opening has settled.
  await expect(async () => {
    await editor.getByRole('heading', { name: 'Neue Aufgabe' }).click()
    await expect(page.getByRole('listbox')).toBeHidden({ timeout: 500 })
  }).toPass()
  await editor.getByLabel('Plan').fill('Schleppschuh, 20 m³/ha')
  await editor.getByRole('button', { name: 'Anlegen' }).click()

  const row = page.getByTestId('task-row').filter({ hasText: 'Gülle ausbringen' })
  await expect(row.getByTestId('operation-badge')).toHaveText('Düngung · 0/2')

  // Only the rye is done today; the sunflowers stay Open.
  await row.getByTestId('task-toggle').click()
  const completion = page.getByRole('dialog', { name: 'Gülle ausbringen erledigen' })
  const rows = completion.getByTestId('complete-row')
  await expect(rows.first().getByRole('textbox', { name: 'Ist' })).toHaveValue('Schleppschuh, 20 m³/ha')
  await rows.nth(1).getByRole('checkbox').click()
  await rows.first().getByRole('textbox', { name: 'Ist' }).fill('Schleppschuh, 18 m³/ha')
  await completion.getByTestId('record-operations').click()
  await expect(row.getByTestId('operation-badge')).toHaveText('Düngung · 1/2')

  await page.getByRole('link', { name: 'Schläge' }).click()
  await page.getByRole('link', { name: /Winterroggen/ }).click()
  await expect(page.getByTestId('operation-log')).toContainText('Düngung · Gülle ausbringen')
  await expect(page.getByTestId('operation-log')).toContainText('Schleppschuh, 18 m³/ha')
})
