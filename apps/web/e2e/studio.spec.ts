import { test, expect } from '@playwright/test'
import { fakeApi, createWork, noOverflow } from './demo-fixture'
import { freshState, restoreDemo, settleDemo, DEMO_KEY } from '../src/features/prototype/demo'

test.beforeEach(async ({ page }) => { await fakeApi(page) })

test('U-10 @smoke studio is explicit demo, responsive and free of console errors', async ({ page }, info) => {
  const errors: string[] = []
  page.on('pageerror', e => errors.push(e.message))
  await page.goto('/image')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Ваша идея')
  await expect(page.getByRole('button', { name: /Создать демо/ })).toBeDisabled()
  await expect(page.getByText('ПРИМЕР · НЕ AI-ГЕНЕРАЦИЯ', { exact: true })).toBeVisible()
  await noOverflow(page)
  expect(errors).toEqual([])
  await page.screenshot({ path: info.outputPath('studio.png'), fullPage: true })
  await info.attach('display-profile', { body: JSON.stringify({ project: info.project.name, viewport: page.viewportSize(), dpr: await page.evaluate(() => devicePixelRatio), browser: 'Chromium', zoom: 'browser default; OS scaling not emulated' }), contentType: 'application/json' })
})

test('U-18 demo reservation settles once, survives reload, and makes no AI submission', async ({ page }) => {
  const mutations: string[] = []
  page.on('request', r => { if (r.method() !== 'GET') mutations.push(r.url()) })
  await createWork(page)
  await expect(page.getByRole('button', { name: 'Демо-баланс: 40 баллов', exact: true })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('button', { name: 'Демо-баланс: 40 баллов', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Открыть работу', exact: false }).click()
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Тестовая архитектурная')
  await expect(page.getByRole('link', { name: 'Скачать SVG-пример' })).toHaveAttribute('download', 'izo-demo-example.svg')
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: 'Скачать SVG-пример' }).click()])
  expect(download.suggestedFilename()).toBe('izo-demo-example.svg')
  expect(mutations).toEqual([])
  await noOverflow(page)
})

test('D-01 model capabilities, focus return, aspect, and local price', async ({ page }) => {
  await page.goto('/image')
  const picker = page.getByRole('button', { name: /Studio · API/ })
  await picker.click()
  await expect(page.getByRole('button', { name: /Следующая модель/ })).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(picker).toBeFocused()
  await picker.click()
  await page.getByRole('button', { name: /Studio · Local/ }).click()
  await page.getByRole('button', { name: '16:9', exact: true }).click()
  await expect(page.getByRole('button', { name: '16:9', exact: true })).toHaveAttribute('aria-pressed', 'true')
  await page.getByLabel('Описание', { exact: true }).fill('Локальный макет')
  await expect(page.getByRole('button', { name: /Создать демо/ })).toContainText('4 балла')
  await noOverflow(page)
})

test('U-18 controlled failure and cancellation do not spend demo balance', async ({ page }) => {
  const date = new Date('2026-09-01T00:00:00Z')
  await page.clock.install({ time: date })
  await page.clock.pauseAt(new Date(date.getTime() + 1000))
  await page.goto('/image')
  await page.getByLabel('Описание', { exact: true }).fill('Проверка ошибки')
  await page.getByText('Проверка состояний макета', { exact: true }).click()
  await page.getByLabel('Показать ошибку вместо успеха').check()
  await page.getByRole('button', { name: /Создать демо/ }).click()
  await page.getByRole('button', { name: 'Подтвердить демо-запуск' }).click()
  await expect(page.getByText('Проверяем сценарий ожидания')).toBeVisible()
  await page.clock.runFor(1800)
  await expect(page.getByText('Тестовая ошибка провайдера')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Демо-баланс: 48 баллов' })).toBeVisible()
  await page.getByLabel('Показать ошибку вместо успеха').uncheck()
  await page.getByRole('button', { name: /Создать демо/ }).click()
  await page.getByRole('button', { name: 'Подтвердить демо-запуск' }).click()
  await page.getByRole('button', { name: 'Отменить демо', exact: true }).click()
  await page.getByRole('button', { name: 'Да, отменить демо' }).click()
  await page.clock.runFor(1800)
  await expect(page.getByText('Демо отменено', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Демо-баланс: 48 баллов' })).toBeVisible()
})

test('D-02 invalid local image is rejected without upload', async ({ page }) => {
  await page.goto('/image')
  await page.getByLabel('Выбрать исходное изображение').setInputFiles({ name: 'bad.png', mimeType: 'image/png', buffer: Buffer.from('not an image') })
  await expect(page.getByRole('alert')).toContainText('не удалось прочитать')
  await expect(page.getByText('Только предпросмотр в браузере.', { exact: false })).toBeVisible()
})

test('demo parsing, idempotent settlement, and damaged storage are bounded', async ({ page }) => {
  expect(restoreDemo('{broken')).toEqual(freshState())
  expect(restoreDemo(JSON.stringify({ ...freshState(), balance: -5 }))).toEqual(freshState())
  const state = freshState()
  state.job = { ...state.draft, prompt: 'fixture', id: 'demo-00000000-0000-0000-0000-000000000000', startedAt: 0, cost: 8, state: 'running', fail: false }
  const completed = settleDemo(state, 2000)
  expect(completed.balance).toBe(40)
  expect(completed.works).toHaveLength(1)
  expect(settleDemo(completed, 5000)).toBe(completed)
  await page.addInitScript(key => sessionStorage.setItem(key, '{broken'), DEMO_KEY)
  await page.goto('/image')
  await expect(page.getByRole('button', { name: 'Демо-баланс: 48 баллов' })).toBeVisible()
})
