import { test, expect, type Page } from '@playwright/test'
import { workspace } from './workspace-fixtures'

const viewports = [
  { width: 1440, height: 900 },
  { width: 2048, height: 1228 },
  { width: 768, height: 1024 },
  { width: 390, height: 844 },
]

const catalog = {
  stale: false,
  fetched_at: 123,
  models: Array.from({ length: 80 }, (_, index) => ({
    id: `vendor/model-${String(index + 1).padStart(3, '0')}`,
    name: `Vendor Model ${String(index + 1).padStart(3, '0')}`,
    provider: 'vendor',
    context_length: 131072,
    input_per_million_usd: 1,
    output_per_million_usd: 2,
    created: 123,
  })),
}

async function expectModelMenuGeometry(page: Page) {
  const selector = page.getByRole('button', { name: 'Выбрать модель' })
  await expect(selector).toContainText('DeepSeek Flash')
  await selector.click()

  const menu = page.getByRole('menu', { name: 'Модели' })
  const flash = menu.getByRole('menuitemradio', { name: /DeepSeek Flash/ })
  await expect(flash).toBeVisible()
  await expect(flash).toBeEnabled()
  await expect(flash).toHaveAttribute('aria-checked', 'true')
  await expect(menu.getByRole('menuitemradio', { name: /DeepSeek V4 Pro/ })).toBeVisible()
  await expect(menu.getByRole('menuitemradio', { name: /Автовыбор OpenRouter/ })).toBeDisabled()

  const geometry = await menu.evaluate((node) => {
    const menuRect = node.getBoundingClientRect()
    const headerRect = document.querySelector('.global-header')!.getBoundingClientRect()
    const flashNode = [...node.querySelectorAll<HTMLElement>('[role="menuitemradio"]')]
      .find(item => item.textContent?.includes('DeepSeek Flash'))!
    const flashRect = flashNode.getBoundingClientRect()
    const x = flashRect.left + flashRect.width / 2
    const y = flashRect.top + flashRect.height / 2
    const hit = document.elementFromPoint(x, y)
    return {
      menuTop: menuRect.top,
      menuBottom: menuRect.bottom,
      headerBottom: headerRect.bottom,
      flashTop: flashRect.top,
      flashBottom: flashRect.bottom,
      viewportHeight: innerHeight,
      scrollHeight: node.scrollHeight,
      clientHeight: node.clientHeight,
      pointerHitsFlash: Boolean(hit && flashNode.contains(hit)),
    }
  })

  expect(geometry.menuTop).toBeGreaterThanOrEqual(geometry.headerBottom)
  expect(geometry.menuBottom).toBeLessThanOrEqual(geometry.viewportHeight)
  expect(geometry.flashTop).toBeGreaterThanOrEqual(geometry.headerBottom)
  expect(geometry.flashBottom).toBeLessThanOrEqual(geometry.viewportHeight)
  expect(geometry.scrollHeight).toBeGreaterThan(geometry.clientHeight)
  expect(geometry.pointerHitsFlash).toBe(true)

  await selector.click()
  await expect(menu).toHaveCount(0)
}

test('large OpenRouter catalog keeps selected DeepSeek model below header', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  await page.route('**/api/v1/chat/catalog/openrouter', route =>
    route.fulfill({ json: catalog }))

  for (const viewport of viewports) {
    await page.setViewportSize(viewport)
    await page.goto('/')
    await expect(page.locator('.chat-composer')).toBeVisible()
    await expectModelMenuGeometry(page)
  }
})
