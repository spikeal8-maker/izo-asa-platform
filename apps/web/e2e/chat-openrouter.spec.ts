import { expect, test, type Page } from '@playwright/test'
import { ApiError, chatProblem, chatProviderProblem } from '../src/shared/api'
import { workspace } from './workspace-fixtures'

const catalog = { stale: false, fetched_at: 100, models: [{
  id: 'anthropic/claude-test', name: 'Claude Test', provider: 'anthropic',
  context_length: 200000, vision: true,
  input_per_million_usd: null, output_per_million_usd: null,
}] }

async function openTextModels(page: Page) {
  await page.getByRole('button', { name: 'Выбрать модель' }).click()
  const menu = page.getByRole('menu', { name: 'Модели' })
  await menu.locator('.chat-model-category summary').click()
  return menu
}

test('first-run DeepSeek key entry receives focus and can be dismissed', async ({ page }) => {
  await workspace(page)
  await page.route('**/api/v1/chat/credentials', route => route.fulfill({ json: { credentials: [
    { provider: 'deepseek', configured: false, enabled: false, verified: false, revision: null, generation: null },
    { provider: 'openrouter', configured: false, enabled: false, verified: false, revision: null, generation: null },
  ] } }))
  await page.goto('/')
  const key = page.getByLabel('API ключ DeepSeek', { exact: true })
  await expect(key).toBeFocused()
  await page.getByRole('button', { name: 'Отмена' }).click()
  await expect(key).toHaveCount(0)
  const add = page.locator('.chat-provider-card').filter({ hasText: 'DeepSeek' })
    .getByRole('button', { name: 'Добавить ключ' })
  await expect(add).toBeFocused()
  await add.click()
  await expect(key).toBeFocused()
  await page.keyboard.press('Escape')
  const toggle = page.getByRole('button', { name: 'Настройки DeepSeek и OpenRouter' })
  await expect(toggle).toBeFocused()
  await toggle.click()
  await expect(key).toBeFocused()
})

test('provider settings verify OpenRouter key and unlock its models', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  let openrouter = { provider: 'openrouter', configured: false, enabled: false,
    verified: false, revision: null as number | null, generation: null as number | null }
  await page.route('**/api/v1/chat/catalog/openrouter', route => route.fulfill({ json: catalog }))
  await page.route('**/api/v1/chat/credentials**', route => {
    const path = new URL(route.request().url()).pathname
    if (path === '/api/v1/chat/credentials') return route.fulfill({ json: { credentials: [
      { provider: 'deepseek', configured: true, enabled: true, verified: true, revision: 1, generation: 1 },
      openrouter,
    ] } })
    if (path === '/api/v1/chat/credentials/openrouter' && route.request().method() === 'POST') {
      expect(route.request().postDataJSON()).toMatchObject({ key: 'synthetic-openrouter-key' })
      openrouter = { ...openrouter, configured: true, enabled: true, revision: 1, generation: 1 }
      return route.fulfill({ json: openrouter })
    }
    if (path === '/api/v1/chat/credentials/openrouter/verify') {
      openrouter = { ...openrouter, verified: true, revision: 2 }
      return route.fulfill({ json: openrouter })
    }
    return route.fallback()
  })
  await page.goto('/')
  let menu = await openTextModels(page)
  await expect(menu.getByRole('menuitemradio', { name: /Claude Test/ })).toBeDisabled()
  await expect(menu.getByRole('menuitemradio', { name: /Claude Test/ }))
    .toContainText('Цена не задана')
  await expect(menu.getByRole('menuitemradio', { name: /Claude Test/ }))
    .toContainText('отправка в чате пока недоступна')
  await page.keyboard.press('Escape')

  await page.getByRole('button', { name: 'DeepSeek подключён' }).click()
  const card = page.locator('.chat-provider-card').filter({ hasText: 'OpenRouter' })
  await card.getByRole('button', { name: 'Добавить ключ' }).click()
  await card.getByLabel('Новый API key OpenRouter').fill('synthetic-openrouter-key')
  await card.getByRole('button', { name: 'Сохранить и проверить' }).click()
  await expect(card.locator('.chat-credential-status')).toContainText('Подключён')
  await expect(card.getByLabel('Новый API key OpenRouter')).toHaveCount(0)
  await page.getByRole('button', { name: 'Настройки DeepSeek и OpenRouter' }).click()

  menu = await openTextModels(page)
  const search = menu.getByLabel('Поиск модели')
  await search.fill('anthropic')
  const model = menu.getByRole('menuitemradio', { name: /Claude Test/ })
  await expect(model).toBeEnabled()
  await expect(model).toContainText('контекст 200 000')
  await model.click()
  await expect(page.getByRole('button', { name: 'Выбрать модель' })).toContainText('Claude Test')
  await expect(page.locator('.chat-sidebar-title')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Новый чат' })).toBeVisible()
  const gap = await page.evaluate(() => document.querySelector('.chat-composer-wrap')!
    .getBoundingClientRect().top - document.querySelector('.chat-start-state h1')!.getBoundingClientRect().bottom)
  expect(gap).toBeLessThanOrEqual(50)
  await page.screenshot({ path: info.outputPath('chat-openrouter-desktop.png') })
})

test('dynamic catalog change blocks request before Chat POST', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  let current = catalog, posts = 0
  await page.route('**/api/v1/chat/catalog/openrouter', route => route.fulfill({ json: current }))
  await page.route('**/api/v1/chat/credentials', route => route.fulfill({ json: { credentials: [
    { provider: 'deepseek', configured: true, enabled: true, verified: true, revision: 1, generation: 1 },
    { provider: 'openrouter', configured: true, enabled: true, verified: true, revision: 1, generation: 1 },
  ] } }))
  await page.route(/\/api\/v1\/chat\/threads(?:\/|$)/, route => {
    if (route.request().method() === 'POST') posts += 1
    return route.fallback()
  })
  await page.goto('/')
  const menu = await openTextModels(page)
  await menu.getByLabel('Поиск модели').fill('claude-test')
  await menu.getByRole('menuitemradio', { name: /Claude Test/ }).click()
  current = { ...catalog, models: [] }
  await page.getByRole('textbox', { name: 'Сообщение' }).fill('Проверить обновлённый каталог')
  await page.getByRole('button', { name: 'Отправить' }).click()
  await expect(page.getByRole('alert')).toContainText('Каталог OpenRouter изменился')
  expect(posts).toBe(0)
  await expect(page.getByRole('textbox', { name: 'Сообщение' })).toHaveValue('Проверить обновлённый каталог')
})

test('unavailable attachment action is explicit and provider errors are named', async ({ page }) => {
  await workspace(page)
  await page.goto('/')
  const add = page.getByRole('button', { name: 'Добавить', exact: true })
  await expect(add).toBeDisabled()
  await expect(add).toHaveAttribute('title', 'Вложения пока недоступны')
  expect(chatProviderProblem('provider_unavailable', 'openrouter')).toBe('OpenRouter сейчас недоступен.')
  expect(chatProviderProblem('provider_rate_limited', 'deepseek')).toBe('DeepSeek ограничил частоту запросов.')
  expect(chatProviderProblem('provider_outcome_unknown', 'openrouter'))
    .toContain('Запрос мог быть оплачен. Не отправляйте его повторно')
  expect(chatProviderProblem('provider_incomplete_response', 'openrouter'))
    .toContain('Проверьте результат перед повторной отправкой')
  expect(chatProblem(new ApiError(409, 'provider_outcome_unknown')))
    .toContain('Запрос мог быть оплачен')
})

test('interrupted stream warns about an unknown paid provider outcome', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  const threadId = '11111111-1111-4111-8111-111111111119'
  await page.route('**/api/v1/chat/threads', route => route.request().method() === 'POST'
    ? route.fulfill({ json: { id: threadId, title: 'Проверка' } }) : route.fallback())
  await page.route(`**/api/v1/chat/threads/${threadId}`, route => route.fulfill({
    json: { thread: { id: threadId, title: 'Проверка' }, messages: [] },
  }))
  await page.route(`**/api/v1/chat/threads/${threadId}/requests`, route => route.fulfill({
    json: { id: route.request().postDataJSON().request_id },
  }))
  await page.route('**/api/v1/chat/requests/*/events', route => route.fulfill({
    status: 200,
    headers: { 'content-type': 'text/event-stream' },
    body: 'event: message.interrupted\ndata: {"reason":"interrupted","code":"provider_outcome_unknown"}\n\n',
  }))
  await page.goto('/')
  await page.getByRole('textbox', { name: 'Сообщение' }).fill('Проверить неизвестный результат')
  await page.getByRole('button', { name: 'Отправить' }).click()
  await expect(page.getByRole('alert')).toContainText('Запрос мог быть оплачен')
  await expect(page.getByRole('alert')).toContainText('Не отправляйте его повторно')
})

test('stop and reload retain an unknown paid outcome warning', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  const threadId = '11111111-1111-4111-8111-111111111120'
  let requestId = ''
  let stopped = false
  let showPersistedCode = false
  let streamStarted!: () => void
  const enteredStream = new Promise<void>(resolve => { streamStarted = resolve })
  let releaseStream!: () => void
  const streamGate = new Promise<void>(resolve => { releaseStream = resolve })
  const thread = { id: threadId, title: 'Проверка после остановки', created_at: 1, updated_at: 1 }
  await page.route('**/api/v1/chat/threads', route => route.request().method() === 'POST'
    ? route.fulfill({ json: thread })
    : route.fulfill({ json: { threads: [thread] } }))
  await page.route(`**/api/v1/chat/threads/${threadId}`, route => {
    if (stopped && !showPersistedCode) return route.fulfill({ status: 503, json: { code: 'unavailable' } })
    return route.fulfill({ json: {
      thread, messages: requestId ? [{
        id: '22222222-2222-4222-8222-222222222220', request_id: requestId,
        role: 'assistant', sequence: 2, content: '', state: stopped ? 'interrupted' : 'partial',
        created_at: 1, updated_at: 1,
      }] : [],
    } })
  })
  await page.route(`**/api/v1/chat/threads/${threadId}/requests`, route => {
    requestId = route.request().postDataJSON().request_id
    return route.fulfill({ json: { id: requestId, thread_id: threadId, state: 'pending' } })
  })
  await page.route('**/api/v1/chat/requests/*/stop', route => {
    stopped = true
    return route.fulfill({ json: { id: requestId, thread_id: threadId, state: 'stopped',
      error_code: 'provider_outcome_unknown' } })
  })
  await page.route('**/api/v1/chat/requests/*/events', async route => {
    streamStarted()
    await streamGate
    await route.abort().catch(() => {})
  })
  await page.route('**/api/v1/chat/requests/*', route => route.fulfill({ json: {
    id: requestId, thread_id: threadId, state: stopped ? 'stopped' : 'streaming',
    error_code: showPersistedCode ? 'provider_outcome_unknown' : null,
  } }))
  await page.goto('/')
  await page.getByRole('textbox', { name: 'Сообщение' }).fill('Проверить остановку')
  await page.getByRole('button', { name: 'Отправить' }).click()
  await enteredStream
  await page.getByRole('button', { name: 'Остановить ответ' }).click()
  releaseStream()
  await expect(page.getByRole('alert')).toContainText('Запрос мог быть оплачен')
  showPersistedCode = true
  await page.reload()
  await page.getByRole('button', { name: 'Проверка после остановки' }).click()
  await expect(page.getByRole('alert')).toContainText('Не отправляйте его повторно')
})
