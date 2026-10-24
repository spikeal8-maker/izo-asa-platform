import { expect, test } from '@playwright/test'
import { workspace } from './workspace-fixtures'

const noKeys = ['deepseek', 'openrouter'].map(provider => ({
  provider, configured: false, enabled: false, verified: false,
  revision: null, generation: null,
}))

test('rejects OpenRouter key in DeepSeek and DeepSeek key in OpenRouter before POST', async ({ page }) => {
  const recorded: string[] = []
  await workspace(page)
  await page.route('**/api/v1/chat/credentials', route =>
    route.fulfill({ json: { credentials: noKeys } }))
  await page.route(/\/api\/v1\/chat\/credentials\/(deepseek|openrouter)$/, route => {
    if (route.request().method() === 'POST') recorded.push(route.request().url())
    return route.fulfill({ status: 422, json: { error: { code: 'credential_provider_mismatch' } } })
  })
  await page.goto('/')
  const deepseek = page.locator('.chat-provider-card[aria-label="DeepSeek"]')
  await deepseek.getByLabel('API ключ DeepSeek').fill('sk-or-v1-' + 'a'.repeat(64))
  await expect(deepseek.getByRole('alert')).toContainText('ключ OpenRouter')
  await expect(deepseek.locator('input[type=password]')).toHaveAttribute('aria-invalid', 'true')
  await expect(deepseek.getByRole('button', { name: 'Сохранить и проверить' })).toBeDisabled()
  await deepseek.getByRole('button', { name: 'Отмена' }).click()
  const openrouter = page.locator('.chat-provider-card[aria-label="OpenRouter"]')
  await openrouter.getByRole('button', { name: 'Добавить ключ' }).click()
  await openrouter.getByLabel('Новый API key OpenRouter').fill('sk-' + 'b'.repeat(32))
  await expect(openrouter.getByRole('alert')).toContainText('ключ формата DeepSeek')
  await expect(openrouter.getByRole('button', { name: 'Сохранить и проверить' })).toBeDisabled()
  await openrouter.getByLabel('Новый API key OpenRouter').fill('sk-or-v1-' + 'b'.repeat(64))
  await expect(openrouter.getByRole('alert')).toHaveCount(0)
  await expect(openrouter.getByRole('button', { name: 'Сохранить и проверить' })).toBeEnabled()
  await openrouter.getByLabel('Новый API key OpenRouter').fill('sk-' + 'b'.repeat(32))
  await openrouter.getByRole('button', { name: 'Отмена' }).click()
  await expect(openrouter.getByLabel('Новый API key OpenRouter')).toHaveCount(0)
  expect(recorded).toHaveLength(0)
})

test('server rejected provider mismatch has a clear localized error', async ({ page }) => {
  await workspace(page)
  await page.route('**/api/v1/chat/credentials', route =>
    route.fulfill({ json: { credentials: noKeys } }))
  await page.route('**/api/v1/chat/credentials/deepseek', route =>
    route.fulfill({ status: 422, json: { error: { code: 'credential_provider_mismatch' } } }))
  await page.goto('/')
  const card = page.locator('.chat-provider-card[aria-label="DeepSeek"]')
  await card.getByLabel('API ключ DeepSeek').fill('opaque-provider-key')
  await card.getByRole('button', { name: 'Сохранить и проверить' }).click()
  await expect(page.getByRole('alert')).toContainText('нельзя сохранить как DeepSeek')
  await expect(card.locator('.chat-credential-status')).toHaveText('Не подключён')
})

test('a previously saved unverified key shows corrective instructions after reload', async ({ page }) => {
  await workspace(page)
  await page.route('**/api/v1/chat/credentials', route => route.fulfill({
    json: { credentials: [
      { provider: 'deepseek', configured: true, enabled: true, verified: false, revision: 3, generation: 3 },
      { provider: 'openrouter', configured: false, enabled: false, verified: false, revision: null, generation: null },
    ] },
  }))
  await page.goto('/')
  await page.getByRole('button', { name: 'Настройки DeepSeek и OpenRouter' }).click()
  const card = page.locator('.chat-provider-card[aria-label="DeepSeek"]')
  await expect(card.locator('.chat-credential-status')).toHaveText('Сохранён, не проверен')
  await expect(card.getByRole('status')).toContainText('Ключ сохранён, но не подтверждён')
  await expect(card.getByRole('button', { name: 'Заменить ключ' })).toBeVisible()
  await page.reload()
  await page.getByRole('button', { name: 'Настройки DeepSeek и OpenRouter' }).click()
  await expect(page.locator('.chat-provider-card[aria-label="DeepSeek"]').getByRole('status'))
    .toContainText('Проверьте, что он принадлежит DeepSeek')
})

test('platform fake starts without automatic personal key prompt but keeps BYOK accessible', async ({ page }) => {
  await workspace(page)
  await page.route('**/api/v1/chat/credentials', route =>
    route.fulfill({ json: { credentials: noKeys } }))
  await page.route('**/api/v1/chat/policy', route => route.fulfill({
    json: {
      revision: 'platform-optional-byok-test', default_model: 'platform:deepseek-flash',
      models: [{ id: 'platform:deepseek-flash', label: 'Платформа · DeepSeek Flash',
        provider: 'platform', text: true, vision: false,
        description: 'Синтетический тест, не оплачиваемый DeepSeek.',
        price: { currency: 'RUB', input_kopeks_per_million: null,
          output_kopeks_per_million: null, image_kopeks_per_image: null } }],
      max_input_chars: 6000, max_output_tokens: 2048, max_attachments: 0, max_image_bytes: 0,
    },
  }))
  await page.goto('/')
  await expect(page.getByText('Свой API-ключ необязателен.', { exact: false })).toBeVisible()
  const settings = page.getByRole('button', { name: 'Настройки DeepSeek и OpenRouter' })
  await expect(settings).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByRole('dialog', { name: 'Провайдеры' })).toHaveCount(0)
  await expect(page.getByRole('textbox', { name: 'Сообщение' })).toBeVisible()
  await settings.click()
  await expect(page.getByRole('dialog', { name: 'Провайдеры' })).toBeVisible()
  await expect(page.locator('.chat-provider-card[aria-label="DeepSeek"]')
    .getByRole('button', { name: 'Добавить ключ' })).toBeVisible()
})

test('BYOK-only first run still opens existing key onboarding', async ({ page }) => {
  await workspace(page)
  await page.route('**/api/v1/chat/credentials', route =>
    route.fulfill({ json: { credentials: noKeys } }))
  await page.goto('/')
  await expect(page.getByText('Подключите и проверьте API key провайдера.')).toBeVisible()
  await expect(page.getByRole('dialog', { name: 'Провайдеры' })).toBeVisible()
  await expect(page.locator('.chat-provider-card[aria-label="DeepSeek"]')
    .getByLabel('API ключ DeepSeek')).toBeVisible()
})

test('credential refresh arriving before platform policy never forces personal key onboarding', async ({ page }) => {
  await workspace(page)
  let releasePolicy = () => {}
  const policyGate = new Promise<void>(resolve => { releasePolicy = resolve })
  let credentialReads = 0
  await page.route('**/api/v1/chat/credentials', route => {
    credentialReads++
    return route.fulfill({ json: { credentials: noKeys } })
  })
  await page.route('**/api/v1/chat/policy', async route => {
    await policyGate
    return route.fulfill({ json: {
      revision: 'delayed-platform-policy', default_model: 'platform:deepseek-flash',
      models: [{ id: 'platform:deepseek-flash', label: 'Платформа · DeepSeek Flash',
        provider: 'platform', text: true, vision: false,
        description: 'Бесплатный синтетический тест.',
        price: { currency: 'RUB', input_kopeks_per_million: null,
          output_kopeks_per_million: null, image_kopeks_per_image: null } }],
      max_input_chars: 6000, max_output_tokens: 2048, max_attachments: 0, max_image_bytes: 0,
    } })
  })
  try {
    await page.goto('/')
    await expect(page.getByRole('button', { name: 'Настройки DeepSeek и OpenRouter' })).toBeVisible()
    await page.evaluate(() => window.dispatchEvent(new Event('focus')))
    await expect.poll(() => credentialReads).toBeGreaterThanOrEqual(2)
    await expect(page.getByRole('dialog', { name: 'Провайдеры' })).toHaveCount(0)
  } finally {
    releasePolicy()
  }
  await expect(page.getByText('Свой API-ключ необязателен.', { exact: false })).toBeVisible()
  await expect(page.getByRole('dialog', { name: 'Провайдеры' })).toHaveCount(0)
  await page.getByRole('button', { name: 'Настройки DeepSeek и OpenRouter' }).click()
  await expect(page.getByRole('dialog', { name: 'Провайдеры' })).toBeVisible()
})
