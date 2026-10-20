import { expect, test } from '@playwright/test'

function uniqueEmail() {
  return `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@example.at`
}

test('register, sign out and sign in again', async ({ page }) => {
  const email = uniqueEmail()
  const password = 'correct horse battery'

  await page.goto('/app')
  await expect(page).toHaveURL(/\/app\/sign-in\?redirect=/)

  await page.getByRole('link', { name: 'Betrieb anlegen' }).click()
  await page.getByLabel('Name deines Betriebs').fill('Hof Playwright')
  await page.getByLabel('E-Mail').fill(email)
  await page.getByLabel('Passwort').fill(password)
  await page.getByRole('button', { name: 'Konto und Betrieb anlegen' }).click()

  await expect(page).toHaveURL(/\/app$/)
  await expect(page.getByTestId('current-farm')).toHaveText('Hof Playwright')

  await page.getByTestId('user-menu').click()
  await page.getByRole('menuitem', { name: 'Abmelden' }).click()
  await expect(page).toHaveURL(/\/app\/sign-in$/)

  // Signed out on the server too: the app sends us back to sign-in.
  await page.goto('/app/account')
  await expect(page).toHaveURL(/\/app\/sign-in\?/)
  expect(new URL(page.url()).searchParams.get('redirect')).toBe('/app/account')

  await page.getByLabel('E-Mail').fill(email.toUpperCase())
  await page.getByLabel('Passwort').fill('wrong password')
  await page.getByRole('button', { name: 'Anmelden' }).click()
  await expect(page.getByText('E-Mail oder Passwort stimmen nicht.')).toBeVisible()

  await page.getByLabel('Passwort').fill(password)
  await page.getByRole('button', { name: 'Anmelden' }).click()

  await expect(page).toHaveURL(/\/app\/account$/)
  await expect(page.getByText(`Angemeldet als ${email}`)).toBeVisible()
  await expect(page.getByTestId('current-farm')).toHaveText('Hof Playwright')
})

test('signed-in state survives a reload', async ({ page }) => {
  await page.goto('/en/app/register')
  await page.getByLabel('Name of your farm').fill('Reload Farm')
  await page.getByLabel('Email').fill(uniqueEmail())
  await page.getByLabel('Password').fill('correct horse battery')
  await page.getByRole('button', { name: 'Create account and farm' }).click()
  await expect(page.getByTestId('current-farm')).toHaveText('Reload Farm')

  await page.reload()

  await expect(page).toHaveURL(/\/en\/app$/)
  await expect(page.getByTestId('current-farm')).toHaveText('Reload Farm')
})
