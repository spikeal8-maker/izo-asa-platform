import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/foundation', route => route.fulfill({ json: { stage: 'foundation', build_sha: 'unreleased', capabilities: [] } }))
})

test('overview has honest capabilities, no document overflow and accessible dialog', async ({ page }, info) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Ваша идея')
  await expect(page.locator('.workspace-card')).toHaveCount(5)
  await expect(page.getByRole('status')).toContainText('API отвечает')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.getByRole('button', { name: 'О состоянии' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: 'Понятно' }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  await page.screenshot({ path: info.outputPath('overview.png'), fullPage: true })
})

test('deep links, shared navigation and themes work', async ({ page }) => {
  await page.goto('/studio/video')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Видео')
  await page.getByRole('navigation').getByRole('link', { name: 'Галерея', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Галерея')
  await page.getByRole('button', { name: 'Переключить тему' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('API failure is visible and retry recovers', async ({ page }) => {
  await page.route('**/api/v1/foundation', route => route.fulfill({ status: 503, body: '{}' }))
  await page.goto('/')
  await expect(page.getByRole('status')).toContainText('API недоступен')
  await page.route('**/api/v1/foundation', route => route.fulfill({ json: { stage: 'foundation', capabilities: [] } }))
  await page.getByRole('button', { name: 'Повторить' }).click()
  await expect(page.getByRole('status')).toContainText('API отвечает')
})

for (const host of ['telegram', 'max'] as const) {
  test(`host hint ${host} reuses shell and grants no account`, async ({ page }) => {
    await page.addInitScript(kind => {
      const w = window as Window & { Telegram?: object; WebApp?: object }
      if (kind === 'telegram') w.Telegram = { WebApp: { initDataUnsafe: { user: { id: 1 } } } }
      else w.WebApp = { initData: 'untrusted-test-input' }
    }, host)
    await page.goto('/account')
    await expect(page.locator('.app')).toHaveAttribute('data-platform', host)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Аккаунт')
    await expect(page.getByText('Регистрация, вход и баланс появятся', { exact: false })).toBeVisible()
    await expect(page.locator('input[type=password]')).toHaveCount(0)
  })
}
