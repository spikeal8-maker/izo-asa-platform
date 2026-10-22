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
