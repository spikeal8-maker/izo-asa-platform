// IMAGE-001: actual built browser -> API -> PostgreSQL/S3 -> separate worker.
// No API fulfillment mocks. The only route rule blocks accidental external egress.
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { chromium, expect } from '@playwright/test'

if (process.env.IZO_ENVIRONMENT !== 'test' || process.env.IZO_IMAGE_ACCEPTANCE !== 'isolated')
  throw new Error('Explicit isolated image stack required')
const phase = process.argv[3]
if (!['before', 'after'].includes(phase)) throw new Error('Expected before or after')
const file = process.argv[2]
const raw = await readFile(file, 'utf8')
if (raw.length > 65536) throw new Error('Fixture exceeds limit')
const state = JSON.parse(raw)
const origin = 'http://localhost:8080'
const evidence = 'apps/web/test-results/image-live'
await mkdir(evidence, { recursive: true })
const browser = await chromium.launch()
async function context() {
  const result = await browser.newContext({ baseURL: origin, viewport: { width: 1440, height: 900 } })
  await result.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort())
  return result
}
async function login(page, user) {
  await page.goto('/login')
  await page.getByLabel('Электронная почта').fill(user.email)
  await page.getByLabel('Пароль', { exact: true }).fill(user.password)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await page.waitForURL('**/account')
  await expect(page.getByTestId('server-account')).toBeVisible()
}
async function downloadedHash(page) {
  const waiting = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Скачать PNG' }).click()
  const download = await waiting
  const stream = await download.createReadStream()
  if (!stream) throw new Error('No downloaded file')
  const hash = createHash('sha256')
  let bytes = 0
  for await (const chunk of stream) { bytes += chunk.length; hash.update(chunk) }
  if (bytes < 8 || bytes > 1000000) throw new Error('Unexpected test image size')
  return hash.digest('hex')
}
try {
  if (phase === 'before') {
    const staff = await context(), page = await staff.newPage()
    await login(page, state.operator)
    await page.goto('/admin/users')
    await page.getByLabel('Имя или публичный код').fill(state.recipient.public_code)
    await page.getByRole('button', { name: 'Найти пользователя' }).click()
    await page.getByRole('link', { name: 'Открыть карточку' }).click()
    await expect(page.getByTestId('admin-available')).toHaveText('0')
    await page.getByLabel('Номер заявки').fill(state.case)
    await page.getByLabel('Количество баллов').fill('5')
    await page.getByRole('button', { name: 'Проверить начисление' }).click()
    const dialog = page.getByRole('dialog', { name: 'Подтверждение компенсации' })
    await dialog.getByLabel('Текущий пароль администратора').fill(state.operator.password)
    await dialog.getByRole('button', { name: 'Подтвердить начисление' }).click()
    await expect(page.locator('.admin-receipt')).toContainText('Начислено 5 баллов')
    await staff.close()
    const user = await context(), studio = await user.newPage()
    await login(studio, state.recipient)
    await studio.goto('/image')
    await expect(studio.getByTestId('studio-available')).toHaveText('5')
    await studio.getByLabel('Описание', { exact: true }).fill('Сквозная проверка серверной студии')
    await studio.screenshot({ path: evidence + '/studio-real-desktop.png', fullPage: true })
    await studio.getByRole('button', { name: 'Рассчитать стоимость' }).click()
    await expect(studio.getByRole('dialog')).toContainText('1 балл.')
    await studio.getByRole('button', { name: 'Подтвердить создание' }).click()
    await studio.waitForURL('**/jobs/*')
    await expect(studio.getByTestId('job-status')).toHaveText('В очереди')
    const jobId = new URL(studio.url()).pathname.split('/').at(-1)
    // No network provider and no worker HTTP endpoints. Process is started by
    // the explicitly opted-in CI harness after UI has persisted the request.
    execFileSync('docker', ['compose', 'run', '--rm', '--no-deps', '-T', '-e', 'IZO_ENVIRONMENT=test',
      '-e', 'IZO_JOBS_ENABLED=true', 'api', 'python', '-m', 'izo.jobs.worker', '--once', '--worker-id', 'image-browser'],
      { timeout: 60000, stdio: 'pipe' })
    await expect(studio.getByTestId('job-status')).toHaveText('Готово', { timeout: 20000 })
    await expect(studio.getByTestId('job-charged')).toHaveText('1')
    await studio.reload()
    await expect(studio.getByTestId('job-status')).toHaveText('Готово')
    await studio.getByRole('link', { name: 'Открыть работу', exact: true }).click()
    await expect(studio.getByTestId('private-image')).toBeVisible()
    const assetId = new URL(studio.url()).pathname.split('/').at(-1)
    const sha256 = await downloadedHash(studio)
    await studio.screenshot({ path: evidence + '/asset-real-desktop.png', fullPage: true })
    await studio.setViewportSize({ width: 390, height: 844 })
    await expect.poll(() => studio.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await studio.screenshot({ path: evidence + '/asset-real-phone.png', fullPage: true })
    await studio.goto('/gallery')
    await expect(studio.locator('.asset-card')).toHaveCount(1)
    await studio.goto('/account/credits')
    await expect(studio.getByTestId('own-available')).toHaveText('4')
    state.browser = { job_id: jobId, asset_id: assetId, sha256 }
    await writeFile(file, JSON.stringify(state), { mode: 0o600 })
    await user.close()
    console.log('IMAGE_BROWSER_BEFORE_OK: real grant -> quote -> submit -> separate worker -> result -> download -> gallery -> balance4')
  } else {
    const user = await context(), page = await user.newPage()
    await login(page, state.recipient)
    await page.goto('/jobs/' + state.browser.job_id)
    await expect(page.getByTestId('job-status')).toHaveText('Готово')
    await page.getByRole('link', { name: 'Открыть работу', exact: true }).click()
    await expect(page.getByTestId('private-image')).toBeVisible()
    expect(await downloadedHash(page)).toBe(state.browser.sha256)
    await page.setViewportSize({ width: 3840, height: 2160 })
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: evidence + '/asset-real-4k-after-restart.png', fullPage: true })
    await page.goto('/gallery')
    await expect(page.locator('.asset-card')).toHaveCount(1)
    await user.close()
    const other = await context(), outsider = await other.newPage()
    await login(outsider, state.other)
    await outsider.goto('/gallery/' + state.browser.asset_id)
    await expect(outsider.getByRole('alert')).toContainText('недоступен')
    await expect(outsider.getByTestId('private-image')).toHaveCount(0)
    await outsider.goto('/jobs/' + state.browser.job_id)
    await expect(outsider.getByRole('alert')).toContainText('недоступен')
    await expect(outsider.getByTestId('job-charged')).toHaveCount(0)
    await other.close()
    console.log('IMAGE_BROWSER_AFTER_OK: same job and downloaded hash after Compose restart, QHD/4K layout, foreign job/asset denied')
  }
} finally { await browser.close() }
