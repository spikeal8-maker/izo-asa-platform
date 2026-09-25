import { test, expect, type Locator, type Page } from '@playwright/test'
import { chatProviderProblem } from '../src/shared/api'
import { workspace } from './workspace-fixtures'

const catalog = {
  stale: false,
  fetched_at: 123,
  models: [
    {
      id: 'anthropic/claude-test',
      name: 'Claude Test',
      provider: 'anthropic',
      context_length: 200000,
      input_per_million_usd: 3,
      output_per_million_usd: 15,
      created: 123,
    },
    {
      id: 'google/gemini-test',
      name: 'Gemini Test',
      provider: 'google',
      context_length: 1000000,
      input_per_million_usd: 1,
      output_per_million_usd: 2,
      created: 123,
    },
  ],
}

async function contrast(locator: Locator) {
  return locator.evaluate(node => {
    function rgb(value: string) {
      const match = value.match(/[\d.]+/g)?.slice(0, 3).map(Number) ?? [0, 0, 0]
      return match.map(item => {
        const v = item / 255
        return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4
      })
    }
    const style = getComputedStyle(node)
    const fg = rgb(style.color)
    const bg = rgb(style.backgroundColor)
    const luminance = (parts: number[]) => .2126 * parts[0] + .7152 * parts[1] + .0722 * parts[2]
    const a = luminance(fg), b = luminance(bg)
    return {
      ratio: (Math.max(a, b) + .05) / (Math.min(a, b) + .05),
      color: style.color,
      background: style.backgroundColor,
      outline: style.outlineColor,
    }
  })
}

async function openProviders(page: Page) {
  await page.getByRole('button', {
    name: 'Настройки DeepSeek и OpenRouter',
  }).click()
}

test('OpenRouter catalog uses donor-style search and provider metadata', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  await page.route('**/api/v1/chat/catalog/openrouter', route =>
    route.fulfill({ json: catalog }))
  await page.goto('/')

  const selector = page.getByRole('button', { name: 'Выбрать модель' })
  await selector.click()
  const menu = page.getByRole('menu', { name: 'Модели' })
  await expect(menu.getByText('DeepSeek', { exact: true })).toBeVisible()
  await expect(menu.getByText('OpenRouter', { exact: true })).toBeVisible()
  await expect(menu.getByRole('menuitemradio', { name: /Автовыбор OpenRouter/ }))
    .toBeDisabled()
  await expect(menu.getByRole('menuitemradio', { name: /Claude Test/ }))
    .toContainText('anthropic · контекст 200 000')

  const search = menu.getByLabel('Поиск модели')
  await search.fill('anthropic')
  await expect(menu.getByRole('menuitemradio')).toHaveCount(1)
  await expect(menu.getByRole('menuitemradio', { name: /Claude Test/ })).toBeVisible()

  await search.fill('google')
  await expect(menu.getByRole('menuitemradio')).toHaveCount(1)
  await expect(menu.getByRole('menuitemradio', { name: /Gemini Test/ })).toBeVisible()

  await search.fill('claude-test')
  await expect(menu.getByRole('menuitemradio', { name: /Claude Test/ })).toBeVisible()
})

test('provider settings hide saved keys and semantic buttons retain contrast', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  await page.route('**/api/v1/chat/catalog/openrouter', route =>
    route.fulfill({ json: catalog }))
  await page.goto('/')
  await openProviders(page)

  const deepseek = page.locator('.chat-provider-card').filter({ hasText: 'DeepSeek' })
  const openrouter = page.locator('.chat-provider-card').filter({ hasText: 'OpenRouter' })
  await expect(deepseek.getByLabel('Новый API key DeepSeek')).toHaveCount(0)
  await expect(deepseek.getByRole('button', { name: 'Проверить' })).toBeVisible()
  await expect(deepseek.getByRole('button', { name: 'Заменить ключ' })).toBeVisible()
  await expect(deepseek.getByRole('button', { name: 'Отключить' })).toBeVisible()
  await expect(openrouter.getByLabel('Новый API key OpenRouter')).toHaveCount(0)

  await openrouter.getByRole('button', { name: 'Добавить ключ' }).click()
  const input = openrouter.getByLabel('Новый API key OpenRouter')
  await expect(input).toBeVisible()
  const primary = openrouter.getByRole('button', { name: 'Сохранить и проверить' })
  await expect(primary).toBeDisabled()
  await input.fill('synthetic-openrouter-credential')
  await expect(primary).toBeEnabled()

  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => {
      document.documentElement.dataset.theme = value
    }, theme)
    const normal = await contrast(primary)
    expect(normal.ratio).toBeGreaterThanOrEqual(4.5)
    await primary.hover()
    const hovered = await contrast(primary)
    expect(hovered.ratio).toBeGreaterThanOrEqual(4.5)
    await primary.focus()
    const focused = await contrast(primary)
    expect(focused.ratio).toBeGreaterThanOrEqual(4.5)
    expect(focused.outline).not.toBe('rgba(0, 0, 0, 0)')
  }

  const secondary = openrouter.getByRole('button', { name: 'Отмена' })
  await expect(secondary).toBeEnabled()
  for (const theme of ['light', 'dark']) {
    await page.evaluate(value => {
      document.documentElement.dataset.theme = value
    }, theme)
    const normal = await contrast(secondary)
    expect(normal.ratio).toBeGreaterThanOrEqual(4.5)
    await secondary.hover()
    expect((await contrast(secondary)).ratio).toBeGreaterThanOrEqual(4.5)
    await secondary.focus()
    expect((await contrast(secondary)).ratio).toBeGreaterThanOrEqual(4.5)
  }
})

test('provider errors never label OpenRouter as DeepSeek', () => {
  expect(chatProviderProblem('provider_unavailable', 'openrouter'))
    .toBe('OpenRouter сейчас недоступен.')
  expect(chatProviderProblem('provider_rate_limited', 'openrouter'))
    .toBe('OpenRouter ограничил частоту запросов.')
  expect(chatProviderProblem('provider_unavailable', 'deepseek'))
    .toBe('DeepSeek сейчас недоступен.')
})
