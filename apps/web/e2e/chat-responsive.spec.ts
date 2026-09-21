import { test, expect, type Page } from '@playwright/test'
import { noOverflow, workspace } from './workspace-fixtures'

const widths = [320, 390, 768, 1024, 1440, 1920, 2560, 3840, 7680]
const desktopWidths = [1440, 1920, 2560, 3840, 7680]
const composer = (page: Page) => page.locator('.chat-composer')
const input = (page: Page) => page.getByRole('textbox', { name: 'Сообщение' })

async function freshChat(page: Page, width: number, height = Math.max(844, Math.round(width * .5625))) {
  await page.setViewportSize({ width, height })
  await page.goto('/')
  await expect(composer(page)).toBeVisible()
}

async function layout(page: Page) {
  return composer(page).getAttribute('data-layout')
}

async function boundaryText(page: Page) {
  let compact = 1, expanded = 400
  await input(page).fill('слово '.repeat(expanded).trim())
  await page.waitForTimeout(16)
  expect(await layout(page)).toBe('expanded')
  while (expanded - compact > 1) {
    const mid = Math.floor((compact + expanded) / 2)
    await input(page).fill('слово '.repeat(mid).trim())
    await page.waitForTimeout(16)
    if (await layout(page) === 'expanded') expanded = mid
    else compact = mid
  }
  return { compact: 'слово '.repeat(compact).trim(), expanded: 'слово '.repeat(expanded).trim() }
}

test('chat shell uses geometry-based sidebar mode and fluid desktop scaling', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  const desktopMetrics: { width: number; heading: number; sidebar: number; composer: number }[] = []
  for (const width of widths) {
    await freshChat(page, width)
    const shell = page.locator('.chat-page')
    const side = page.locator('.chat-sidebar')
    const open = await shell.evaluate(node => node.classList.contains('sidebar-open'))
    if (width < 1120) {
      expect(open).toBe(false)
      const box = await side.boundingBox()
      expect(box ? box.x + box.width : 1).toBeLessThanOrEqual(0)
    } else expect(open).toBe(true)
    await noOverflow(page)
    if (desktopWidths.includes(width)) {
      desktopMetrics.push({ width,
        heading: await page.locator('.chat-start-state h1').evaluate(node => parseFloat(getComputedStyle(node).fontSize)),
        sidebar: (await side.boundingBox())!.width,
        composer: (await page.locator('.chat-composer-wrap').boundingBox())!.width })
    }
  }
  for (let i = 1; i < desktopMetrics.length; i++) {
    expect(desktopMetrics[i].heading).toBeGreaterThanOrEqual(desktopMetrics[i - 1].heading)
    expect(desktopMetrics[i].sidebar).toBeGreaterThanOrEqual(desktopMetrics[i - 1].sidebar)
    expect(desktopMetrics[i].composer).toBeGreaterThanOrEqual(desktopMetrics[i - 1].composer)
  }
})

test('continuous resize has no responsive jumps or horizontal overflow', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  await freshChat(page, 1920, 1080)
  let previous = 0
  for (const width of [1920, 2080, 2304, 2560, 2880, 3200, 3520, 3840, 4096, 4608, 5120, 5760, 6400, 7040, 7680]) {
    await page.setViewportSize({ width, height: Math.max(1080, Math.round(width * .5625)) })
    const current = await page.locator('.chat-start-state h1').evaluate(node => parseFloat(getComputedStyle(node).fontSize))
    expect(current).toBeGreaterThanOrEqual(previous)
    if (previous) expect(current / previous).toBeLessThan(1.12)
    previous = current
    await noOverflow(page)
    await expect(page.locator('.chat-page')).toHaveClass(/sidebar-open/)
  }
})

test('composer is compact for one line and expands from real wrapping', async ({ page }, info) => {
  test.setTimeout(120_000)
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  for (const width of [320, 390, 768, 1440, 1920, 2560, 3840, 7680]) {
    await freshChat(page, width)
    const box = composer(page)
    expect(await layout(page)).toBe('compact')
    const emptyHeight = (await box.boundingBox())!.height
    await input(page).fill('Привет')
    await expect(box).toHaveAttribute('data-layout', 'compact')
    expect(Math.abs((await box.boundingBox())!.height - emptyHeight)).toBeLessThanOrEqual(2)
    const row = await box.evaluate(node => ['.chat-composer-plus', 'textarea', '.chat-model-selector', '.chat-mic-button', '.chat-send-button'].map(selector => { const r = node.querySelector(selector)!.getBoundingClientRect(); return r.top + r.height / 2 }))
    expect(Math.max(...row) - Math.min(...row)).toBeLessThanOrEqual(2)

    const near = await boundaryText(page)
    await input(page).fill(near.compact)
    await expect(box).toHaveAttribute('data-layout', 'compact')
    await input(page).fill(near.expanded)
    await expect(box).toHaveAttribute('data-layout', 'expanded')
    const expandedRows = await box.evaluate(node => ({ input: node.querySelector('textarea')!.getBoundingClientRect(), plus: node.querySelector('.chat-composer-plus')!.getBoundingClientRect() }))
    expect(expandedRows.input.top).toBeLessThan(expandedRows.plus.top)

    await input(page).fill('Первая строка\nВторая строка')
    await expect(box).toHaveAttribute('data-layout', 'expanded')
    await input(page).fill('')
    await expect(box).toHaveAttribute('data-layout', 'compact')
    await noOverflow(page)
  }
})

test('composer layout has hysteresis on resize and attachments force expansion', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  const state = await workspace(page)
  state.capabilities = ['fal.flux2.klein.4b']
  await freshChat(page, 1920, 1080)
  const near = await boundaryText(page)
  await input(page).fill(near.expanded)
  await expect(composer(page)).toHaveAttribute('data-layout', 'expanded')
  for (const width of [1919, 1921, 2560, 3839, 3840, 3841, 5760, 7680]) {
    await page.setViewportSize({ width, height: Math.max(1080, Math.round(width * .5625)) })
    await expect(composer(page)).toHaveAttribute('data-layout', 'expanded')
  }
  await input(page).fill('')
  await expect(composer(page)).toHaveAttribute('data-layout', 'compact')

  const chooser = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: 'Добавить', exact: true }).click()
  await page.getByRole('menu', { name: 'Инструменты' }).getByRole('menuitem', { name: 'Добавить файл' }).click()
  const file = await chooser
  await file.setFiles({ name: 'reference.txt', mimeType: 'text/plain', buffer: Buffer.from('reference') })
  await expect(composer(page)).toHaveAttribute('data-layout', 'expanded')
  await page.getByRole('button', { name: 'Удалить вложение' }).click()
  await expect(composer(page)).toHaveAttribute('data-layout', 'compact')
})
