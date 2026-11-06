import { expect, test } from '@playwright/test'
import { seedDemoAdmin, signIn } from './support'

test('a fertiliser starts from the catalogue, keeps its source and can be archived', async ({ page }) => {
  const { email, password } = seedDemoAdmin('e2e-inputs')
  await signIn(page, email, password)

  await page.getByRole('link', { name: 'Betrieb', exact: true }).click()
  await page.getByTestId('open-farm-inputs').click()
  await expect(page.getByRole('heading', { name: 'Betriebsmittel', level: 1 })).toBeVisible()

  await page.getByTestId('new-input').click()
  const editor = page.getByRole('dialog', { name: 'Neues Betriebsmittel' })
  await editor.getByTestId('input-catalogue').click()
  await page.getByRole('option', { name: 'Rindergülle (Milchkühe 6.000 kg Milch)' }).click()
  await expect(editor.getByTestId('input-total_n')).toHaveValue('3.51')
  await expect(editor.getByTestId('input-reference')).toHaveValue(/RSD, 8\. Auflage/)
  await expect(editor.getByTestId('input-catalogue-note')).toBeVisible()
  await editor.getByTestId('input-name').fill('Rindergülle Stall Nord')
  await editor.getByTestId('save-input').click()

  const row = page.getByTestId('input-row').filter({ hasText: 'Rindergülle Stall Nord' })
  await expect(row).toContainText('je m³: 3,51 kg N (2,14 jahreswirksam) · 1,39 kg P₂O₅ · 6,94 kg K₂O')
  await expect(row).toContainText('Richtwert · RSD, 8. Auflage')

  await row.click()
  const existing = page.getByRole('dialog', { name: 'Rindergülle Stall Nord' })
  await existing.getByTestId('archive-input').click()
  await expect(row).toHaveCount(0)
  await page.getByRole('button', { name: '1 archiviertes anzeigen' }).click()
  await expect(row).toContainText('Archiviert')
})
