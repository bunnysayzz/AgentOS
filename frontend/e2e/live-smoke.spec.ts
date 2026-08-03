import { expect, test } from '@playwright/test'

/**
 * TEMPORARY live smoke test — hits the production URL directly.
 * Verifies: login page renders, Google button present, invalid creds show an
 * error, and a fresh email/password account can register + log in.
 * Deleted after the run (never committed).
 */

const BASE = 'https://letsagentos.onrender.com'

test.describe('live auth smoke', () => {
  test('login page renders with Google + email options', async ({ page }) => {
    await page.goto(`${BASE}/login`)
    await expect(page.getByText('AgentOS Studio')).toBeVisible()
    await expect(page.getByPlaceholder('you@example.com')).toBeVisible()
    await expect(page.getByPlaceholder('••••••••')).toBeVisible()
    await expect(page.getByRole('button', { name: /sign in with google/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /^sign in$/i })).toBeVisible()
  })

  test('invalid credentials show an error box', async ({ page }) => {
    await page.goto(`${BASE}/login`)
    await page.getByPlaceholder('you@example.com').fill('nobody-live@example.com')
    await page.getByPlaceholder('••••••••').fill('definitely-wrong-password')
    await page.getByRole('button', { name: /^sign in$/i }).click()
    await expect(page.getByTestId('auth-error')).toBeVisible({ timeout: 20_000 })
  })

  test('register a new account and log back in', async ({ page }) => {
    const email = `live-e2e-${Date.now()}@example.com`
    const pass = 'SuperSecret123!'

    // Register
    await page.goto(`${BASE}/register`)
    await expect(page.getByRole('heading', { name: 'Create Account' })).toBeVisible()
    await page.getByPlaceholder('John Doe').fill('Live E2E User')
    await page.getByPlaceholder('you@example.com').fill(email)
    await page.getByPlaceholder('••••••••').fill(pass)
    await page.getByRole('button', { name: /create account/i }).click()

    // Should land on the dashboard (register + auto-login)
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 30_000 })

    // Sign out, then log back in with the same credentials
    await page.evaluate(() => localStorage.clear())
    await page.goto(`${BASE}/login`)
    await page.getByPlaceholder('you@example.com').fill(email)
    await page.getByPlaceholder('••••••••').fill(pass)
    await page.getByRole('button', { name: /^sign in$/i }).click()

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 30_000 })
  })
})
