import { test, expect } from '@playwright/test'

/**
 * Automates: Login (admin/admin) → Connect to DB → Open Workspace.
 *
 * Run when frontend (and backend) are up. Use for quick local testing so you
 * don’t have to type credentials and connection each time.
 *
 * Env (optional):
 *   KOTTE_BASE_URL     - App URL (default http://localhost:5173)
 *   KOTTE_DB_HOST      - DB host (default localhost)
 *   KOTTE_DB_PORT      - DB port (default 5455)
 *   KOTTE_DB_NAME      - DB name (default postgresDB)
 *   KOTTE_DB_USER      - DB user (default postgresUser)
 *   KOTTE_DB_PASSWORD  - DB password (default postgresPW)
 *   KEEP_BROWSER_OPEN  - Set to 1 to leave browser open after reaching workspace
 *
 * Usage:
 *   npm run quick-start              # headless
 *   npm run quick-start:headed       # see the browser
 *   KEEP_BROWSER_OPEN=1 npm run quick-start:headed   # stay on workspace
 */
test('quick to workspace: login, connect, open workspace', async ({ page }) => {
  const db = {
    host: process.env.KOTTE_DB_HOST || 'localhost',
    port: process.env.KOTTE_DB_PORT || '5455',
    database: process.env.KOTTE_DB_NAME || 'postgresDB',
    user: process.env.KOTTE_DB_USER || 'postgresUser',
    password: process.env.KOTTE_DB_PASSWORD || 'postgresPW',
  }

  await page.goto('/login')

  // Login
  await page.getByLabel(/username/i).fill('admin')
  await page.getByLabel(/password/i).fill('admin')
  await page.getByRole('button', { name: /^login$/i }).click()

  // After login we land on /workspace then get redirected to / (connection page) if not connected
  const connectionHeading = page.getByRole('heading', { name: /connect to database/i })
  const workspaceContent = page.getByText(/cypher query|query 1|graphs/i).first()
  await Promise.race([
    connectionHeading.waitFor({ state: 'visible', timeout: 20000 }),
    workspaceContent.waitFor({ state: 'visible', timeout: 20000 }),
  ])

  if (await workspaceContent.isVisible()) {
    await expect(page).toHaveURL(/\/workspace/)
    if (process.env.KEEP_BROWSER_OPEN === '1') {
      await page.waitForTimeout(3600000)
    }
    return
  }

  // Connection page: fill form (labels wrap inputs: "Host:", "Port:", etc.)
  await page.getByLabel(/host/i).fill(db.host)
  await page.getByLabel(/port/i).fill(db.port)
  await page.getByLabel(/database/i).fill(db.database)
  await page.getByLabel(/\buser\b/i).fill(db.user)
  await page.getByLabel(/password/i).fill(db.password)

  await page.getByRole('button', { name: /test connection/i }).click()

  await expect(page.getByRole('button', { name: /go to workspace/i })).toBeVisible({ timeout: 15000 })
  await page.getByRole('button', { name: /go to workspace/i }).click()

  await page.waitForURL(/\/workspace/, { timeout: 10000 })
  await expect(page.getByText(/cypher query|query 1|graphs/i).first()).toBeVisible({ timeout: 10000 })

  if (process.env.KEEP_BROWSER_OPEN === '1') {
    await page.waitForTimeout(3600000)
  }
})
