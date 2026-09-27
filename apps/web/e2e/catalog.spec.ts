import { expect, test, type Page } from '@playwright/test'
import { noOverflow, workspace } from './workspace-fixtures'

const pricedModel = {
  id: 'deepseek-flash', label: 'DeepSeek Flash',
  price: { currency: 'RUB', input_kopeks_per_million: 125,
    output_kopeks_per_million: null, image_kopeks_per_image: null },
}
const policy = (revision = 'test', defaultModel = 'deepseek-flash', models = [pricedModel]) => ({
  revision, default_model: defaultModel, models, max_input_chars: 6000, max_output_tokens: 2048,
})

async function setup(page: Page, initial = policy()) {
  const state = await workspace(page)
  await page.route('**/api/v1/chat/policy', route => route.fulfill({ json: initial }))
  return state
}

async function trackChatPosts(page: Page) {
  let count = 0
  await page.route(/\/api\/v1\/chat\/threads(?:\/|$)/, route => {
    if (route.request().method() === 'POST') {
      count += 1
      return route.fulfill({ status: 409, json: { error: { code: 'test_admission' } } })
    }
    return route.fallback()
  })
  return () => count
}

const composer = (page: Page) => page.locator('.chat-composer')
const draft = (page: Page) => composer(page).getByRole('textbox', { name: 'Сообщение' })
const send = (page: Page) => composer(page).getByRole('button', { name: 'Отправить' })

test('catalog-only staff sees Admin between workspaces and tokens', async ({ page }) => {
  const state = await setup(page)
  state.account.permissions = ['catalog.read']
  await page.route('**/api/v1/admin/catalog', route => route.fulfill({
    json: { revision: 1, permissions: ['catalog.read'], providers: [], models: [] },
  }))
  await page.goto('/')
  const header = page.getByTestId('global-header')
  const admin = header.getByRole('link', { name: 'Admin', exact: true })
  await expect(admin).toBeVisible()
  await expect(admin).toHaveAttribute('href', '/admin/catalog')
  const order = await header.evaluate(element => {
    const nodes = ['.product-nav', '.header-admin-link', '.token-box']
      .map(selector => element.querySelector(selector))
    return nodes.every(Boolean)
      && Boolean(nodes[0]!.compareDocumentPosition(nodes[1]!) & Node.DOCUMENT_POSITION_FOLLOWING)
      && Boolean(nodes[1]!.compareDocumentPosition(nodes[2]!) & Node.DOCUMENT_POSITION_FOLLOWING)
  })
  expect(order).toBe(true)
  await noOverflow(page)
  await admin.click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Каталог моделей')
  await expect(page.getByRole('button', { name: 'Настроить' })).toHaveCount(0)
})

test('model menu shows display price and fits 320px', async ({ page }) => {
  await setup(page)
  await page.setViewportSize({ width: 320, height: 568 })
  await page.goto('/')
  await page.getByRole('button', { name: 'Выбрать модель' }).click()
  const menu = page.getByRole('menu', { name: 'Модели' })
  const bounds = await menu.boundingBox()
  expect(bounds).not.toBeNull()
  expect(bounds!.x).toBeGreaterThanOrEqual(0)
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(320)
  await noOverflow(page)
  const text = menu.locator('.chat-model-category').filter({ hasText: 'Текст' })
  await text.locator('summary').click()
  const model = text.getByRole('menuitemradio', { name: 'DeepSeek Flash' })
  await expect(model).toContainText('1,25 ₽')
  await expect(model).toContainText('Цена не задана')
  await expect(menu.getByRole('menuitemradio', { name: 'FLUX.2 [klein] 4B' })).toHaveCount(0)
  await expect(menu).toContainText('При собственном ключе провайдер может взимать плату отдельно.')
})

test('removed default model does not send another model', async ({ page }) => {
  const unavailable = policy('stale', 'deepseek-v4-pro')
  await setup(page, unavailable)
  const posts = await trackChatPosts(page)
  await page.goto('/')
  await expect(draft(page)).toBeEnabled()
  await draft(page).fill('Не отправлять на другую модель')
  await send(page).click()
  await expect(composer(page).getByRole('alert')).toContainText('Выбранная модель больше недоступна')
  expect(posts()).toBe(0)
})

test('changed catalog or failed price check blocks Chat POST', async ({ page }) => {
  await setup(page)
  const posts = await trackChatPosts(page)
  await page.goto('/')
  await expect(draft(page)).toBeEnabled()
  await page.route('**/api/v1/chat/policy', route => route.fulfill({ json: policy('changed') }))
  await draft(page).fill('Проверить новую цену')
  await send(page).click()
  await expect(composer(page).getByRole('alert')).toContainText('Модели или цены изменились')
  expect(posts()).toBe(0)
  await page.route('**/api/v1/chat/policy', route => route.fulfill({
    status: 503, json: { error: { code: 'temporary' } },
  }))
  await send(page).click()
  await expect(composer(page).getByRole('alert')).toContainText('Не удалось проверить цену')
  expect(posts()).toBe(0)
})

test('delayed price check locks inputs until changed policy blocks send', async ({ page }) => {
  await setup(page)
  const posts = await trackChatPosts(page)
  await page.goto('/')
  await expect(draft(page)).toBeEnabled()
  let release: () => void = () => {}, notify: () => void = () => {}
  const gate = new Promise<void>(resolve => { release = resolve })
  const entered = new Promise<void>(resolve => { notify = resolve })
  await page.route('**/api/v1/chat/policy', async route => {
    notify()
    await gate
    await route.fulfill({ json: policy('changed') })
  })
  await draft(page).fill('Черновик остаётся прежним')
  await send(page).click()
  await entered
  await expect(draft(page)).toBeDisabled()
  await expect(composer(page).getByRole('button', { name: 'Выбрать модель' })).toBeDisabled()
  await expect(composer(page).getByRole('button', { name: 'Добавить' })).toBeDisabled()
  await expect(composer(page).getByRole('button', { name: 'Микрофон' })).toBeDisabled()
  await expect(composer(page).getByRole('button', { name: 'Проверяем модель и цену' })).toBeDisabled()
  release()
  await expect(composer(page).getByRole('alert')).toContainText('Модели или цены изменились')
  await expect(draft(page)).toHaveValue('Черновик остаётся прежним')
  await expect(draft(page)).toBeEnabled()
  expect(posts()).toBe(0)
})

test('unchanged policy permits Chat admission attempt', async ({ page }) => {
  await setup(page)
  const posts = await trackChatPosts(page)
  await page.goto('/')
  await expect(draft(page)).toBeEnabled()
  await draft(page).fill('Отправить после проверки')
  await send(page).click()
  await expect.poll(posts).toBe(1)
})
