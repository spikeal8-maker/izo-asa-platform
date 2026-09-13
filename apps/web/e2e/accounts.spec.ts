import { test, expect } from '@playwright/test'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/foundation', route => route.fulfill({ json: { stage: 'foundation', capabilities: [] } }))
})
const account = { id: '11111111-1111-4111-8111-111111111111', public_code: 'test-account-code',
  display_name: 'Тестовый аккаунт', email: 'test@example.invalid', email_verified: false, state: 'active', permissions: [] }
const view = { account, csrf_token: 'a'.repeat(43) }

test('login uses server result and returns to product', async ({ page }) => {
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
  await page.getByLabel('Пароль', { exact: true }).fill('simple-passphrase')
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page).toHaveURL(/\/$/)
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Создавайте')
  const storage = await page.evaluate(() => JSON.stringify(localStorage) + JSON.stringify(sessionStorage))
  expect(storage).not.toContain('csrf_token')
  expect(storage).not.toContain('simple-passphrase')
})

test('rejection stays signed out', async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ status: 401, json: { error: { code: 'auth_required' } } }))
  await page.route('**/api/v1/auth/login', route => route.fulfill({ status: 401, json: { error: { code: 'invalid_credentials' } } }))
  await page.goto('/login')
  await page.getByLabel('Электронная почта').fill('test@example.invalid')
  await page.getByLabel('Пароль', { exact: true }).fill('wrong-password')
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Не удалось войти')
  await expect(page.getByLabel('Пароль', { exact: true })).toHaveValue('')
})

test('public signup requires no invitation and accepts eight-character password', async ({ page }) => {
  let registered = false
  await page.route('**/api/v1/auth/me', route => route.fulfill(registered
    ? { json: view } : { status: 401, json: { error: { code: 'auth_required' } } }))
  await page.route('**/api/v1/auth/register', async route => {
    const data = route.request().postDataJSON()
    expect(Object.keys(data).sort()).toEqual(['display_name', 'email', 'password'])
    expect(data.password).toBe('12345678')
    registered = true
    await route.fulfill({ status: 201, json: view })
  })
  await page.goto('/register')
  await expect(page.getByText(/приглашен/i)).toHaveCount(0)
  await page.getByLabel('Имя', { exact: true }).fill('Тест')
  await page.getByLabel('Электронная почта').fill('test@example.invalid')
  await page.getByLabel('Пароль', { exact: true }).fill('12345678')
  await page.getByRole('button', { name: 'Создать аккаунт' }).click()
  await expect(page).toHaveURL(/\/$/)
})
