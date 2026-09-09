import { createHash } from 'node:crypto'
import { test, expect } from '@playwright/test'
import { workspace, asset, create, noOverflow, hash } from './workspace-fixtures'

test('IMAGE-001 gallery empty state has no invented works or original prefetch', async ({ page }) => {
  const app = await workspace(page)
  await page.goto('/gallery')
  await expect(page.getByRole('heading', { name: 'Здесь начнётся ваша коллекция' })).toBeVisible()
  expect(app.contentReads).toBe(0)
  await expect(page.locator('.asset-card')).toHaveCount(0)
  await noOverflow(page)
})

test('IMAGE-001 own list, page search, protected preview and server download', async ({ page }, info) => {
  const app = await workspace(page)
  await create(page)
  await page.goto('/gallery')
  await expect(page.locator('.asset-card')).toHaveCount(1)
  expect(app.contentReads).toBe(0)
  await page.getByLabel('Поиск на этой странице').fill('неттакого')
  await expect(page.getByRole('heading', { name: 'Ничего не найдено на этой странице' })).toBeVisible()
  await page.getByRole('button', { name: 'Сбросить поиск' }).click()
  await page.locator('.asset-card').click()
  await expect(page.getByTestId('private-image')).toBeVisible()
  const previewTicketCount = app.tickets
  const previewContentReads = app.contentReads
  const waiting = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Скачать PNG' }).click()
  const download = await waiting
  const stream = await download.createReadStream()
  expect(stream).not.toBeNull()
  const digest = createHash('sha256')
  for await (const chunk of stream!) digest.update(chunk)
  expect(digest.digest('hex')).toBe(hash)
  expect(app.tickets).toBe(previewTicketCount + 1)
  expect(app.contentReads).toBe(previewContentReads + 1)
  await noOverflow(page)
  await page.screenshot({ path: info.outputPath('server-asset.png'), fullPage: true })
  await page.reload()
  await expect(page.getByTestId('private-image')).toBeVisible()
})

test('IMAGE-001 gallery pagination is explicit and never fetches all originals', async ({ page }) => {
  const app = await workspace(page)
  for (let i = 0; i < 21; i++) app.assets.push(asset())
  await page.goto('/gallery')
  await expect(page.locator('.asset-card')).toHaveCount(20)
  await page.getByRole('button', { name: 'Следующая страница' }).click()
  await expect(page.locator('.asset-card')).toHaveCount(1)
  await page.getByRole('button', { name: 'Предыдущая страница' }).click()
  await expect(page.locator('.asset-card')).toHaveCount(20)
  expect(app.contentReads).toBe(0)
  await noOverflow(page)
})

test('IMAGE-001 gallery error cannot fall back to old demo data', async ({ page }) => {
  const app = await workspace(page); app.assets.push(asset())
  await page.goto('/gallery')
  await expect(page.locator('.asset-card')).toHaveCount(1)
  app.assetError = 'unavailable'
  await page.getByRole('button', { name: 'Обновить галерею' }).click()
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.locator('.asset-card')).toHaveCount(0)
  app.assetError = ''
  await page.getByRole('button', { name: 'Повторить загрузку' }).click()
  await expect(page.locator('.asset-card')).toHaveCount(1)
})

test('IMAGE-001 missing or foreign identifiers never fetch image contents', async ({ page }) => {
  const app = await workspace(page)
  await page.goto('/gallery/22222222-2222-4222-8222-222222222222')
  await expect(page.getByRole('alert')).toContainText('недоступен')
  await expect(page.getByTestId('private-image')).toHaveCount(0)
  await page.goto('/gallery/not-an-id')
  await expect(page.getByRole('heading', { name: 'Работа не найдена' })).toBeVisible()
  expect(app.contentReads).toBe(0)
})

test('IMAGE-001 malformed ticket and corrupt bytes never become visible pixels', async ({ page }) => {
  const app = await workspace(page); const item = asset(); app.assets.push(item)
  app.evilTicket = true
  await page.goto(`/gallery/${item.id}`)
  await expect(page.locator('.private-image').getByRole('alert')).toBeVisible()
  expect(app.contentReads).toBe(0)
  app.evilTicket = false; app.badImage = true
  await page.getByRole('button', { name: 'Повторить предпросмотр' }).click()
  await expect(page.locator('.private-image').getByRole('alert')).toBeVisible()
  await expect(page.getByTestId('private-image')).toHaveCount(0)
  app.badImage = false
  await page.getByRole('button', { name: 'Повторить предпросмотр' }).click()
  await expect(page.getByTestId('private-image')).toBeVisible()
})

test('IMAGE-001 navigation releases private object URL; signout clears loaded work', async ({ page }) => {
  const app = await workspace(page); const item = asset(); app.assets.push(item)
  await page.addInitScript(() => {
    const original = URL.revokeObjectURL
    const counter = Object.assign(window, { revokedImages: 0 })
    URL.revokeObjectURL = function (url) {
      counter.revokedImages++
      original.call(URL, url)
    }
  })
  await page.goto(`/gallery/${item.id}`)
  await expect(page.getByTestId('private-image')).toBeVisible()
  await page.getByRole('link', { name: 'Мои работы', exact: true }).click()
  expect(await page.evaluate(() => Number(Reflect.get(window, 'revokedImages')))).toBeGreaterThan(0)
  await page.locator('.asset-card').click()
  await expect(page.getByTestId('private-image')).toBeVisible()
  app.signedIn = false
  await page.evaluate(() => window.dispatchEvent(new Event('focus')))
  await expect(page.getByRole('heading', { name: 'Войдите, чтобы продолжить' })).toBeVisible()
  await expect(page.getByTestId('private-image')).toHaveCount(0)
})

test('IMAGE-001 zero balance still reads own files and theme persists', async ({ page }) => {
  const app = await workspace(page); app.balance = 0; app.assets.push(asset())
  await page.goto('/gallery')
  await expect(page.locator('.asset-card')).toHaveCount(1)
  await page.getByRole('button', { name: 'Переключить тему' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.locator('.asset-card')).toHaveCount(1)
  expect(app.requests.filter(r => r.path === '/api/v1/credits')).toHaveLength(0)
})


test('IMAGE-001 download rechecks bytes and refuses a damaged file even with a loaded preview', async ({ page }) => {
  const app = await workspace(page); const item = asset(); app.assets.push(item)
  await page.goto(`/gallery/${item.id}`)
  await expect(page.getByTestId('private-image')).toBeVisible()
  app.badImage = true
  const downloads: string[] = []
  page.on('download', file => downloads.push(file.url()))
  await page.getByRole('button', { name: 'Скачать PNG' }).click()
  await expect(page.locator('.asset-information').getByRole('alert')).toBeVisible()
  expect(app.contentReads).toBe(2)
  expect(downloads).toHaveLength(0)
})
