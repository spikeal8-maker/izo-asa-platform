import { expect, test } from '@playwright/test'
import { noOverflow, workspace } from './workspace-fixtures'

test('P0 Chat visual hierarchy applies to desktop and keeps controls operable', async ({ page }) => {
  await workspace(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  const sidebar = page.locator('.chat-sidebar')
  await expect(sidebar).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Чем я могу помочь?' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Новый чат' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Выбрать модель' })).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Сообщение' })).toBeVisible()
  const style = await sidebar.evaluate(el => {
    const item = getComputedStyle(el)
    return { background: item.backgroundImage, border: item.borderRightColor }
  })
  expect(style.background).toContain('linear-gradient')
  expect(style.background).toContain('rgb(20, 33, 60)')
  await page.getByRole('button', { name: 'Выбрать модель' }).click()
  await expect(page.getByRole('menu', { name: 'Модели' })).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('menu', { name: 'Модели' })).toHaveCount(0)
  await sidebar.getByRole('button', { name: 'Новый чат' }).click()
  await noOverflow(page)
})

test('P0 visual mobile drawer remains accessible and no horizontal clipping', async ({ page }) => {
  await workspace(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.locator('.chat-page')).toBeVisible()
  const mainColor = await page.locator('.chat-main').evaluate(el => getComputedStyle(el).backgroundColor)
  expect(mainColor).toBe('rgb(245, 247, 252)')
  await page.getByRole('button', { name: 'Открыть панель' }).click()
  await expect(page.locator('.chat-sidebar')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Новый чат' })).toBeVisible()
  await noOverflow(page)
  await page.keyboard.press('Escape')
  await expect(page.locator('.chat-sidebar')).toHaveAttribute('inert', '')
  await expect(page.getByRole('textbox', { name: 'Сообщение' })).toBeVisible()
  await noOverflow(page)
})

test('P0 model picker stays legible with semantic colors in both themes', async ({ page }) => {
  await workspace(page)
  await page.goto('/')
  for (const theme of ['light', 'dark'] as const) {
    await page.evaluate(value => { document.documentElement.dataset.theme = value }, theme)
    await page.getByRole('button', { name: 'Выбрать модель' }).click()
    const menu = page.getByRole('menu', { name: 'Модели' })
    await expect(menu).toBeVisible()
    const colors = await menu.evaluate(element => {
      const sample = document.createElement('span')
      sample.style.cssText = 'background:var(--color-surface);color:var(--color-text);border:1px solid var(--color-border)'
      element.appendChild(sample)
      const actual = getComputedStyle(element)
      const expected = getComputedStyle(sample)
      const value = {
        background: actual.backgroundColor, expectedBackground: expected.backgroundColor,
        foreground: actual.color, expectedForeground: expected.color,
        border: actual.borderTopColor, expectedBorder: expected.borderTopColor,
      }
      sample.remove()
      return value
    })
    expect(colors.background).toBe(colors.expectedBackground)
    expect(colors.foreground).toBe(colors.expectedForeground)
    expect(colors.border).toBe(colors.expectedBorder)
    await menu.getByRole('menuitem', { name: /Текст/ }).click()
    const providerTitle = page.locator('.chat-model-provider-title').first()
    await expect(providerTitle).toBeVisible()
    const providerColors = await providerTitle.evaluate(element => {
      const sample = document.createElement('span')
      sample.style.color = 'var(--color-brand)'
      element.appendChild(sample)
      const actual = getComputedStyle(element).color
      const expected = getComputedStyle(sample).color
      sample.remove()
      return { actual, expected }
    })
    expect(providerColors.actual).toBe(providerColors.expected)
    await noOverflow(page)
    await page.keyboard.press('Escape')
    await expect(menu).toHaveCount(0)
  }
})

test('P0 Admin provider forms preserve semantic input colors in both themes', async ({ page }) => {
  await workspace(page)
  await page.route('**/api/v1/admin/providers', route => route.fulfill({ json: {
    connections: [{ provider: 'deepseek', configured: false, enabled: false, verified: false,
      status: 'not_configured', model: 'deepseek-flash', revision: null, generation: null,
      daily_limit: 30, concurrency_limit: 1, available_to_users: false }],
  } }))
  await page.goto('/admin/providers')
  const fields = page.locator('.provider-form input, .provider-form select, .provider-auth input')
  await expect(fields.first()).toBeVisible()
  for (const theme of ['light', 'dark'] as const) {
    await page.evaluate(value => { document.documentElement.dataset.theme = value }, theme)
    const colors = await fields.evaluateAll(elements => {
      const sample = document.createElement('span')
      sample.style.cssText = 'background:var(--color-surface);color:var(--color-text);border:1px solid var(--color-border)'
      document.body.appendChild(sample)
      const style = getComputedStyle(sample)
      const expected = { background: style.backgroundColor, color: style.color, border: style.borderTopColor }
      const found = elements.map(element => {
        const actual = getComputedStyle(element)
        return { background: actual.backgroundColor, color: actual.color, border: actual.borderTopColor }
      })
      sample.remove()
      return { expected, found }
    })
    expect(colors.found.length).toBeGreaterThanOrEqual(3)
    for (const actual of colors.found) {
      expect(actual.background).toBe(colors.expected.background)
      expect(actual.color).toBe(colors.expected.color)
      expect(actual.border).toBe(colors.expected.border)
    }
    await noOverflow(page)
  }
})

test('P0 fenced code copy toolbar uses semantic contrast in light and dark', async ({ page }) => {
  await workspace(page)
  await page.goto('/')
  for (const theme of ['light', 'dark'] as const) {
    await page.evaluate(value => { document.documentElement.dataset.theme = value }, theme)
    const colors = await page.evaluate(() => {
      const parent = document.querySelector('.chat-page')
      if (!parent) throw new Error('Chat page not mounted')
      const block = document.createElement('div')
      block.className = 'chat-code-block'
      const toolbar = document.createElement('div')
      toolbar.className = 'chat-code-toolbar'
      const copy = document.createElement('button')
      copy.type = 'button'
      copy.textContent = 'Копировать'
      toolbar.appendChild(copy)
      block.appendChild(toolbar)
      const sample = document.createElement('span')
      sample.style.cssText = 'background:var(--color-surface);color:var(--color-text-secondary);border:1px solid var(--color-border)'
      block.appendChild(sample)
      parent.appendChild(block)
      const toolbarStyle = getComputedStyle(toolbar)
      const copyStyle = getComputedStyle(copy)
      const expectedStyle = getComputedStyle(sample)
      const colors = {
        background: toolbarStyle.backgroundColor, expectedBackground: expectedStyle.backgroundColor,
        foreground: copyStyle.color, expectedForeground: expectedStyle.color,
      }
      block.remove()
      return colors
    })
    expect(colors.background).toBe(colors.expectedBackground)
    expect(colors.foreground).toBe(colors.expectedForeground)
  }
})
