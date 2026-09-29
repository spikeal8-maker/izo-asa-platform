import { test, expect, type Page } from '@playwright/test'
import { chatWorkspace, noOverflow, png, visionPolicy, workspace } from './workspace-fixtures'

const widths = [320, 390, 768, 1024, 1440, 1920, 2560, 3840, 7680]
const desktopWidths = [1440, 1920, 2560, 3840, 7680]
const structuralBoundaries = [359, 360, 361, 388, 389, 390, 519, 520, 521, 1119, 1120, 1121]
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

async function preciseBoundaryText(page: Page) {
  let compact = 1, expanded = 2400
  const value = (length: number) => 'i'.repeat(length)
  await input(page).fill(value(expanded))
  await expect(composer(page)).toHaveAttribute('data-layout', 'expanded')
  while (expanded - compact > 1) {
    const mid = Math.floor((compact + expanded) / 2)
    await input(page).fill(value(mid))
    await page.waitForTimeout(16)
    if (await layout(page) === 'expanded') expanded = mid
    else compact = mid
  }
  return { compact: value(compact), expanded: value(expanded) }
}

async function expectNoHeaderCollision(page: Page) {
  const boxes = await page.locator('.global-brand,.explore-nav,.product-nav,.header-right').evaluateAll(nodes =>
    nodes.map(node => {
      const rect = node.getBoundingClientRect()
      return { name: (node as HTMLElement).className, left: rect.left, right: rect.right, top: rect.top, bottom: rect.bottom }
    }),
  )
  for (let first = 0; first < boxes.length; first++) {
    for (let second = first + 1; second < boxes.length; second++) {
      const a = boxes[first], b = boxes[second]
      const overlapX = Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left))
      const overlapY = Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top))
      expect(overlapX * overlapY, `${a.name} collides with ${b.name}`).toBeLessThanOrEqual(1)
    }
  }
}

async function expectCompactRow(page: Page) {
  const row = await composer(page).evaluate(node =>
    ({ width: node.getBoundingClientRect().width, centers: ['.chat-composer-plus', 'textarea', '.chat-model-selector', '.chat-mic-button', '.chat-send-button'].map(selector => {
      const rect = node.querySelector(selector)!.getBoundingClientRect()
      return rect.top + rect.height / 2
    }) }),
  )
  const [plus, input, model, mic, send] = row.centers
  const controls = [plus, model, mic, send]
  expect(Math.max(...controls) - Math.min(...controls)).toBeLessThanOrEqual(2)
  if (row.width <= 620) expect(input).toBeLessThan(plus - 2)
  else expect(Math.abs(input - plus)).toBeLessThanOrEqual(2)
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

test('attachment list stays frozen during delayed policy preflight', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  const { admitted } = await chatWorkspace(page)
  let reads = 0, entered!: () => void, release!: () => void
  const waiting = new Promise<void>(resolve => { entered = resolve })
  const gate = new Promise<void>(resolve => { release = resolve })
  await page.route('**/api/v1/chat/policy', async route => {
    if (++reads > 1) { entered(); await gate }
    await route.fulfill({ json: visionPolicy })
  })
  await page.goto('/')
  await page.getByLabel('Выбрать изображения').setInputFiles({ name: 'fixed.png', mimeType: 'image/png', buffer: png })
  await page.getByRole('button', { name: 'Отправить' }).click()
  await waiting
  await expect(page.getByRole('button', { name: 'Удалить изображение fixed.png' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Добавить', exact: true })).toBeDisabled()
  await page.locator('.chat-composer').evaluate((node, bytes) => {
    const transfer = new DataTransfer()
    transfer.items.add(new File([new Uint8Array(bytes)], 'late.png', { type: 'image/png' }))
    node.dispatchEvent(new DragEvent('drop', { dataTransfer: transfer, bubbles: true, cancelable: true }))
  }, Array.from(png))
  await expect(page.getByTestId('chat-attachment-preview')).toHaveCount(1)
  release()
  await expect.poll(() => admitted.length).toBe(1)
  expect((admitted[0].attachment_ids as string[])).toHaveLength(1)
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
    await expectCompactRow(page)

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

test('composer remains readable on wide screens and unavailable attachments stay disabled', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  await freshChat(page, 1920, 1080)
  const near = await preciseBoundaryText(page)
  await input(page).fill(near.expanded)
  await expect(composer(page)).toHaveAttribute('data-layout', 'expanded')
  const bounded = await page.locator('.chat-composer-wrap').boundingBox()
  expect(bounded!.width).toBeLessThanOrEqual(760)
  await page.setViewportSize({ width: 3840, height: 1080 })
  const wide = await page.locator('.chat-composer-wrap').boundingBox()
  expect(wide!.width).toBeLessThanOrEqual(760)
  await expect(composer(page)).toHaveAttribute('data-layout', 'expanded')

  await input(page).fill('')
  await expect(composer(page)).toHaveAttribute('data-layout', 'compact')
  await expect(page.getByRole('button', { name: 'Добавить', exact: true })).toBeDisabled()
  await noOverflow(page)
})

test('composer remeasures when compact control geometry changes', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  const state = await workspace(page)
  state.capabilities = ['fal.flux2.klein.4b']
  await freshChat(page, 1440)
  const near = await preciseBoundaryText(page)
  const controlSensitiveText = near.compact.slice(0, -4)
  await input(page).fill(controlSensitiveText)
  await expect(composer(page)).toHaveAttribute('data-layout', 'compact')

  const modelButton = page.getByRole('button', { name: 'Выбрать модель' })
  const autoWidth = (await modelButton.boundingBox())!.width
  await modelButton.click()
  const textCategory = page.locator('.chat-model-category').filter({ hasText: 'Текст' })
  await expect(textCategory).toContainText('3')
  await textCategory.locator('summary').click()
  await page.getByRole('menuitemradio', { name: 'DeepSeek V4 Pro' }).click()
  await expect(modelButton).toContainText('DeepSeek V4 Pro')
  expect((await modelButton.boundingBox())!.width).toBeGreaterThan(autoWidth)
  await expect(composer(page)).toHaveAttribute('data-layout', 'expanded')

  await modelButton.click()
  await page.getByRole('menuitemradio', { name: 'Авто' }).click()
  await expect(modelButton).toContainText('Авто')
  await expect(composer(page)).toHaveAttribute('data-layout', 'compact')
})

test('responsive structural boundaries keep header, sidebar and composer geometry valid', async ({ page }, info) => {
  test.setTimeout(120_000)
  test.skip(info.project.name !== 'laptop')
  await workspace(page)
  for (const width of structuralBoundaries) {
    await freshChat(page, width)
    const shell = page.locator('.chat-page')
    const side = page.locator('.chat-sidebar')
    const shouldBeDesktop = width >= 1120
    expect(await shell.evaluate(node => node.classList.contains('sidebar-open'))).toBe(shouldBeDesktop)
    expect(await side.evaluate(node => getComputedStyle(node).position)).toBe(shouldBeDesktop ? 'static' : 'absolute')
    if (!shouldBeDesktop) {
      const box = await side.boundingBox()
      expect(box ? box.x + box.width : 1).toBeLessThanOrEqual(0)
    }

    await expectNoHeaderCollision(page)
    await expect(composer(page)).toHaveAttribute('data-layout', 'compact')
    await input(page).fill('Привет')
    await expect(composer(page)).toHaveAttribute('data-layout', 'compact')
    await expectCompactRow(page)

    await input(page).fill('длинный текст '.repeat(120))
    await expect(composer(page)).toHaveAttribute('data-layout', 'expanded')
    const expandedRows = await composer(page).evaluate(node => ({
      input: node.querySelector('textarea')!.getBoundingClientRect(),
      plus: node.querySelector('.chat-composer-plus')!.getBoundingClientRect(),
    }))
    expect(expandedRows.input.top).toBeLessThan(expandedRows.plus.top)
    await noOverflow(page)

    await input(page).fill('')
    await expect(composer(page)).toHaveAttribute('data-layout', 'compact')
  }
})
