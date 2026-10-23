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
