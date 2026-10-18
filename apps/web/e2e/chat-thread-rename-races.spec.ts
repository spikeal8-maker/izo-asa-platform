import { expect, test } from '@playwright/test'
import { fixture, gate, rename, row, side } from './chat-thread-rename-fixture'

test('rename returns focus when an animation frame runs before the pending React commit', async ({ page }) => {
  const state = await fixture(page)
  state.patchGate = gate()
  await rename(page, 'Разговор 1', 'Имя после раннего кадра')
  await expect.poll(() => state.patches).toBe(1)
  await expect(page.getByRole('button', { name: 'Сохраняем…', exact: true })).toBeFocused()
  await page.evaluate(() => {
    const requestFrame = window.requestAnimationFrame
    // Async frame delivery may precede React's scheduled commit after a fetch resolves.
    window.requestAnimationFrame = callback => {
      window.requestAnimationFrame = requestFrame
      queueMicrotask(() => callback(performance.now()))
      return 0
    }
  })
  state.patchGate.release()
  const saved = row(page, 'Имя после раннего кадра')
  await expect(saved).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Название чата', exact: true })).toHaveCount(0)
  await expect(saved.getByRole('button', { name: 'Переименовать', exact: true })).toBeFocused()
})

test('a pending rename preserves focus deliberately moved to another connected control', async ({ page }) => {
  const state = await fixture(page)
  state.patchGate = gate()
  await rename(page, 'Разговор 1', 'Имя после поиска')
  await expect.poll(() => state.patches).toBe(1)
  await side(page).getByRole('button', { name: 'Поиск чатов' }).click()
  const search = side(page).getByRole('textbox', { name: 'Поиск по чатам', exact: true })
  await expect(search).toBeFocused()
  await expect(page.getByRole('textbox', { name: 'Название чата', exact: true })).toBeVisible()
  state.patchGate.release()
  await expect(row(page, 'Имя после поиска')).toBeVisible()
  await expect(page.getByRole('textbox', { name: 'Название чата', exact: true })).toHaveCount(0)
  await expect(search).toBeFocused()
})
