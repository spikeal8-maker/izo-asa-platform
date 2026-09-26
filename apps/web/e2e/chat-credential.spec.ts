import { test, expect, type Page } from '@playwright/test'
import { workspace } from './workspace-fixtures'

type Credential = {
  configured: boolean
  enabled: boolean
  verified: boolean
  revision: number | null
  generation: number | null
  provider: 'deepseek' | 'openrouter'
}

function empty(provider: Credential['provider']): Credential {
  return {
    configured: false, enabled: false, verified: false,
    revision: null, generation: null, provider,
  }
}

async function providerCard(page: Page, label: string) {
  return page.locator('.chat-provider-card').filter({ hasText: label })
}

test('saved DeepSeek credential remains visible when verification fails', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  let verifyFails = true
  let deepseek = empty('deepseek')
  const openrouter = empty('openrouter')

  await page.route('**/api/v1/chat/credentials**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path === '/api/v1/chat/credentials' && request.method() === 'GET') {
      return route.fulfill({ json: { credentials: [deepseek, openrouter] } })
    }
    if (path === '/api/v1/chat/credentials/deepseek' && request.method() === 'POST') {
      expect(request.headers()['x-csrf-token']).toBe('workspace-csrf')
      deepseek = {
        configured: true, enabled: true, verified: false,
        revision: 1, generation: 1, provider: 'deepseek',
      }
      return route.fulfill({ json: deepseek })
    }
    if (path === '/api/v1/chat/credentials/deepseek/verify') {
      if (verifyFails) {
        return route.fulfill({
          status: 503,
          json: { error: { code: 'provider_unavailable' } },
        })
      }
      deepseek = { ...deepseek, verified: true, revision: 2 }
      return route.fulfill({ json: deepseek })
    }
    return route.fallback()
  })

  await page.goto('/')
  await page.getByRole('button', {
    name: 'Настройки DeepSeek и OpenRouter',
  }).click()
  let card = await providerCard(page, 'DeepSeek')
  await expect(card.locator('.chat-credential-status'))
    .toContainText('Не подключён')

  await card.getByRole('button', { name: 'Добавить ключ' }).click()
  await card.getByLabel('Новый API key DeepSeek')
    .fill('synthetic-test-credential')
  await card.getByRole('button', {
    name: 'Сохранить и проверить', exact: true,
  }).click()
  await expect(card.locator('.chat-credential-status'))
    .toContainText('Проверка не пройдена')
  await expect(page.getByRole('alert'))
    .toContainText('Ключ DeepSeek сохранён. Проверка не пройдена.')

  await page.reload()
  await page.getByRole('button', {
    name: 'Настройки DeepSeek и OpenRouter',
  }).click()
  card = await providerCard(page, 'DeepSeek')
  await expect(card.locator('.chat-credential-status'))
    .toContainText('Сохранён, не проверен')

  verifyFails = false
  await card.getByRole('button', { name: 'Проверить', exact: true }).click()
  await expect(card.locator('.chat-credential-status'))
    .toContainText('Подключён')
})

test('OpenRouter model enables immediately after provider verification', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  const deepseek: Credential = {
    configured: true, enabled: true, verified: true,
    revision: 4, generation: 2, provider: 'deepseek',
  }
  let openrouter = empty('openrouter')

  await page.route('**/api/v1/chat/credentials**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path === '/api/v1/chat/credentials' && request.method() === 'GET') {
      return route.fulfill({ json: { credentials: [deepseek, openrouter] } })
    }
    if (path === '/api/v1/chat/credentials/openrouter' && request.method() === 'POST') {
      openrouter = {
        configured: true, enabled: true, verified: false,
        revision: 1, generation: 1, provider: 'openrouter',
      }
      return route.fulfill({ json: openrouter })
    }
    if (path === '/api/v1/chat/credentials/openrouter/verify') {
      openrouter = { ...openrouter, verified: true, revision: 2 }
      return route.fulfill({ json: openrouter })
    }
    return route.fallback()
  })

  await page.goto('/')
  const selector = page.getByRole('button', { name: 'Выбрать модель' })
  await selector.click()
  let menu = page.getByRole('menu', { name: 'Модели' })
  let model = menu.getByRole('menuitemradio', { name: /Автовыбор OpenRouter/ })
  await expect(model).toBeDisabled()
  await expect(model).toContainText('Подключите OpenRouter API key')
  await page.keyboard.press('Escape')

  await page.getByRole('button', {
    name: 'Настройки DeepSeek и OpenRouter',
  }).click()
  const card = await providerCard(page, 'OpenRouter')
  await card.getByRole('button', { name: 'Добавить ключ' }).click()
  await card.getByLabel('Новый API key OpenRouter')
    .fill('synthetic-openrouter-credential')
  await card.getByRole('button', {
    name: 'Сохранить и проверить', exact: true,
  }).click()
  await expect(card.locator('.chat-credential-status'))
    .toContainText('Подключён')

  await page.getByRole('button', {
    name: 'Настройки DeepSeek и OpenRouter',
  }).click()
  await selector.click()
  menu = page.getByRole('menu', { name: 'Модели' })
  model = menu.getByRole('menuitemradio', { name: /Автовыбор OpenRouter/ })
  await expect(model).toBeEnabled()
  await model.click()
  await expect(selector).toContainText('Автовыбор OpenRouter')
})
