import { expect, test } from '@playwright/test'

/**
 * End-to-end smoke tests against the REAL stack:
 *   backend  → FastAPI on :8000 (SQLite)
 *   frontend → Vite on :5173 (proxies /api → :8000)
 */

test.describe('auth flows', () => {
  test('login page renders the sign-in form', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByText('AgentOS Studio')).toBeVisible()
    await expect(page.getByPlaceholder('you@example.com')).toBeVisible()
    await expect(page.getByPlaceholder('••••••••')).toBeVisible()
    await expect(page.getByRole('button', { name: /sign in with google/i })).toBeVisible()
    await expect(page.getByRole('button', { name: /^sign in$/i })).toBeVisible()
  })

  test('invalid credentials show the backend error message', async ({ page }) => {
    await page.goto('/login')

    await page.getByPlaceholder('you@example.com').fill('nobody@example.com')
    await page.getByPlaceholder('••••••••').fill('definitely-wrong-password')
    await page.getByRole('button', { name: /^sign in$/i }).click()

    await expect(page.getByText(/invalid email or password/i)).toBeVisible()
  })

  test('register link navigates to the register page', async ({ page }) => {
    await page.goto('/login')
    await page.getByRole('link', { name: /create one/i }).click()

    await expect(page).toHaveURL(/\/register$/)
    await expect(page.getByRole('button', { name: /create account/i })).toBeVisible()
  })

  test('unauthenticated users are redirected to /login from protected routes', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login/)
    await expect(page.getByPlaceholder('you@example.com')).toBeVisible()
  })

  test('registering a new account and logging in works end to end', async ({ page }) => {
    const email = `e2e-${Date.now()}@example.com`
    const username = `e2e-user-${Date.now()}`

    // Register via the register page
    await page.goto('/register')
    await page.getByPlaceholder('John Doe').fill('E2E User')
    await page.getByPlaceholder('johndoe').fill(username)
    await page.getByPlaceholder('you@example.com').fill(email)
    await page.getByPlaceholder('••••••••').fill('SuperSecret123!')
    await page.getByRole('button', { name: /create account/i }).click()

    // Landing on the dashboard means registration + auto-login succeeded
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 })

    // Sign out and log back in with the same credentials
    await page.evaluate(() => localStorage.clear())
    await page.goto('/login')
    await page.getByPlaceholder('you@example.com').fill(email)
    await page.getByPlaceholder('••••••••').fill('SuperSecret123!')
    await page.getByRole('button', { name: /^sign in$/i }).click()

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 })
  })
})
