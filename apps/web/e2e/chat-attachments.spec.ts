import { test, expect, type Page } from '@playwright/test'
import { noOverflow, png, workspace } from './workspace-fixtures'

const composer = (page: Page) => page.locator('.chat-composer')
const input = (page: Page) => page.getByRole('textbox', { name: 'Сообщение' })

async function freshChat(page: Page) {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')
  await expect(composer(page)).toBeVisible()
}

test('Anthropic attachment composer keeps five ordered image drafts', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  await freshChat(page)
  const chooser = page.locator('input.chat-file-input')
  const files = Array.from({ length: 6 }, (_, index) => ({
    name: `owner-${index + 1}.png`, mimeType: 'image/png', buffer: png,
  }))
  await chooser.setInputFiles(files.slice(0, 1))
  await expect(page.getByTestId('chat-attachment-preview')).toHaveCount(1)
  const wrap = await page.locator('.chat-composer-wrap').boundingBox()
  expect(Math.round(wrap!.width)).toBe(672)
  const first = page.getByTestId('chat-attachment-preview').first()
  const tile = await first.boundingBox()
  expect(Math.round(tile!.width)).toBe(120)
  expect(Math.round(tile!.height)).toBe(120)
  expect(await first.locator('img').evaluate(node => getComputedStyle(node).objectFit)).toBe('contain')
  expect(await first.locator('.chat-attachment-sr').evaluate(
    node => getComputedStyle(node).clip)).not.toBe('auto')

  const stripBox = await page.getByTestId('chat-attachment-strip').boundingBox()
  const inputBox = await input(page).boundingBox()
  expect(stripBox!.y + stripBox!.height).toBeLessThanOrEqual(inputBox!.y + 1)
  expect(await page.getByTestId('chat-attachment-strip').evaluate(
    node => getComputedStyle(node).gap)).toBe('12px')
  expect(await page.getByTestId('chat-attachment-strip').evaluate(
    node => getComputedStyle(node).overflowX)).toBe('auto')

  const remove = page.getByRole('button', { name: 'Удалить изображение owner-1.png' })
  expect(await remove.evaluate(node => getComputedStyle(node).opacity)).toBe('0')
  await first.hover()
  expect(await remove.evaluate(node => getComputedStyle(node).opacity)).toBe('1')
  await remove.click()
  await expect(page.getByTestId('chat-attachment-preview')).toHaveCount(0)
  await chooser.setInputFiles(files.slice(0, 3))
  await expect(page.getByTestId('chat-attachment-preview')).toHaveCount(3)
  await chooser.setInputFiles(files.slice(3, 5))
  await expect(page.getByTestId('chat-attachment-preview')).toHaveCount(5)
  await input(page).fill('Черновик')
  await chooser.setInputFiles(files.slice(5))
  await expect(page.getByTestId('chat-attachment-preview')).toHaveCount(5)
  await expect(page.getByText('Можно прикрепить не больше 5 изображений.')).toBeVisible()
  await expect(input(page)).toHaveValue('Черновик')

  await page.getByTestId('chat-attachment-preview').nth(1).hover()
  await page.getByRole('button', { name: 'Удалить изображение owner-2.png' }).click()
  await expect(page.getByTestId('chat-attachment-preview')).toHaveCount(4)
  const labels = await page.locator('.chat-attachment-tile > button').evaluateAll(nodes =>
    nodes.map(node => node.getAttribute('aria-label')))
  expect(labels).toEqual([
    'Удалить изображение owner-1.png',
    'Удалить изображение owner-3.png',
    'Удалить изображение owner-4.png',
    'Удалить изображение owner-5.png',
  ])
  while (await page.getByTestId('chat-attachment-preview').count()) {
    const current = page.getByTestId('chat-attachment-preview').first()
    await current.hover()
    await current.locator('button').click()
  }
  const bytes = Array.from(png)
  await composer(page).evaluate((node, raw) => {
    const transfer = new DataTransfer()
    transfer.items.add(new File([new Uint8Array(raw)], 'paste.png', { type: 'image/png' }))
    node.dispatchEvent(new ClipboardEvent('paste', {
      bubbles: true, cancelable: true, clipboardData: transfer,
    }))
  }, bytes)
  await expect(page.getByRole(
    'button', { name: 'Удалить изображение paste.png' })).toBeAttached()

  await composer(page).evaluate((node, raw) => {
    const transfer = new DataTransfer()
    transfer.items.add(new File([new Uint8Array(raw)], 'drop.png', { type: 'image/png' }))
    node.dispatchEvent(new DragEvent('drop', {
      bubbles: true, cancelable: true, dataTransfer: transfer,
    }))
  }, bytes)
  await expect(page.getByRole(
    'button', { name: 'Удалить изображение drop.png' })).toBeAttached()
  await expect(page.getByTestId('chat-attachment-preview')).toHaveCount(2)
  await noOverflow(page)
})
