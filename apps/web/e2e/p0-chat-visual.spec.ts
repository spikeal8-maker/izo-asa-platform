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
