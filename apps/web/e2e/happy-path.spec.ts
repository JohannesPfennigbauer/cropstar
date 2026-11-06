import { expect, test } from '@playwright/test'
import { seedDemoAdmin, signIn } from './support'

test('plots, an Operation on two of them, its log, and a locked season', async ({ page }) => {
  const { email, password } = seedDemoAdmin('e2e-happy-path')
  await signIn(page, email, password)

  // A fertiliser with its contents and their source, as kept under Farm › Farm inputs.
  const me = await (await page.request.get('/api/me')).json()
  const created = await page.request.post(`/api/farms/${me.memberships[0].farm.id}/farm-inputs`, {
    data: {
      kind: 'fertiliser',
      name: 'Rindergülle',
      unit: 'm3',
      total_n: 3.51,
      available_n: 2.14,
      p2o5: 1.39,
      k2o: 6.94,
      value_source: 'standard_value',
      source_reference: 'RSD, 8. Auflage'
    }
  })
  expect(created.status()).toBe(201)

  // The seeded Plots are on the list and on the map.
  await page.getByRole('link', { name: 'Schläge', exact: true }).click()
  await expect(page.getByRole('link', { name: /Winterroggen/ })).toBeVisible()
  await expect(page.locator('canvas.maplibregl-canvas')).toBeVisible()

  await page.getByRole('link', { name: 'Aufgaben', exact: true }).click()
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
  const plan = editor.getByTestId('planned-details')
  await plan.getByTestId('details-farm_input_id').click()
  await page.getByRole('option', { name: 'Rindergülle' }).click()
  // Choosing slurry with contents per m³ leaves only units by volume.
  await expect(plan.getByTestId('details-unit')).toHaveText('m³/ha')
  await plan.getByLabel('Menge je ha').fill('20')
  await plan.getByLabel('Notiz').fill('Schleppschuh')
  await editor.getByRole('button', { name: 'Anlegen' }).click()

  const row = page.getByTestId('task-row').filter({ hasText: 'Gülle ausbringen' })
  await expect(row.getByTestId('operation-badge')).toHaveText('Düngung · 0/2')

  // Only the rye is done today; the sunflowers stay Open.
  await row.getByTestId('task-toggle').click()
  const completion = page.getByRole('dialog', { name: 'Gülle ausbringen erledigen' })
  const rows = completion.getByTestId('complete-row')
  await expect(rows.first().getByLabel('Menge je ha')).toHaveValue('20')
  await expect(rows.first().getByLabel('Notiz')).toHaveValue('Schleppschuh')
  await rows.nth(1).getByRole('checkbox').click()
  await rows.first().getByLabel('Menge je ha').fill('18')
  await completion.getByTestId('record-operations').click()
  await expect(row.getByTestId('operation-badge')).toHaveText('Düngung · 1/2')

  await page.getByRole('link', { name: 'Schläge', exact: true }).click()
  await page.getByRole('link', { name: /Winterroggen/ }).click()
  await expect(page.getByTestId('operation-log')).toContainText('Düngung · Gülle ausbringen')
  await expect(page.getByTestId('operation-log')).toContainText('Rindergülle · 18 m³/ha · Schleppschuh')
  await expect(page.getByTestId('nutrients-applied')).toContainText('≙ 63,2 kg N (38,5 jahreswirksam) · 25 kg P₂O₅ · 124,9 kg K₂O je ha')
  await expect(page.getByTestId('nutrients-applied')).toContainText('Richtwert · RSD, 8. Auflage')
  const plotPage = page.url()

  // The season is closed: everything referring to it becomes read-only.
  await page.getByRole('link', { name: 'Betrieb', exact: true }).click()
  await page.getByTestId('lock-year').click()
  await expect(page.getByTestId('harvest-year-row')).toContainText(`Gesperrt von ${email}`)

  await page.goto(plotPage)
  await expect(page.getByTestId('lock-notice')).toBeVisible()
  await expect(page.getByTestId('new-plot-task')).toBeDisabled()

  await page.getByRole('link', { name: 'Aufgaben', exact: true }).click()
  await expect(row.getByTestId('task-toggle')).toBeDisabled()
  await row.getByText('Gülle ausbringen').click()
  const locked = page.getByRole('dialog', { name: 'Aufgabe' })
  await expect(locked.getByTestId('lock-notice')).toBeVisible()
  await expect(locked.getByLabel('Titel')).toBeDisabled()
  await expect(locked.getByRole('button', { name: 'Speichern' })).toHaveCount(0)
})
