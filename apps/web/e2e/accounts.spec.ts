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
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Чем я могу помочь?')
  await expect(page.getByRole('textbox', { name: 'Сообщение' })).toBeVisible()
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
  await expect(page.getByRole('alert')).toContainText('\u041d\u0435\u0432\u0435\u0440\u043d\u0430\u044f \u043f\u043e\u0447\u0442\u0430 \u0438\u043b\u0438 \u043f\u0430\u0440\u043e\u043b\u044c.')
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


test('AUTH-UNBLOCK-001 guest probe failure does not block public registration', async ({ page }) => {
  let registerCalls = 0, claimCalls = 0
  await page.route('**/api/v1/auth/me', route => route.fulfill(
    { status: 401, json: { error: { code: 'auth_required' } } }))
  await page.route('**/api/v1/guest/me', route => route.fulfill(
    { status: 503, json: { error: { code: 'guest_trial_unavailable' } } }))
  await page.route('**/api/v1/auth/register', route => {
    registerCalls++
    return route.fulfill({ status: 201, json: view })
  })
  await page.route('**/api/v1/guest/claim', route => {
    claimCalls++
    return route.fulfill({ status: 500, json: { error: { code: 'unexpected' } } })
  })
  await page.goto('/register')
  await expect(page.locator('form.account-form')).toBeVisible()
  await expect(page.locator('body')).not.toContainText('\u0417\u0430\u043f\u0440\u043e\u0441 \u043e\u0442\u043a\u043b\u043e\u043d\u0451\u043d \u0441\u0435\u0440\u0432\u0435\u0440\u043e\u043c.')
  await page.locator('input[name="display_name"]').fill('Test User')
  await page.locator('input[name="email"]').fill('test@example.invalid')
  await page.locator('input[name="password"]').fill('12345678')
  await page.locator('form.account-form button[type="submit"]').click()
  await expect(page).toHaveURL(/\/$/)
  expect(registerCalls).toBe(1)
  expect(claimCalls).toBe(0)
})

test('AUTH-UNBLOCK-001 unknown registration failure stays inside form with safe text', async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill(
    { status: 401, json: { error: { code: 'auth_required' } } }))
  await page.route('**/api/v1/guest/me', route => route.fulfill(
    { status: 503, json: { error: { code: 'guest_trial_unavailable' } } }))
  await page.route('**/api/v1/auth/register', route => route.fulfill(
    { status: 500, json: { error: { code: 'internal_error' } } }))
  await page.goto('/register')
  await page.locator('input[name="display_name"]').fill('Test User')
  await page.locator('input[name="email"]').fill('test@example.invalid')
  await page.locator('input[name="password"]').fill('12345678')
  await page.locator('form.account-form button[type="submit"]').click()
  await expect(page.locator('form.account-form').getByRole('alert')).toContainText(
    '\u041d\u0435 \u0443\u0434\u0430\u043b\u043e\u0441\u044c \u0441\u043e\u0437\u0434\u0430\u0442\u044c \u0430\u043a\u043a\u0430\u0443\u043d\u0442. \u041f\u043e\u0432\u0442\u043e\u0440\u0438\u0442\u0435 \u043f\u043e\u043f\u044b\u0442\u043a\u0443.')
  await expect(page.locator('body')).not.toContainText('\u0417\u0430\u043f\u0440\u043e\u0441 \u043e\u0442\u043a\u043b\u043e\u043d\u0451\u043d \u0441\u0435\u0440\u0432\u0435\u0440\u043e\u043c.')
})
