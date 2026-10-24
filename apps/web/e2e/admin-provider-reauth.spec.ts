import { expect, test } from '@playwright/test'

const user = {
  id: '9d9d9d9d-5555-4555-9555-555555555555',
  public_code: 'testadmin00000001',
  display_name: 'Тестовый главный администратор',
  state: 'active',
  email: 'staff@example.invalid',
  email_verified: false,
  permissions: ['users.read_limited', 'connections.read', 'connections.write', 'secrets.bind'],
}
const csrf = 'synthetic-csrf-only'
type Model = 'deepseek-flash' | 'deepseek-v4-pro'
type Connection = {
  provider: 'deepseek'
  configured: boolean
  enabled: boolean
  verified: boolean
  status: 'not_configured' | 'not_verified' | 'disabled' | 'verified'
  model: Model
  revision: number | null
  generation: number | null
  daily_limit: number
  concurrency_limit: number
  available_to_users: boolean
}
const initial = (): Connection => ({
  provider: 'deepseek',
  configured: false,
  enabled: false,
  verified: false,
  status: 'not_configured',
  model: 'deepseek-flash',
  revision: null,
  generation: null,
  daily_limit: 30,
  concurrency_limit: 1,
  available_to_users: false,
})
const password = 'synthetic-admin-login-password'
const fakeKey = 'test-only-deepseek-api-key-value'

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/foundation', route => route.fulfill({
    json: { stage: 'foundation', build_sha: 'test-only', capabilities: [] },
  }))
  await page.route('**/api/v1/auth/me', route => route.fulfill({
    json: { account: user, csrf_token: csrf },
  }))
  await page.route('**/api/v1/admin/me', route => route.fulfill({
    json: { permissions: user.permissions, max_grant: 0, csrf_token: csrf },
  }))
})

test('P0 reauth: save requests password visibly and never sends without it', async ({ page }) => {
  let provider = initial()
  const captured: Record<string, unknown>[] = []
  await page.route('**/api/v1/admin/providers', route =>
    route.fulfill({ json: { connections: [provider] } }))
  await page.route('**/api/v1/admin/providers/deepseek/credential', route => {
    const body = route.request().postDataJSON()
    captured.push(body)
    expect(route.request().headers()['x-csrf-token']).toBe(csrf)
    expect(body.current_password).toBe(password)
    expect(body.key).toBe(fakeKey)
    provider = { ...provider, configured: true, revision: 1, generation: 1,
      status: 'not_verified', verified: false, enabled: false }
    return route.fulfill({ json: provider })
  })

  await page.goto('/admin/providers')
  await expect(page.getByRole('heading', { name: 'Подтверждение действий' })).toBeVisible()
  await expect(page.getByText('Это не API-ключ.')).toBeVisible()
  const confirmation = page.getByLabel('Текущий пароль аккаунта IZO ASA')
  const apiKey = page.getByLabel('Новый API-ключ')
  await expect(confirmation).toBeVisible()
  await apiKey.fill(fakeKey)
  const save = page.getByRole('button', { name: 'Сохранить ключ на сервере' })
  await expect(save).toBeEnabled()
  await save.click()

  await expect(page.getByRole('alert')).toContainText('введите текущий пароль вашего аккаунта IZO ASA')
  await expect(confirmation).toBeFocused()
  await expect(apiKey).toHaveValue(fakeKey)
  expect(captured).toHaveLength(0)

  await confirmation.fill(password)
  await save.click()
  await expect(page.getByRole('status')).toContainText('Новый ключ зашифрован на сервере')
  await expect(confirmation).toHaveValue('')
  await expect(apiKey).toHaveValue('')
  expect(captured).toHaveLength(1)
  await expect(page.getByText('Сохранён на сервере')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Проверить подключение' })).toBeEnabled()
})

test('P0 reauth: verify and policy show feedback and require password on every attempt', async ({ page }) => {
  let provider: Connection = { ...initial(), configured: true, enabled: false,
    verified: false, status: 'not_verified', revision: 4, generation: 2 }
  let verifiedCalls = 0
  let policyCalls = 0
  await page.route('**/api/v1/admin/providers', route =>
    route.fulfill({ json: { connections: [provider] } }))
  await page.route('**/api/v1/admin/providers/deepseek/verify', route => {
    const body = route.request().postDataJSON()
    expect(body.current_password).toBe(password)
    expect(body.expected_revision).toBe(4)
    verifiedCalls++
    provider = { ...provider, verified: true, revision: 5, status: 'disabled' }
    return route.fulfill({ json: provider })
  })
  await page.route('**/api/v1/admin/providers/deepseek/config', route => {
    const body = route.request().postDataJSON()
    expect(body.current_password).toBe(password)
    expect(body.model).toBe('deepseek-v4-pro')
    expect(body.enabled).toBe(true)
    expect(body.daily_limit).toBe(8)
    expect(body.concurrency_limit).toBe(2)
    expect(body.expected_revision).toBe(5)
    policyCalls++
    provider = { ...provider, model: 'deepseek-v4-pro', enabled: true,
      status: 'verified', revision: 6, daily_limit: 8, concurrency_limit: 2 }
    return route.fulfill({ json: provider })
  })
  await page.goto('/admin/providers')
  const confirmation = page.getByLabel('Текущий пароль аккаунта IZO ASA')
  const verify = page.getByRole('button', { name: 'Проверить подключение' })
  await expect(verify).toBeEnabled()
  await verify.click()
  await expect(confirmation).toBeFocused()
  await expect(page.getByRole('alert')).toContainText('Для сохранения ключа')
  expect(verifiedCalls).toBe(0)
  await confirmation.fill(password)
  await verify.click()
  await expect(page.getByRole('status')).toContainText('Сервер подтвердил проверку')
  expect(verifiedCalls).toBe(1)
  await expect(confirmation).toHaveValue('')

  await page.locator('.provider-form select').selectOption('deepseek-v4-pro')
  await page.getByLabel('Лимит запросов в сутки').fill('8')
  await page.getByLabel('Максимум одновременных запросов').fill('2')
  await page.getByLabel('Разрешить подключение в настройках').check()
  const saveSettings = page.getByRole('button', { name: 'Сохранить настройки' })
  await saveSettings.click()
  await expect(confirmation).toBeFocused()
  expect(policyCalls).toBe(0)
  await confirmation.fill(password)
  await saveSettings.click()
  await expect(page.getByRole('status')).toContainText('Настройки сохранены в PostgreSQL')
  await expect(confirmation).toHaveValue('')
  expect(policyCalls).toBe(1)
})

test('P0 reauth: missing connection explains disabled verify and fits narrow viewport', async ({ page }) => {
  await page.route('**/api/v1/admin/providers', route =>
    route.fulfill({ json: { connections: [initial()] } }))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/admin/providers')
  const confirmation = page.getByLabel('Текущий пароль аккаунта IZO ASA')
  const save = page.getByRole('button', { name: 'Сохранить ключ на сервере' })
  await expect(confirmation).toBeVisible()
  await expect(save).toBeDisabled()
  await page.getByLabel('Новый API-ключ').fill(fakeKey)
  await expect(save).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Проверить подключение' })).toBeDisabled()
  await expect(page.getByText('Проверка станет доступна после сохранения API-ключа.')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('P0 reauth: invalid password is reported, never cached, and key stays editable', async ({ page }) => {
  let calls = 0
  await page.route('**/api/v1/admin/providers', route =>
    route.fulfill({ json: { connections: [initial()] } }))
  await page.route('**/api/v1/admin/providers/deepseek/credential', route => {
    calls++
    return route.fulfill({ status: 403, json: { error: { code: 'reauth_required' } } })
  })
  await page.goto('/admin/providers')
  const confirmation = page.getByLabel('Текущий пароль аккаунта IZO ASA')
  const key = page.getByLabel('Новый API-ключ')
  await key.fill(fakeKey)
  await confirmation.fill('wrong-test-password')
  await page.getByRole('button', { name: 'Сохранить ключ на сервере' }).click()
  await expect(page.getByRole('alert')).toContainText('Неверный текущий пароль администратора.')
  await expect(confirmation).toHaveValue('')
  await expect(key).toHaveValue(fakeKey)
  expect(calls).toBe(1)
})

test('P0 admin reauthentication uses semantic tokens in light and dark', async ({ page }) => {
  await page.route('**/api/v1/admin/providers', route =>
    route.fulfill({ json: { connections: [initial()] } }))
  await page.goto('/admin/providers')
  const passwordInput = page.getByLabel('Текущий пароль аккаунта IZO ASA')
  await expect(passwordInput).toBeVisible()
  for (const theme of ['light', 'dark'] as const) {
    await page.evaluate(value => { document.documentElement.dataset.theme = value }, theme)
    await passwordInput.focus()
    const colors = await passwordInput.evaluate(element => {
      const panel = element.closest('.provider-auth-top')
      if (!panel) throw new Error('Missing protected confirmation panel')
      const sample = document.createElement('span')
      sample.style.cssText = [
        'background:var(--color-surface)',
        'color:var(--color-text)',
        'border:1px solid var(--color-border)',
        'border-left-color:var(--color-brand)',
        'outline:3px solid color-mix(in srgb, var(--color-brand) 78%, var(--color-surface))',
      ].join(';')
      panel.appendChild(sample)
      const expected = getComputedStyle(sample)
      const container = getComputedStyle(panel)
      const input = getComputedStyle(element)
      const result = {
        background: container.backgroundColor, expectedBackground: expected.backgroundColor,
        accent: container.borderLeftColor, expectedAccent: expected.borderLeftColor,
        inputBackground: input.backgroundColor, expectedInputBackground: expected.backgroundColor,
        inputColor: input.color, expectedInputColor: expected.color,
        inputBorder: input.borderTopColor, expectedInputBorder: expected.borderTopColor,
        focusOutline: input.outlineColor, expectedFocusOutline: expected.outlineColor,
      }
      sample.remove()
      return result
    })
    expect(colors.background).toBe(colors.expectedBackground)
    expect(colors.accent).toBe(colors.expectedAccent)
    expect(colors.inputBackground).toBe(colors.expectedInputBackground)
    expect(colors.inputColor).toBe(colors.expectedInputColor)
    expect(colors.inputBorder).toBe(colors.expectedInputBorder)
    expect(colors.focusOutline).toBe(colors.expectedFocusOutline)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  }
})
