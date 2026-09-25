import { test, expect } from '@playwright/test'
import { workspace } from './workspace-fixtures'

test('saved DeepSeek credential remains visible when verification fails', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  let verifyFails = true
  let credential = {
    configured: false,
    enabled: false,
    verified: false,
    revision: null as number | null,
    generation: null as number | null,
    provider: 'deepseek',
  }

  await page.route('**/api/v1/chat/credential**', async route => {
    const request = route.request()
    const path = new URL(request.url()).pathname
    if (path === '/api/v1/chat/credential' && request.method() === 'GET') {
      return route.fulfill({ json: credential })
    }
    if (path === '/api/v1/chat/credential' && request.method() === 'POST') {
      expect(request.headers()['x-csrf-token']).toBe('workspace-csrf')
      credential = {
        configured: true, enabled: true, verified: false,
        revision: 1, generation: 1, provider: 'deepseek',
      }
      return route.fulfill({ json: credential })
    }
    if (path === '/api/v1/chat/credential/verify') {
      expect(request.headers()['x-csrf-token']).toBe('workspace-csrf')
      if (verifyFails) {
        return route.fulfill({
          status: 503,
          json: { error: { code: 'provider_unavailable' } },
        })
      }
      credential = {
        ...credential, verified: true, revision: 2,
      }
      return route.fulfill({ json: credential })
    }
    return route.fallback()
  })

  await page.goto('/')
  const settings = page.getByRole('button', { name: 'Настройки DeepSeek' })
  await settings.click()
  await expect(page.locator('.chat-credential-status'))
    .toContainText('Статус: не подключён')

  await page.getByLabel('Новый API key').fill('synthetic-test-credential')
  await page.getByRole('button', { name: 'Сохранить и проверить' }).click()
  await expect(page.locator('.chat-credential-status'))
    .toContainText('Статус: проверка не пройдена')
  await expect(page.getByRole('alert'))
    .toContainText('Ключ сохранён. Проверка не пройдена. DeepSeek сейчас недоступен.')

  await page.reload()
  await page.getByRole('button', { name: 'Настройки DeepSeek' }).click()
  await expect(page.locator('.chat-credential-status'))
    .toContainText('Статус: сохранён, не проверен')

  verifyFails = false
  await page.getByRole('button', { name: 'Проверить' }).click()
  await expect(page.locator('.chat-credential-status'))
    .toContainText('Статус: подключён')
})
