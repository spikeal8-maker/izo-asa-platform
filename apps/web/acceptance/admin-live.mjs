// Real browser -> built web/Caddy -> FastAPI -> PostgreSQL, no mocked API responses.
// Input is an ephemeral synthetic fixture in protected RUNNER_TEMP, never an artifact.
import { readFile, mkdir } from 'node:fs/promises'
import { chromium, expect } from '@playwright/test'

if (process.env.IZO_ENVIRONMENT !== 'test' || process.env.IZO_ADMIN_ACCEPTANCE !== 'isolated')
  throw new Error('Explicit isolated stack required')
const state = JSON.parse(await readFile(process.argv[2], 'utf8'))
const browser = await chromium.launch()
const origin = 'http://localhost:8080'
const evidence = 'apps/web/test-results/admin-live'
await mkdir(evidence, { recursive: true })
async function context() {
  const c = await browser.newContext({ baseURL: origin, viewport: { width: 1440, height: 900 } })
  await c.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort())
  return c
}
async function login(page, user) {
  await page.goto('/login')
  await page.getByLabel('Электронная почта').fill(user.email)
  await page.getByLabel('Пароль', { exact: true }).fill(user.password)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await page.waitForURL('**/account')
  await expect(page.getByTestId('server-account')).toBeVisible()
}
try {
  const c = await context(), page = await c.newPage()
  await login(page, state.live_operator)
  await page.goto('/admin/users')
  await page.getByLabel('Имя или публичный код').fill(state.live_recipient.public_code)
  await page.getByRole('button', { name: 'Найти пользователя' }).click()
  await page.getByRole('link', { name: 'Открыть карточку' }).click()
  await expect(page.getByTestId('admin-available')).toHaveText('0')
  await page.getByLabel('Номер заявки').fill(state.live_case)
  await page.getByLabel('Количество баллов').fill('40')
  await page.getByRole('button', { name: 'Проверить начисление' }).click()
  const dialog = page.getByRole('dialog', { name: 'Подтверждение компенсации' })
  await dialog.getByLabel('Текущий пароль администратора').fill(state.live_operator.password)
  await dialog.getByRole('button', { name: 'Подтвердить начисление' }).click()
  await expect(page.locator('.admin-receipt')).toContainText('Начислено 40 баллов')
  await expect(page.getByTestId('admin-available')).toHaveText('40')
  await page.reload()
  await expect(page.getByTestId('admin-available')).toHaveText('40')
  await page.screenshot({ path: evidence + '/admin-real-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  await page.screenshot({ path: evidence + '/admin-real-phone.png', fullPage: true })
  await c.close()
  const u = await context(), userPage = await u.newPage()
  await login(userPage, state.live_recipient)
  await userPage.goto('/account/credits')
  await expect(userPage.getByTestId('own-available')).toHaveText('40')
  await userPage.reload()
  await expect(userPage.getByTestId('own-available')).toHaveText('40')
  await userPage.screenshot({ path: evidence + '/credits-real-desktop.png', fullPage: true })
  await userPage.goto('/admin/users/' + state.live_operator.id)
  await expect(userPage.locator('.admin-page').getByRole('alert')).toContainText('Нет необходимого')
  await expect(userPage.getByTestId('admin-available')).toHaveCount(0)
  await u.close()
  console.log('ADMIN_BROWSER_OK: real login -> search -> confirmed grant -> reload -> own balance; ordinary user denied')
} finally {
  await browser.close()
}
