import { expect, test } from '@playwright/test'
import { noOverflow, workspace } from './workspace-fixtures'

const price = { currency: 'RUB', input_kopeks_per_million: null,
  output_kopeks_per_million: null, image_kopeks_per_image: null }
const byok = { id: 'deepseek-flash', label: 'DeepSeek Flash', provider: 'deepseek',
  text: true, vision: false, price }
const offered = { id: 'platform:deepseek-flash', label: 'Платформа · DeepSeek Flash',
  provider: 'platform', text: true, vision: false,
  description: 'Бесплатный синтетический тест. Не реальный DeepSeek.', price }

test('platform fake model is selectable without BYOK and disabled disappears after refresh', async ({ page }) => {
  await workspace(page)
  let enabled = true
  await page.route('**/api/v1/chat/credentials', route => route.fulfill({
    json: { credentials: ['deepseek', 'openrouter'].map(provider => ({
      configured: false, enabled: false, verified: false,
      revision: null, generation: null, provider,
    })) },
  }))
  await page.route('**/api/v1/chat/policy', route => route.fulfill({
    json: { revision: enabled ? 'isolated-platform-on' : 'isolated-platform-off',
      default_model: enabled ? offered.id : byok.id,
      models: enabled ? [byok, offered] : [byok],
      max_input_chars: 6000, max_output_tokens: 2048,
      max_attachments: 0, max_image_bytes: 0 },
  }))
  await page.goto('/')
  await expect(page.getByText('Свой API-ключ необязателен.', { exact: false })).toBeVisible()
  await page.getByRole('textbox', { name: 'Сообщение' }).fill('Проверка платформенной модели')
  await expect(page.getByRole('button', { name: 'Отправить' })).toBeEnabled()
  await page.getByRole('button', { name: 'Выбрать модель' }).click()
  await page.getByRole('menuitem', { name: /Текст/ }).click()
  const option = page.locator('.chat-model-row').getByRole('menuitemradio', { name: /Платформа · DeepSeek Flash/ })
  await expect(option).toBeVisible()
  await expect(option).toBeEnabled()
  await option.click()
  await expect(page.getByRole('button', { name: 'Выбрать модель' })).toContainText('Платформа')
  await noOverflow(page)
  enabled = false
  await page.reload()
  await expect(page.getByText('Подключите и проверьте API key провайдера.')).toBeVisible()
  await page.getByRole('button', { name: 'Выбрать модель' }).click()
  await page.getByRole('menuitem', { name: /Текст/ }).click()
  await expect(page.locator('.chat-model-row').getByRole('menuitemradio', { name: /Платформа · DeepSeek Flash/ })).toHaveCount(0)
  await noOverflow(page)
})

test('isolated fake mode is labelled as demo, never presented as paid provider', async ({ page }) => {
  await workspace(page)
  await page.route('**/api/v1/chat/policy', route => route.fulfill({
    json: { revision: 'isolated-platform-on', default_model: offered.id,
      models: [byok, offered], max_input_chars: 6000,
      max_output_tokens: 2048, max_attachments: 0, max_image_bytes: 0 },
  }))
  await page.route('**/api/v1/chat/credentials', route => route.fulfill({
    json: { credentials: [{ provider: 'deepseek', configured: false,
      verified: false, enabled: false, generation: null, revision: null }] },
  }))
  await page.goto('/')
  await page.getByRole('button', { name: 'Выбрать модель' }).click()
  await page.getByRole('menuitem', { name: /Текст/ }).click()
  await expect(page.getByText('Бесплатный синтетический тест. Не реальный DeepSeek.')).toBeVisible()
  await noOverflow(page)
})
