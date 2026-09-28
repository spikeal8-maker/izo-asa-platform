import { expect, test, type Page } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { asset, chatWorkspace as chat, noOverflow, owner, png, visionPolicy, visionProvider, visionThread } from './workspace-fixtures'

const input = (page: Page) => page.getByLabel('Выбрать изображения')
const button = (page: Page, name: string) => page.getByRole('button', { name })
const send = (page: Page) => button(page, 'Отправить').click()
const pngFile = (name: string) => ({ name, mimeType: 'image/png', buffer: png })
const previews = (page: Page) => page.getByTestId('chat-attachment-preview')
const alert = (page: Page) => page.getByRole('alert')
const count = (page: Page, n: number) => expect(previews(page)).toHaveCount(n)
const warn = (page: Page, text: string) => expect(alert(page)).toContainText(text)
const pending = (page: Page) => page.evaluate(account =>
  JSON.parse(localStorage.getItem(`izo-chat-pending-media:${account}`) ?? '[]'), owner)
const laptop = (info: { project: { name: string } }) => test.skip(info.project.name !== 'laptop')
const accepted = (items: unknown[]) => expect.poll(() => items.length).toBe(1)
async function attach(page: Page, files: Parameters<ReturnType<typeof input>['setInputFiles']>[0]) {
  await expect(page.getByRole('button', { name: 'Добавить', exact: true })).toBeEnabled()
  await input(page).setInputFiles(files)
}

test('image-only renders after reload', async ({ page }, info) => {
  const { app, admitted } = await chat(page)
  await page.goto('/')
  await attach(page, pngFile('образец.png'))
  await count(page, 1)
  await expect(page.locator('.chat-composer')).toHaveAttribute('data-layout', 'expanded')
  await page.screenshot({ path: info.outputPath('chat-attachment-compose.png') })
  await send(page)
  await accepted(admitted)
  expect(admitted[0]).toMatchObject({ text: '', model: 'deepseek-flash',
    attachment_ids: [app.assets[0].id] })
  expect(app.uploadOperations.size).toBe(1)
  await expect(page.getByAltText('Прикреплённое изображение')).toBeVisible()
  await page.reload()
  if (page.viewportSize()!.width < 1120) await button(page, 'Открыть панель').click()
  await button(page, 'Изображение').click()
  await expect(page.getByAltText('Прикреплённое изображение')).toBeVisible()
  await noOverflow(page)
})

test('unknown Media preserves operation order', async ({ page }) => {
  const { app, admitted } = await chat(page)
  app.uploadUncertainOnce = true
  await page.goto('/')
  const files = [1, 2].map(number => ({ name: `image-${number}.png`, mimeType: 'image/png', buffer: png }))
  await attach(page, files)
  await count(page, 2)
  await page.getByRole('textbox', { name: 'Сообщение' }).fill('Сравни их')
  await send(page)
  await accepted(admitted)
  expect((admitted[0].attachment_ids as string[])).toEqual(app.assets.map(item => item.id))
  expect(app.uploadOperations.size).toBe(2)
})

test('storing retry keeps upload ID', async ({ page }, info) => {
  laptop(info)
  const { app, admitted } = await chat(page)
  let completed = 0, contents = 0
  await page.route(/\/api\/v1\/media\/uploads\/[^/]+\/content$/, route => {
    const id = new URL(route.request().url()).pathname.split('/')[5]
    const upload = app.uploads.get(id)!
    if (++contents === 1) {
      upload.status = 'storing'
      return route.fulfill({ status: 503, json: { error: { code: 'storage_write_uncertain' } } })
    }
    upload.status = 'ready'; upload.asset_id = id
    app.assets.push(asset(id as ReturnType<typeof randomUUID>))
    return route.fulfill({ json: upload })
  })
  await page.route(/\/api\/v1\/media\/uploads\/[^/]+\/complete$/, route => {
    completed++
    return route.fulfill({ status: 503, json: { error: { code: 'storage_write_uncertain' } } })
  })
  await page.goto('/')
  await attach(page, pngFile('stored.png'))
  await send(page)
  await accepted(admitted)
  expect(completed).toBe(1)
  expect(contents).toBe(2)
  expect(app.uploadOperations.size).toBe(1)
})

test('validating retry keeps upload ID', async ({ page }, info) => {
  laptop(info)
  const { app, admitted } = await chat(page)
  let first = true
  await page.route(/\/api\/v1\/media\/uploads\/[^/]+\/content$/, route => {
    const id = new URL(route.request().url()).pathname.split('/')[5]
    const upload = app.uploads.get(id)!
    if (first) { first = false; upload.status = 'validating'
      return route.fulfill({ status: 409, json: { error: { code: 'upload_busy' } } }) }
    upload.status = 'ready'; upload.asset_id = id
    app.assets.push(asset(id as ReturnType<typeof randomUUID>))
    return route.fulfill({ json: upload })
  })
  await page.goto('/')
  await attach(page, pngFile('lease.png'))
  await send(page)
  await warn(page, 'ещё обрабатывается')
  await send(page)
  await accepted(admitted)
  expect(app.uploadOperations.size).toBe(1)
})

test('invalid format and plan rejection retain draft', async ({ page }) => {
  const { app, admitted } = await chat(page)
  await page.goto('/')
  await attach(page, { name: 'bad.gif', mimeType: 'image/gif', buffer: png })
  await warn(page, 'Поддерживаются PNG, JPEG и WebP')
  await count(page, 0)
  await attach(page, pngFile('valid.png'))
  app.uploadError = 'plan_unconfigured'
  await send(page)
  await warn(page, 'не настроил лимиты загрузки')
  await count(page, 1)
  expect(admitted).toHaveLength(0)
})

test('paste and drop share vision preview', async ({ page }, info) => {
  laptop(info)
  await chat(page)
  await page.goto('/')
  await button(page, 'Выбрать модель').click()
  await page.locator('.chat-model-category summary').click()
  await page.getByRole('menuitemradio', { name: /DeepSeek Text/ }).click()
  await page.getByRole('textbox', { name: 'Сообщение' }).evaluate((node, bytes) => {
    const transfer = new DataTransfer()
    transfer.items.add(new File([new Uint8Array(bytes)], 'pasted.png', { type: 'image/png' }))
    node.dispatchEvent(new ClipboardEvent('paste', { clipboardData: transfer, bubbles: true }))
  }, Array.from(png))
  await count(page, 1)
  await expect(button(page, 'Выбрать модель')).toContainText('DeepSeek Flash')
  await page.locator('.chat-composer').evaluate((node, bytes) => {
    const transfer = new DataTransfer()
    transfer.items.add(new File([new Uint8Array(bytes)], 'dropped.png', { type: 'image/png' }))
    node.dispatchEvent(new DragEvent('drop', { dataTransfer: transfer, bubbles: true, cancelable: true }))
  }, Array.from(png))
  await count(page, 2)
  await button(page, 'Удалить изображение pasted.png').click()
  await count(page, 1)
  await attach(page, Array.from({ length: 6 }, (_, index) =>
    ({ name: `bulk-${index}.png`, mimeType: 'image/png', buffer: png })))
  await count(page, 5)
  await warn(page, 'не больше 5 изображений')
  await button(page, 'Новый чат').click()
  await count(page, 0)
  await expect.poll(async () => (await pending(page)).length).toBe(0)
  await noOverflow(page)
})

test('OpenRouter vision rechecked before admission', async ({ page }, info) => {
  laptop(info)
  const { admitted } = await chat(page)
  let vision = true
  await visionProvider(page, () => vision)
  await page.goto('/')
  await button(page, 'Выбрать модель').click()
  await page.locator('.chat-model-category summary').click()
  await page.getByRole('menuitemradio', { name: /Vision Test/ }).click()
  await attach(page, pngFile('vision.png'))
  vision = false
  await send(page)
  await warn(page, 'больше не принимает изображения')
  expect(admitted).toHaveLength(0)
  vision = true
  await send(page)
  await accepted(admitted)
  expect(admitted[0]).toMatchObject({ model: 'anthropic/vision-test' })
})

test('uncertain Media keeps ID through reload', async ({ page }, info) => {
  laptop(info)
  const { app, admitted } = await chat(page, true)
  let fail = true
  await page.route(/\/api\/v1\/media\/uploads\/[^/]+\/content$/, route => {
    if (fail) { fail = false; return route.abort('failed') }
    return route.fallback()
  })
  await page.goto('/')
  const file = pngFile('recover.png')
  await attach(page, file)
  await send(page)
  await warn(page, 'тот же файл')
  expect(app.uploadOperations.size).toBe(1)
  await page.locator('.chat-sidebar').getByRole('button', { name: visionThread.title, exact: true }).click()
  await expect(page.getByText('Есть незавершённая загрузка')).toBeVisible()
  await button(page, 'Новый чат').click()
  await expect(page.getByText('Есть незавершённая загрузка')).toBeVisible()
  await page.reload()
  await expect(page.getByText('Есть незавершённая загрузка')).toBeVisible()
  await attach(page, file)
  await send(page)
  await accepted(admitted)
  expect(app.uploadOperations.size).toBe(1)
  const ids = app.requests.filter(item => item.path === '/api/v1/media/uploads')
    .map(item => item.body!.operation_id)
  expect(new Set(ids).size).toBe(1)
  await page.reload()
  await expect(page.getByText('Есть незавершённая загрузка')).toHaveCount(0)
})

test('second tab waits for Media lease', async ({ page }, info) => {
  laptop(info)
  await chat(page)
  await page.route(/\/api\/v1\/media\/uploads\/[^/]+\/content$/, route => route.abort('failed'))
  const other = await page.context().newPage()
  await chat(other)
  await page.goto('/'); await other.goto('/')
  const file = pngFile('same.png')
  await attach(page, file)
  await send(page)
  await warn(page, 'тот же файл')
  const id = (await pending(page))[0].operationId
  await attach(other, file)
  await expect(alert(other)).toContainText('другой вкладке')
  await expect(previews(other)).toHaveCount(0)
  await page.goto('/gallery')
  await attach(other, file)
  await expect(previews(other)).toHaveCount(1)
  expect((await pending(other))[0].operationId).toBe(id)
})

test('price rechecked after image upload', async ({ page }, info) => {
  laptop(info)
  const { admitted } = await chat(page)
  let revision = visionPolicy.revision, reads = 0
  await page.route('**/api/v1/chat/policy', route => { reads++
    return route.fulfill({ json: { ...visionPolicy, revision } }) })
  await page.route('**/api/v1/media/uploads', route => {
    if (route.request().method() === 'POST') revision = 'new-price'
    return route.fallback()
  })
  await page.goto('/')
  await attach(page, pngFile('price.png'))
  await send(page)
  await warn(page, 'Модели или цены изменились')
  expect(reads).toBeGreaterThanOrEqual(3)
  expect(admitted).toHaveLength(0)
  await send(page)
  await accepted(admitted)
})

test('no Web Locks blocks upload', async ({ page }, info) => {
  laptop(info)
  await chat(page)
  await page.addInitScript(() => Object.defineProperty(navigator, 'locks', { value: undefined }))
  await page.goto('/')
  await attach(page, pngFile('safe.png'))
  await warn(page, 'не поддерживает безопасное восстановление')
})

test('unknown admission keeps draft and exact ID', async ({ page }, info) => {
  laptop(info)
  const { admitted } = await chat(page, true)
  let first = true, revision = visionPolicy.revision
  const ids: string[] = []
  await page.route('**/api/v1/chat/policy', route => route.fulfill({ json: { ...visionPolicy, revision } }))
  await page.route(`**/api/v1/chat/threads/${visionThread.id}/requests`, route => {
    ids.push(route.request().postDataJSON().request_id)
    if (first) { first = false; return route.abort('failed') }
    return route.fallback()
  })
  await page.route('**/api/v1/chat/requests/*', route => route.fulfill({ status: 404, json: {} }))
  await page.goto('/')
  await attach(page, pngFile('pending.png'))
  await page.getByRole('textbox', { name: 'Сообщение' }).fill('текст')
  await send(page)
  await warn(page, 'Приём неизвестен')
  await count(page, 1)
  await button(page, 'Новый чат').click()
  await count(page, 1)
  await page.locator('.chat-sidebar').getByRole('button', { name: visionThread.title }).click()
  await count(page, 1)
  await expect(page.getByRole('textbox', { name: 'Сообщение' })).toHaveValue('текст')
  expect(ids).toHaveLength(1)
  revision = 'new-price'
  await send(page)
  await expect(page.locator('.chat-voice-error')).toContainText('Модели или цены изменились')
  await send(page)
  await accepted(admitted)
  expect(ids[1]).toBe(ids[0])
})
