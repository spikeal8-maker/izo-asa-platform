import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/foundation', route => route.fulfill({ json: { stage: 'foundation', capabilities: [] } }))
})
const account = { id: '11111111-1111-4111-8111-111111111111', public_code: 'test-account-code',
  display_name: 'Тестовый аккаунт', email: 'test@example.invalid', email_verified: false, state: 'active', permissions: [] }
const view = { account, csrf_token: 'a'.repeat(43) }

test('AUTH-001 login uses server result and restores account after navigation', async ({ page }) => {
  let authenticated = false
  await page.route('**/api/v1/auth/me', route => route.fulfill(authenticated
    ? { json: view } : { status: 401, json: { error: { code: 'auth_required' } } }))
  await page.route('**/api/v1/auth/sessions', route => route.fulfill({ json: { sessions: [] } }))
  await page.route('**/api/v1/auth/login', async route => {
    expect(route.request().postDataJSON().email).toBe('test@example.invalid')
    expect(route.request().headers()['x-izo-request']).toBe('web')
    authenticated = true
    await route.fulfill({ json: view })
  })
  await page.goto('/login')
  await page.getByLabel('Электронная почта').fill('test@example.invalid')
  await page.getByLabel('Пароль', { exact: true }).fill('test-only password longer than15')
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/account$/)
  await expect(page.getByTestId('server-account')).toContainText('Тестовый аккаунт')
  await page.reload()
  await expect(page.getByTestId('server-account')).toBeVisible()
  const storage = await page.evaluate(() => JSON.stringify(localStorage) + JSON.stringify(sessionStorage))
  expect(storage).not.toContain('csrf_token')
  expect(storage).not.toContain('test-only password')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('AUTH-001 rejection stays signed out and never enables platform hints', async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ status: 401, json: { error: { code: 'auth_required' } } }))
  await page.route('**/api/v1/auth/login', route => route.fulfill({ status: 401, json: { error: { code: 'invalid_credentials' } } }))
  await page.goto('/account')
  await page.getByLabel('Электронная почта').fill('test@example.invalid')
  await page.getByLabel('Пароль', { exact: true }).fill('wrong-password')
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Не удалось войти')
  await expect(page.getByLabel('Пароль', { exact: true })).toHaveValue('')
  await expect(page.getByTestId('server-account')).toHaveCount(0)
})

test('AUTH-001 signup sends one-use invitation but never requested privileges', async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ status: 401, json: { error: { code: 'auth_required' } } }))
  await page.route('**/api/v1/auth/register', async route => {
    const data = route.request().postDataJSON()
    expect(Object.keys(data).sort()).toEqual(['display_name', 'email', 'invite_code', 'password'])
    expect(data.invite_code).toBe('a'.repeat(43))
    await route.fulfill({ status: 400, json: { error: { code: 'registration_rejected' } } })
  })
  await page.goto('/register')
  await page.getByLabel('Имя', { exact: true }).fill('Тест')
  await page.getByLabel('Электронная почта').fill('test@example.invalid')
  await page.getByLabel('Пароль', { exact: true }).fill('test-only long password15')
  await page.getByLabel('Одноразовое приглашение').fill('a'.repeat(43))
  await page.getByRole('button', { name: 'Создать аккаунт' }).click()
  await expect(page.getByRole('alert')).toContainText('Регистрация не выполнена')
})
