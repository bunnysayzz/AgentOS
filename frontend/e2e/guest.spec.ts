import { expect, test } from '@playwright/test'

/**
 * Guest-mode smoke tests against the REAL stack (FastAPI :8000 + Vite :5173).
 * These flows need no Firebase credentials: guests can browse every page
 * (nothing is locked behind a login wall), so these double as a smoke test
 * for the app shell, routing, and public pages.
 */

test.describe('guest flows', () => {
  test('dashboard renders the guest hero and app shell', async ({ page }) => {
    await page.goto('/')

    // App shell: sidebar branding + navigation sections
    const sidebar = page.locator('aside')
    await expect(sidebar.getByText('AgentOS', { exact: true })).toBeVisible()
    await expect(sidebar.getByText('Dashboard', { exact: true })).toBeVisible()
    await expect(sidebar.getByText('MCP Gateway', { exact: true })).toBeVisible()
    await expect(sidebar.getByText('Evaluations', { exact: true })).toBeVisible()

    // Guest hero
    await expect(page.getByRole('heading', { level: 1, name: /build agents that/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /sign in to save your work/i })).toBeVisible()
    await expect(page.getByRole('link', { name: /create an account/i })).toBeVisible()

    // Getting-started checklist
    await expect(page.getByText('Getting Started', { exact: true })).toBeVisible()
    await expect(page.getByText('Create a workspace', { exact: true })).toBeVisible()
    await expect(page.getByText('Connect an AI provider', { exact: true })).toBeVisible()
  })

  test('quick actions navigate to their pages (guest mode browses freely)', async ({ page }) => {
    await page.goto('/')
    await page.getByText('New Agent', { exact: true }).click()

    await page.waitForURL(/\/agents/)
    await expect(page.getByRole('heading', { level: 1, name: 'Agents' })).toBeVisible()
  })

  test('gallery is public and lists agents or a graceful empty state', async ({ page }) => {
    await page.goto('/gallery')

    await expect(page.getByRole('heading', { level: 1, name: /steal a head start/i })).toBeVisible()
    const cards = page.locator('.card')
    if ((await cards.count()) > 0) {
      await expect(cards.first()).toBeVisible()
    } else {
      await expect(page.getByText(/no agents|coming soon|empty/i).first()).toBeVisible()
    }
  })

  test('unknown routes render the 404 page', async ({ page }) => {
    await page.goto('/this-route-does-not-exist')

    await expect(page.getByRole('heading', { level: 1, name: '404' })).toBeVisible()
    await expect(page.getByText('Page not found')).toBeVisible()
  })

  test('login page renders the sign-in form', async ({ page }) => {
    await page.goto('/login')

    await expect(page.getByPlaceholder('you@example.com')).toBeVisible()
    await expect(page.getByRole('button', { name: /sign in with google/i })).toBeVisible()
  })
})
