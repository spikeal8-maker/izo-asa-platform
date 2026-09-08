import { test, expect, type Page } from '@playwright/test'

const proof = 'a'.repeat(32) + '.' + 'B'.repeat(43)
const password = 'test-only new password 2026'
const auth = { account: { id: '00000000-0000-0000-0000-000000000011', public_code: 'testaccount000001',
  display_name: 'Проверка почты', email: 'verified@example.invalid', email_verified: false,
  state: 'active', permissions: [] }, csrf_token: 'C'.repeat(43) }

async function scaffold(page: Page, signedIn = true) {
  await page.route('**/api/v1/foundation', route => route.fulfill({ json: {
    stage: 'foundation', build_sha: 'unreleased', capabilities: [],
  } }))
  await page.route('**/api/v1/auth/me', route => route.fulfill(signedIn ? { json: auth }
    : { status: 401, json: { error: { code: 'auth_required' } } }))
}

test('AUTH-002 verification needs explicit action and strips token fragment', async ({ page }) => {
  await scaffold(page)
  let calls = 0
  await page.route('**/api/v1/auth/email/verification/confirm', async route => {
    calls++
    expect(route.request().postDataJSON()).toEqual({ token: proof })
    expect(route.request().headers()['x-csrf-token']).toBe(auth.csrf_token)
    await route.fulfill({ status: 204 })
  })
  await page.goto('/verify-email#token=' + proof)
  await expect(page.getByRole('heading', { name: 'Подтверждение почты' })).toBeVisible()
  await expect(page.getByLabel('Код из тестового письма')).toHaveValue(proof)
  await expect(page).toHaveURL(/\/verify-email$/)
  expect(calls).toBe(0)
  await page.getByRole('button', { name: 'Подтвердить адрес', exact: true }).click()
  await expect(page.getByRole('status')).toContainText('Адрес подтверждён на сервере')
  expect(calls).toBe(1)
  await expect(page.locator('meta[name="referrer"]')).toHaveAttribute('content', 'no-referrer')
})

test('AUTH-002 reset form rejects mismatched passwords then returns to login', async ({ page }) => {
  await scaffold(page, false)
  let calls = 0
  await page.route('**/api/v1/auth/password/reset', async route => {
    calls++
    expect(route.request().postDataJSON()).toEqual({ token: proof, password, confirmation: password })
    await route.fulfill({ status: 204 })
  })
  await page.goto('/password/reset#token=' + proof)
  await page.getByLabel('Новый пароль', { exact: true }).fill(password)
  await page.getByLabel('Повторите новый пароль').fill('different-long-password')
  await page.getByRole('button', { name: 'Сохранить новый пароль' }).click()
  await expect(page.getByRole('alert')).toHaveText('Пароли не совпадают.')
  expect(calls).toBe(0)
  await page.getByLabel('Повторите новый пароль').fill(password)
  await page.getByRole('button', { name: 'Сохранить новый пароль' }).click()
  await expect(page.getByRole('status')).toContainText('Все прежние сессии завершены')
  await expect(page.getByRole('link', { name: 'Войти с новым паролем' })).toHaveAttribute('href', '/login')
  expect(calls).toBe(1)
})

test('AUTH-002 forgot is neutral and invalid proof never reports success', async ({ page }) => {
  await scaffold(page, false)
  await page.route('**/api/v1/auth/password/forgot', route => route.fulfill({ status: 202,
    json: { accepted: true, delivery: 'test' } }))
  await page.goto('/password/forgot')
  await page.getByLabel('Электронная почта').fill('unknown@example.invalid')
  await page.getByRole('button', { name: 'Запросить восстановление' }).click()
  await expect(page.getByRole('status')).toContainText('Если адрес подтверждён')
  await page.route('**/api/v1/auth/password/reset', route => route.fulfill({ status: 400,
    json: { error: { code: 'invalid_challenge' } } }))
  await page.goto('/password/reset#token=' + proof)
  await page.getByLabel('Новый пароль', { exact: true }).fill(password)
  await page.getByLabel('Повторите новый пароль').fill(password)
  await page.getByRole('button', { name: 'Сохранить новый пароль' }).click()
  await expect(page.getByRole('alert')).toContainText('Ссылка недействительна')
  await expect(page.getByLabel('Новый пароль', { exact: true })).toHaveValue('')
  await expect(page.getByRole('link', { name: 'Войти с новым паролем' })).toHaveCount(0)
})

test('AUTH-002 security requires server session and current password', async ({ page }) => {
  await scaffold(page, false)
  await page.goto('/account/security')
  await expect(page.getByRole('link', { name: 'Войти в аккаунт', exact: true })).toBeVisible()
  await expect(page.getByLabel('Текущий пароль')).toHaveCount(0)
  await scaffold(page, true)
  await page.reload()
  await page.route('**/api/v1/auth/password/change', async route => {
    expect(route.request().headers()['x-csrf-token']).toBe(auth.csrf_token)
    expect(route.request().postDataJSON().current_password).toBe('test-old-password-2026')
    await route.fulfill({ status: 204 })
  })
  await page.getByLabel('Текущий пароль').fill('test-old-password-2026')
  await page.getByLabel('Новый пароль', { exact: true }).fill(password)
  await page.getByLabel('Повторите новый пароль').fill(password)
  await page.getByRole('button', { name: 'Сохранить новый пароль' }).click()
  await expect(page.getByRole('status')).toContainText('Пароль изменён')
})
