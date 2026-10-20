import { expect, test } from '@playwright/test'

test('an admin invites an advisor, who joins with the link', async ({ browser }) => {
  const stamp = Date.now()
  const admin = await (await browser.newContext()).newPage()
  await admin.goto('/app/register')
  await admin.getByLabel('Name deines Betriebs').fill(`Hof Einladung ${stamp}`)
  await admin.getByLabel('E-Mail').fill(`e2e-admin-${stamp}@example.at`)
  await admin.getByLabel('Passwort').fill('correct horse battery')
  await admin.getByRole('button', { name: 'Konto und Betrieb anlegen' }).click()
  await expect(admin.getByTestId('current-farm')).toHaveText(`Hof Einladung ${stamp}`)

  await admin.getByRole('link', { name: 'Betrieb', exact: true }).click()
  await admin.getByRole('combobox', { name: 'Rolle' }).last().click()
  await admin.getByRole('option', { name: 'Berater' }).click()
  await admin.getByTestId('create-invitation').click()
  const link = await admin.getByTestId('invitation-link').inputValue()
  expect(link).toMatch(/\/app\/invite\//)

  const advisor = await (await browser.newContext()).newPage()
  await advisor.goto(link)
  await expect(advisor.getByText(`Du bist eingeladen, Hof Einladung ${stamp} als Berater beizutreten.`))
    .toBeVisible()
  await advisor.getByRole('link', { name: 'Konto anlegen und beitreten' }).click()
  await advisor.getByLabel('E-Mail').fill(`e2e-advisor-${stamp}@example.at`)
  await advisor.getByLabel('Passwort').fill('correct horse battery')
  await advisor.getByRole('button', { name: 'Konto anlegen und beitreten' }).click()
  await expect(advisor.getByTestId('current-farm')).toHaveText(`Hof Einladung ${stamp}`)

  // The link is single-use.
  await advisor.goto(link)
  await expect(advisor.getByText('Diese Einladung wurde schon verwendet.')).toBeVisible()

  await admin.reload()
  await expect(admin.getByTestId('member-row')).toHaveCount(2)
  await expect(admin.getByTestId('member-row').filter({ hasText: `e2e-advisor-${stamp}` }))
    .toBeVisible()
})
