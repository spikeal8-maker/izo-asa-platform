import { expect, test } from '@playwright/test'
import { noOverflow, workspace } from './workspace-fixtures'
import { graphFixture, openGraphThread, answer } from './conversation-graph-fixture'

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
  // Varying the approved brand token must propagate into the sidebar gradient.
  const beforeBrandChange = await sidebar.evaluate(el => getComputedStyle(el).backgroundImage)
  await page.evaluate(() => document.documentElement.style.setProperty('--color-brand', 'rgb(33, 180, 111)'))
  const afterBrandChange = await sidebar.evaluate(el => getComputedStyle(el).backgroundImage)
  expect(afterBrandChange).not.toBe(beforeBrandChange)
  await page.evaluate(() => document.documentElement.style.removeProperty('--color-brand'))
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
  const documentColor = await page.evaluate(() => getComputedStyle(document.body).backgroundColor)
  expect(mainColor).toBe(documentColor)
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
  const fields = page.locator('.provider-form input:not([type="checkbox"]), .provider-form select, .provider-auth input:not([type="checkbox"])')
  await expect(fields.first()).toBeVisible()
  for (const theme of ['light', 'dark'] as const) {
    await page.evaluate(value => { document.documentElement.dataset.theme = value }, theme)
    const panelColors = await page.locator('.provider-panel').first().evaluate(panel => {
      const sample = document.createElement('span')
      sample.style.cssText = 'background:var(--color-surface);color:var(--color-text)'
      panel.appendChild(sample)
      const actual = getComputedStyle(panel)
      const expected = getComputedStyle(sample)
      const result = {
        background: actual.backgroundColor, expectedBackground: expected.backgroundColor,
        foreground: actual.color, expectedForeground: expected.color,
      }
      sample.remove()
      return result
    })
    expect(panelColors.background).toBe(panelColors.expectedBackground)
    expect(panelColors.foreground).toBe(panelColors.expectedForeground)
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
    const checkColor = await page.locator('.provider-check input[type="checkbox"]').evaluate(element => {
      const sample = document.createElement('input')
      sample.type = 'checkbox'
      sample.style.accentColor = 'var(--color-brand)'
      document.body.appendChild(sample)
      const result = {
        actual: getComputedStyle(element).accentColor,
        expected: getComputedStyle(sample).accentColor,
      }
      sample.remove()
      return result
    })
    expect(checkColor.actual).toBe(checkColor.expected)
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
  // Hovered actions must retain the canonical readable text color in dark mode.
  await page.evaluate(() => { document.documentElement.dataset.theme = 'dark' })
  await page.locator('.chat-page').evaluate(el => {
    el.insertAdjacentHTML('beforeend', '<div class="chat-message-actions"><button>Copy</button></div>')
  })
  const button = page.locator('.chat-page > .chat-message-actions button')
  await button.hover()
  await expect.poll(async () => button.evaluate(el =>
    getComputedStyle(el).color === getComputedStyle(document.body).color)).toBe(true)
})


test('P0 mobile drawer is not usable before the initial account check finishes', async ({ page }) => {
  const fixture = await workspace(page)
  let resolveAuth!: () => void
  let notifyAuth!: () => void
  const pendingAuth = new Promise<void>(resolve => { resolveAuth = resolve })
  const authStarted = new Promise<void>(resolve => { notifyAuth = resolve })
  await page.route('**/api/v1/auth/me', async route => {
    notifyAuth()
    await pendingAuth
    await route.fulfill({ json: { account: fixture.account, csrf_token: 'workspace-csrf' } })
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  try {
    await authStarted
    await expect(page.getByRole('status')).toContainText('Проверяем вход…')
    // A session change must never destroy an already opened drawer.
    await expect(page.getByRole('button', { name: 'Открыть панель' })).toHaveCount(0)
  } finally {
    resolveAuth()
  }
  const opener = page.getByRole('button', { name: 'Открыть панель' })
  await expect(opener).toBeVisible()
  await opener.click()
  await expect(page.getByRole('dialog', { name: 'История чатов' })).toBeVisible()
  await expect(page.locator('.chat-sidebar')).toHaveAttribute('aria-hidden', 'false')
})

test('P0 Graph fixture waits for authenticated mobile drawer before selecting a persisted thread', async ({ page }) => {
  await graphFixture(page)
  let reportAuthRequested!: () => void
  let releaseAuth!: () => void
  const authRequested = new Promise<void>(resolve => { reportAuthRequested = resolve })
  const authGate = new Promise<void>(resolve => { releaseAuth = resolve })
  await page.route('**/api/v1/auth/me', async route => {
    reportAuthRequested()
    await authGate
    await route.fallback()
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  try {
    await authRequested
    await expect(page.getByRole('status')).toContainText('Проверяем вход…')
    const opening = openGraphThread(page)
    releaseAuth()
    await opening
    await expect(answer(page)).toContainText('Ответ 1, вариант 1')
    // Selecting the opened thread intentionally dismisses the mobile drawer.
    await expect(page.locator('.chat-sidebar')).toHaveAttribute('aria-hidden', 'true')
  } finally {
    releaseAuth()
  }
})
