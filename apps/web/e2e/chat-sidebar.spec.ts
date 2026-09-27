import { expect, test, type Page } from '@playwright/test'
import { noOverflow, workspace } from './workspace-fixtures'

const sidebar = (page: Page) => page.locator('.chat-sidebar')
const shell = (page: Page) => page.locator('.chat-page')
const opener = (page: Page) => page.getByRole('button', { name: 'Открыть панель' })

test('desktop collapse leaves usable rail, reflows chat and persists preference', async ({ page }) => {
  await workspace(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  const side = sidebar(page), main = page.locator('.chat-main')
  await expect(side).toBeVisible()
  await side.getByRole('button', { name: 'Скрыть панель' }).click()
  await expect(shell(page)).toHaveClass(/sidebar-compact/)
  await expect.poll(async () => (await side.boundingBox())!.width).toBeLessThanOrEqual(72)
  const rail = (await side.boundingBox())!, content = (await main.boundingBox())!
  expect(rail.width).toBeGreaterThanOrEqual(56)
  expect(Math.abs(content.x - rail.x - rail.width)).toBeLessThanOrEqual(2)
  await expect(side.getByRole('button', { name: 'Новый чат' })).toBeVisible()
  await expect(side.getByRole('button', { name: 'Поиск чатов' })).toBeVisible()
  await expect(side.getByRole('button', { name: 'Развернуть панель' })).toBeVisible()
  await expect(side.getByRole('button', { name: 'Профиль в боковой панели' })).toBeVisible()
  await expect(side.locator('.chat-sidebar-actions button > span')).toBeHidden()
  await noOverflow(page)
  for (const width of [3840, 7680]) {
    await page.setViewportSize({ width, height: 900 })
    await expect.poll(async () => (await side.boundingBox())!.width)
      .toBeGreaterThanOrEqual(width === 3840 ? 170 : 195)
    const wideRail = (await side.boundingBox())!
    for (const control of ['Развернуть панель', 'Поиск чатов', 'Новый чат', 'Профиль в боковой панели']) {
      const icon = (await side.getByRole('button', { name: control }).boundingBox())!
      expect(icon.x).toBeGreaterThanOrEqual(wideRail.x)
      expect(icon.x + icon.width).toBeLessThanOrEqual(wideRail.x + wideRail.width + 1)
    }
    await noOverflow(page)
  }

  await page.reload()
  await expect(shell(page)).toHaveClass(/sidebar-compact/)
  await sidebar(page).getByRole('button', { name: 'Поиск чатов' }).click()
  await expect(shell(page)).toHaveClass(/sidebar-open/)
  await expect(sidebar(page).getByRole('textbox', { name: 'Поиск по чатам' })).toBeFocused()
  await sidebar(page).getByRole('button', { name: 'Скрыть панель' }).click()
  await sidebar(page).getByRole('button', { name: 'Профиль в боковой панели' }).click()
  await expect(shell(page)).toHaveClass(/sidebar-open/)
  await expect(page.getByRole('menuitem', { name: 'Настройки' })).toBeVisible()
  await page.keyboard.press('Escape')
  await sidebar(page).getByRole('button', { name: 'Скрыть панель' }).click()
  await sidebar(page).getByRole('button', { name: 'Развернуть панель' }).click()
  await expect(shell(page)).toHaveClass(/sidebar-open/)
})

test('mobile drawer is inert when closed and dismissals restore opener focus', async ({ page }) => {
  await workspace(page)
  const thread = { id: '11111111-1111-4111-8111-111111111122', title: 'Первый разговор',
    created_at: 1, updated_at: 2 }
  await page.route('**/api/v1/chat/threads', route => route.fulfill({ json: { threads: [thread] } }))
  await page.route(`**/api/v1/chat/threads/${thread.id}`, route => route.fulfill({ json: {
    thread, messages: [{ id: '11111111-1111-4111-8111-111111111123', role: 'user',
      content: 'Открытый разговор', state: 'complete' }],
  } }))
  await page.setViewportSize({ width: 320, height: 640 })
  await page.goto('/')
  const header = page.getByTestId('global-header')
  const headerBox = (await header.boundingBox())!
  await expect(sidebar(page)).toHaveAttribute('aria-hidden', 'true')
  await expect(sidebar(page)).toHaveAttribute('inert', '')
  await opener(page).click()
  await expect(shell(page)).toHaveClass(/sidebar-open/)
  await expect.poll(async () => (await sidebar(page).boundingBox())!.x).toBeGreaterThanOrEqual(-1)
  expect((await sidebar(page).boundingBox())!.width).toBeGreaterThan(250)
  const drawerClose = sidebar(page).getByRole('button', { name: 'Скрыть панель' })
  await expect(drawerClose).toBeFocused()
  await expect(sidebar(page)).toHaveAttribute('role', 'dialog')
  await expect(sidebar(page)).toHaveAttribute('aria-modal', 'true')
  await expect(header).toHaveAttribute('inert', '')
  await expect(page.locator('.chat-main')).toHaveAttribute('inert', '')
  await page.keyboard.press('Shift+Tab')
  await expect(sidebar(page).getByRole('button', { name: 'Профиль в боковой панели' })).toBeFocused()
  await page.keyboard.press('Tab')
  await expect(drawerClose).toBeFocused()
  await header.getByRole('link', { name: 'ИЗО АСА' }).focus()
  await expect(drawerClose).toBeFocused()
  await page.setViewportSize({ width: 320, height: 400 })
  await expect(drawerClose).toBeFocused()
  await expect(header).toHaveAttribute('inert', '')
  await page.setViewportSize({ width: 320, height: 640 })
  await page.keyboard.press('Escape')
  await expect(shell(page)).not.toHaveClass(/sidebar-open/)
  await expect(opener(page)).toBeFocused()
  await expect(sidebar(page)).toHaveAttribute('inert', '')
  await expect(header).not.toHaveAttribute('inert', '')
  await expect(page.locator('.chat-main')).not.toHaveAttribute('inert', '')

  await opener(page).click()
  const backdrop = page.locator('.chat-drawer-backdrop')
  const backdropWidth = (await backdrop.boundingBox())!.width
  await backdrop.click({ position: { x: backdropWidth - 8, y: 200 } })
  await expect(shell(page)).not.toHaveClass(/sidebar-open/)
  await expect(opener(page)).toBeFocused()

  await opener(page).click()
  await sidebar(page).getByRole('button', { name: 'Поиск чатов' }).click()
  await sidebar(page).getByRole('textbox', { name: 'Поиск по чатам' }).fill('Первый')
  await sidebar(page).getByRole('button', { name: 'Первый разговор' }).click()
  await expect(page.getByText('Открытый разговор')).toBeVisible()
  await expect(shell(page)).not.toHaveClass(/sidebar-open/)
  await expect(opener(page)).toBeFocused()
  await opener(page).click()
  await expect(sidebar(page).getByRole('textbox', { name: 'Поиск по чатам' })).toHaveCount(0)
  await page.keyboard.press('Escape')
  const nextHeader = (await header.boundingBox())!
  expect([nextHeader.x, nextHeader.y, nextHeader.width, nextHeader.height])
    .toEqual([headerBox.x, headerBox.y, headerBox.width, headerBox.height])
  await noOverflow(page)
})

test('desktop focus in sidebar migrates to mobile opener on resize', async ({ page }) => {
  await workspace(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await sidebar(page).getByRole('button', { name: 'Поиск чатов' }).focus()
  await expect(sidebar(page).getByRole('button', { name: 'Поиск чатов' })).toBeFocused()
  await page.setViewportSize({ width: 320, height: 640 })
  await expect(sidebar(page)).toHaveAttribute('inert', '')
  await expect(opener(page)).toBeFocused()
  await page.keyboard.press('Tab')
  expect(await page.evaluate(() => Boolean(document.activeElement?.closest('.chat-sidebar')))).toBe(false)
})

test('mobile drawer reopens without old search or profile state', async ({ page }) => {
  await workspace(page)
  await page.setViewportSize({ width: 320, height: 640 })
  await page.goto('/')
  const side = sidebar(page)
  const backdrop = page.locator('.chat-drawer-backdrop')
  const dismiss = async () => {
    const width = (await backdrop.boundingBox())!.width
    await backdrop.click({ position: { x: width - 8, y: 200 } })
    await expect(opener(page)).toBeFocused()
  }
  await opener(page).click()
  await side.getByRole('button', { name: 'Поиск чатов' }).click()
  await side.getByRole('textbox', { name: 'Поиск по чатам' }).fill('старый запрос')
  await dismiss()
  await opener(page).click()
  await expect(side.getByRole('textbox', { name: 'Поиск по чатам' })).toHaveCount(0)
  await expect(side.getByRole('button', { name: 'Поиск чатов' })).toHaveAttribute('aria-expanded', 'false')

  await side.getByRole('button', { name: 'Профиль в боковой панели' }).click()
  await expect(side.getByRole('menuitem', { name: 'Настройки' })).toBeVisible()
  await dismiss()
  await opener(page).click()
  await expect(side.getByRole('menuitem', { name: 'Настройки' })).toHaveCount(0)
  await expect(side.getByRole('button', { name: 'Профиль в боковой панели' })).toHaveAttribute('aria-expanded', 'false')
  await side.getByRole('button', { name: 'Поиск чатов' }).click()
  await side.getByRole('textbox', { name: 'Поиск по чатам' }).fill('после нового чата')
  await side.getByRole('button', { name: 'Новый чат' }).click()
  await expect(opener(page)).toBeFocused()
  await opener(page).click()
  await expect(side.getByRole('textbox', { name: 'Поиск по чатам' })).toHaveCount(0)
  await side.getByRole('button', { name: 'Профиль в боковой панели' }).click()
  await page.keyboard.press('Escape')
  await expect(side.getByRole('menuitem', { name: 'Настройки' })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await expect(opener(page)).toBeFocused()
  await opener(page).click()
  await expect(side.getByRole('menuitem', { name: 'Настройки' })).toHaveCount(0)
})

test('empty heading and composer share a centered block on phone and desktop', async ({ page }) => {
  await workspace(page)
  for (const viewport of [{ width: 320, height: 640 }, { width: 1440, height: 900 }]) {
    await page.setViewportSize(viewport)
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Чем я могу помочь?' })).toBeVisible()
    await expect(page.getByRole('textbox', { name: 'Сообщение' })).toBeEnabled()
    const main = (await page.locator('.chat-main').boundingBox())!
    const block = (await page.locator('.chat-start-state').boundingBox())!
    const heading = (await page.getByRole('heading', { name: 'Чем я могу помочь?' }).boundingBox())!
    const input = (await page.locator('.chat-composer-wrap').boundingBox())!
    if (viewport.width === 320) {
      const textarea = (await page.getByRole('textbox', { name: 'Сообщение' }).boundingBox())!
      const plus = (await page.getByRole('button', { name: 'Добавить' }).boundingBox())!
      expect(textarea.y + textarea.height).toBeLessThanOrEqual(plus.y)
    }
    const centerX = main.x + main.width / 2
    expect(Math.abs(heading.x + heading.width / 2 - centerX)).toBeLessThanOrEqual(2)
    expect(Math.abs(input.x + input.width / 2 - centerX)).toBeLessThanOrEqual(2)
    const contentCenter = (heading.y + input.y + input.height) / 2
    expect(Math.abs(contentCenter - (block.y + block.height / 2))).toBeLessThanOrEqual(12)
    const toolbar = (await page.locator('.chat-toolbar').boundingBox())!
    const availableCenter = toolbar.y + toolbar.height + (main.height - toolbar.height) / 2
    expect(Math.abs(contentCenter - availableCenter)).toBeLessThanOrEqual(12)
    await noOverflow(page)
  }
})
