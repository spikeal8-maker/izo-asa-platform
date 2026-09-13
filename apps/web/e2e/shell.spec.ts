import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ status: 401, json: { error: { code: 'auth_required' } } }))
})

test('feed-first shell is product-facing and overflow-free', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Создавайте, смотрите и развивайте идеи')
  await expect(page.locator('.feed-card')).toHaveCount(6)
  await expect(page.getByText('ТЕСТОВАЯ ПЛАТФОРМА')).toHaveCount(0)
  await expect(page.getByText(/Одно место\.\s*Много возможностей/i)).toHaveCount(0)
  if ((page.viewportSize()?.width ?? 9999) <= 820) {
    await page.getByRole('button', { name: 'Меню', exact: true }).click()
    const menu = page.getByRole('dialog', { name: 'Меню' })
    await expect(menu.getByRole('link', { name: 'Войти', exact: true })).toBeVisible()
    await expect(menu.getByRole('link', { name: 'Создать аккаунт', exact: true })).toBeVisible()
  } else {
    await expect(page.getByRole('link', { name: 'Войти', exact: true })).toBeVisible()
    await expect(page.getByRole('link', { name: 'Регистрация', exact: true })).toBeVisible()
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('primary navigation and themes work', async ({ page }) => {
  await page.goto('/studio/video')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Видео')
  await expect(page.getByText('В разработке')).toHaveCount(0)
  await page.getByRole('navigation', { name: 'Основные разделы' }).getByRole('link', { name: 'Галерея', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Галерея')
  await page.getByRole('button', { name: 'Переключить тему' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('jobs are not primary navigation while deep link remains available', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('navigation', { name: 'Основные разделы' }).getByRole('link', { name: 'Задания' })).toHaveCount(0)
  await page.goto('/jobs')
  await expect(page.locator('main')).toBeVisible()
})

test('mobile has top menu plus short bottom navigation', async ({ page }, info) => {
  test.skip(!info.project.name.startsWith('phone'))
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Меню', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Меню', exact: true }).click()
  await expect(page.getByRole('dialog', { name: 'Меню' })).toBeVisible()
  await expect(page.getByRole('dialog', { name: 'Меню' }).getByRole('link', { name: 'Чат' })).toBeVisible()
  const primary = page.getByRole('navigation', { name: 'Основные разделы' })
  await expect(primary.getByRole('link')).toHaveCount(3)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('8K shell uses wide canvas without stretching reading text', async ({ page }, info) => {
  test.skip(info.project.name !== 'eight-k')
  await page.goto('/')
  const grid = page.locator('.feed-grid')
  const columns = await grid.evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length)
  expect(columns).toBeGreaterThanOrEqual(8)
  expect((await grid.boundingBox())?.width ?? 0).toBeGreaterThan(4000)
  expect((await page.locator('.feed-hero-copy').boundingBox())?.width ?? 9999).toBeLessThan(1000)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

for (const host of ['telegram', 'max'] as const) {
  test(`host hint ${host} reuses shell and grants no account`, async ({ page }) => {
    await page.addInitScript(kind => {
      const w = window as Window & { Telegram?: object; WebApp?: object }
      if (kind === 'telegram') w.Telegram = { WebApp: { initDataUnsafe: { user: { id: 1 } } } }
      else w.WebApp = { initData: 'untrusted-test-input' }
    }, host)
    await page.goto('/login')
    await expect(page.locator('.app')).toHaveAttribute('data-platform', host)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Войти')
    await expect(page.getByRole('button', { name: 'Войти', exact: true })).toBeVisible()
    await expect(page.getByTestId('server-account')).toHaveCount(0)
  })
}
