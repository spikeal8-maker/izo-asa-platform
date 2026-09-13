import { expect, test } from '@playwright/test'
import { workspace } from './workspace-fixtures'

async function create(page: import('@playwright/test').Page) {
  await page.goto('/image')
  await page.getByLabel('Описание').fill('red cube on white')
  await page.getByRole('button', { name: 'Рассчитать стоимость' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: 'Подтвердить создание' }).click()
  await expect(page.getByTestId('job-status')).toBeVisible()
}

test('IMAGE-001 studio uses server account, plan and price on every viewport', async ({ page }) => {
  const app = await workspace(page)
  await page.goto('/image')
  await expect(page.getByTestId('studio-available')).toHaveText('20')
  await expect(page.getByLabel('Режим')).toHaveValue('test.image.v1')
  await page.getByLabel('Описание').fill('red cube on white')
  await page.getByRole('button', { name: 'Рассчитать стоимость' }).click()
  await expect(page.getByRole('dialog')).toContainText('1 балл')
  expect(app.quoteRequests).toBe(1)
})

test('IMAGE-001 explicit submit is idempotent and server result survives refresh', async ({ page }) => {
  const app = await workspace(page)
  await create(page)
  expect(app.jobs).toHaveLength(1)
  const original = app.jobs[0].id
  await page.reload()
  await expect(page.getByTestId('job-status')).toBeVisible()
  expect(app.jobs[0].id).toBe(original)
})

test('IMAGE-001 lost submit response restores the same command after reload', async ({ page }) => {
  const app = await workspace(page)
  app.failSubmitAfterAdmission = true
  await page.goto('/image')
  await page.getByLabel('Описание').fill('red cube on white')
  await page.getByRole('button', { name: 'Рассчитать стоимость' }).click()
  await page.getByRole('button', { name: 'Подтвердить создание' }).click()
  await expect(page.getByText('Результат отправки пока неизвестен')).toBeVisible()
  const id = app.jobs[0].id
  app.failSubmitAfterAdmission = false
  await page.reload()
  await page.getByRole('button', { name: 'Проверить прежний запрос' }).click()
  await expect(page.getByTestId('job-status')).toBeVisible()
  expect(app.jobs).toHaveLength(1)
  expect(app.jobs[0].id).toBe(id)
})

test('IMAGE-001 disabled storage prevents sending an unremembered request', async ({ page }) => {
  const app = await workspace(page)
  await page.addInitScript(() => {
    const original = Storage.prototype.setItem
    Storage.prototype.setItem = function (key, value) {
      if (key.includes('pending')) throw new DOMException('denied')
      return original.call(this, key, value)
    }
  })
  await page.goto('/image')
  await page.getByLabel('Описание').fill('red cube on white')
  await page.getByRole('button', { name: 'Рассчитать стоимость' }).click()
  await page.getByRole('button', { name: 'Подтвердить создание' }).click()
  await expect(page.getByText('Не удалось сохранить номер запроса')).toBeVisible()
  expect(app.jobs).toHaveLength(0)
})

test('IMAGE-001 corrupted pending record blocks mutation instead of inventing another ID', async ({ page }) => {
  const app = await workspace(page)
  await page.addInitScript(() => localStorage.setItem('izo:pending-job', '{bad'))
  await page.goto('/image')
  await expect(page.getByText('Хранилище номера запроса недоступно или повреждено.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Рассчитать стоимость' })).toBeDisabled()
  expect(app.jobs).toHaveLength(0)
})

test('IMAGE-001 zero balance is server denial, not access loss to gallery', async ({ page }) => {
  const app = await workspace(page); app.balance = 0
  await page.goto('/image')
  await expect(page.getByTestId('studio-available')).toHaveText('0')
  await page.getByLabel('Описание').fill('red cube')
  await page.getByRole('button', { name: 'Рассчитать стоимость' }).click()
  await expect(page.getByRole('alert')).toContainText('Недостаточно баллов')
  await page.goto('/gallery')
  await expect(page.getByTestId('gallery-used')).toBeVisible()
})

test('IMAGE-001 cancellation uses server state and never settles locally', async ({ page }) => {
  const app = await workspace(page)
  await create(page)
  app.jobs[0].status = 'reconciling'; app.jobs[0].cancel_requested = false
  await page.reload()
  await page.getByRole('button', { name: 'Отменить задание' }).click()
  await expect(page.getByTestId('job-status')).toHaveText('Уточняем результат')
  expect(app.jobs[0].cancel_requested).toBe(true)
})

test('IMAGE-001 exhausted reconciliation does not start a new job or pretend refund', async ({ page }) => {
  const app = await workspace(page)
  await create(page)
  app.jobs[0].status = 'reconciling'; app.jobs[0].error_code = 'reconciliation_required'
  app.jobs[0].asset_id = null; app.jobs[0].charged_credits = 0; app.jobs[0].reserved_credits = 7
  await page.reload()
  await expect(page.getByTestId('job-status')).toHaveText('Уточняем результат')
  await expect(page.locator('.job-record')).toContainText('Нужен разбор оператором. Резерв сохранён.')
  await expect(page.getByRole('link', { name: 'Открыть работу', exact: true })).toHaveCount(0)
  expect(app.jobs).toHaveLength(1)
})

test('IMAGE-001 guest trial replaces the legacy login wall while unverified accounts remain blocked', async ({ page }) => {
  const app = await workspace(page); app.signedIn = false
  await page.goto('/image')
  await expect(page.getByRole('heading', { name: 'Попробуйте без регистрации' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Создать пробную работу' })).toBeVisible()
  await expect(page.getByTestId('studio-available')).toHaveCount(0)
  app.signedIn = true; app.account.email_verified = false
  await page.reload()
  await expect(page.getByRole('link', { name: 'Подтвердите почту' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Рассчитать стоимость' })).toBeDisabled()
  expect(app.jobs).toHaveLength(0)
})

test('IMAGE-001 failure removes stale private job data and retry reads server again', async ({ page }) => {
  const app = await workspace(page)
  await create(page)
  app.signedIn = false
  await page.getByRole('button', { name: 'Обновить задание' }).click()
  await expect(page.getByRole('heading', { name: 'Войдите, чтобы продолжить' })).toBeVisible()
  await expect(page.getByTestId('job-status')).toHaveCount(0)
  await expect(page.getByTestId('job-charged')).toHaveCount(0)
})

test('CHANGE-001 A confirmation shows the server reserve beside the touch action', async ({ page }) => {
  await workspace(page)
  await page.goto('/image')
  await page.getByLabel('Описание').fill('red cube on white')
  await page.getByRole('button', { name: 'Рассчитать стоимость' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('1 балл', { exact: false })).toBeVisible()
  await expect(dialog.getByRole('button', { name: 'Подтвердить создание' })).toBeVisible()
})

test('CHANGE-001 C failure classification requires the exact pre-admission protocol', async ({ page }) => {
  await page.goto('/image')
  await page.evaluate(() => {
    localStorage.setItem('izo:pending-job', JSON.stringify({ quote_id: 'bad', operation_id: crypto.randomUUID() }))
  })
  await page.reload()
  await expect(page.getByText('Хранилище номера запроса недоступно или повреждено.')).toBeVisible()
})

test('CHANGE-001 C definite rejections free only the pending ID and never create a job', async ({ page }) => {
  const app = await workspace(page); app.submitReject = 'quote_expired'
  await page.goto('/image')
  await page.getByLabel('Описание').fill('red cube')
  await page.getByRole('button', { name: 'Рассчитать стоимость' }).click()
  await page.getByRole('button', { name: 'Подтвердить создание' }).click()
  await expect(page.getByRole('alert')).toContainText('Цена устарела')
  expect(app.jobs).toHaveLength(0)
})

test('CHANGE-001 C a familiar code inside server failure still reuses the pending ID', async ({ page }) => {
  const app = await workspace(page); app.submitReject = 'internal_quote_expired'
  await page.goto('/image')
  await page.getByLabel('Описание').fill('red cube')
  await page.getByRole('button', { name: 'Рассчитать стоимость' }).click()
  await page.getByRole('button', { name: 'Подтвердить создание' }).click()
  await expect(page.getByText('Результат отправки пока неизвестен')).toBeVisible()
})
