import { test, expect } from '@playwright/test'
import { ApiError } from '../src/shared/api'
import { rejectedBeforeAdmission } from '../src/shared/submission'
import { workspace, estimate, create, noOverflow, owner } from './workspace-fixtures'

test('IMAGE-001 studio uses server account, plan and price on every viewport', async ({ page }, info) => {
  const app = await workspace(page)
  await estimate(page, 'Длинное описание по-русски. '.repeat(20))
  await expect(page.getByRole('dialog')).toContainText('7 балл.')
  expect(app.requests.filter(r => r.path === '/api/v1/jobs')).toHaveLength(0)
  const quote = app.requests.find(r => r.path === '/api/v1/jobs/quotes')!
  expect(Object.keys(quote.body!).sort()).toEqual(['capability_id', 'height', 'prompt', 'width'])
  await page.getByRole('button', { name: 'Закрыть диалог' }).click()
  await noOverflow(page)
  await page.screenshot({ path: info.outputPath('server-studio.png'), fullPage: true })
})

test('IMAGE-001 explicit submit is idempotent and server result survives refresh', async ({ page }) => {
  const app = await workspace(page)
  await estimate(page)
  await page.getByRole('button', { name: 'Подтвердить создание' }).evaluate(node => {
    (node as HTMLButtonElement).click(); (node as HTMLButtonElement).click()
  })
  await expect(page.getByTestId('job-status')).toHaveText('Готово')
  const calls = app.requests.filter(r => r.path === '/api/v1/jobs' && r.method === 'POST')
  expect(calls).toHaveLength(1)
  expect(Object.keys(calls[0].body!).sort()).toEqual(['operation_id', 'quote_id'])
  await expect(page.getByTestId('job-charged')).toHaveText('7')
  await page.reload()
  await expect(page.getByTestId('job-status')).toHaveText('Готово')
  expect(app.jobs).toHaveLength(1); expect(app.balance).toBe(93)
  await page.getByRole('link', { name: 'Открыть работу', exact: true }).click()
  await expect(page.getByTestId('private-image')).toBeVisible()
})

test('IMAGE-001 lost submit response restores the same command after reload', async ({ page }) => {
  const app = await workspace(page); app.uncertainOnce = true
  await estimate(page)
  await page.getByRole('button', { name: 'Подтвердить создание' }).click()
  await expect(page.getByRole('alert')).toContainText('Результат отправки пока неизвестен')
  await page.reload()
  await expect(page.getByRole('button', { name: 'Рассчитать стоимость' })).toBeDisabled()
  await page.getByRole('button', { name: 'Проверить прежний запрос' }).click()
  await expect(page.getByTestId('job-status')).toHaveText('Готово')
  const calls = app.requests.filter(r => r.path === '/api/v1/jobs' && r.method === 'POST')
  expect(calls).toHaveLength(2); expect(calls[0].body).toEqual(calls[1].body)
  expect(app.jobs).toHaveLength(1); expect(app.balance).toBe(93)
  expect(await page.evaluate(id => sessionStorage.getItem(`izo-pending-submit:${id}`), owner)).toBeNull()
})

test('IMAGE-001 disabled storage prevents sending an unremembered request', async ({ page }) => {
  const app = await workspace(page)
  await page.addInitScript(() => {
    const original = Storage.prototype.setItem
    Storage.prototype.setItem = function (key, value) {
      if (key.startsWith('izo-pending-submit:')) throw new DOMException('denied', 'SecurityError')
      original.call(this, key, value)
    }
  })
  await estimate(page)
  await page.getByRole('button', { name: 'Подтвердить создание' }).click()
  await expect(page.getByText('Не удалось сохранить номер запроса. Отправка задания не выполнялась.', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Рассчитать стоимость' })).toBeDisabled()
  expect(app.requests.filter(r => r.path === '/api/v1/jobs' && r.method === 'POST')).toHaveLength(0)
})

test('IMAGE-001 corrupted pending record blocks mutation instead of inventing another ID', async ({ page }) => {
  const app = await workspace(page)
  await page.addInitScript(id => sessionStorage.setItem(`izo-pending-submit:${id}`, '{broken'), owner)
  await page.goto('/image')
  await expect(page.getByRole('alert')).toContainText('повреждено')
  await expect(page.getByRole('button', { name: 'Рассчитать стоимость' })).toBeDisabled()
  expect(app.jobs).toHaveLength(0)
})

test('IMAGE-001 zero balance is server denial, not access loss to gallery', async ({ page }) => {
  const app = await workspace(page); app.balance = 0; app.quoteError = 'insufficient_credits'
  await page.goto('/image')
  await expect(page.getByTestId('studio-available')).toHaveText('0')
  await page.getByLabel('Описание', { exact: true }).fill('Проверка')
  await page.getByRole('button', { name: 'Рассчитать стоимость' }).click()
  await expect(page.getByRole('alert')).toContainText('Недостаточно баллов')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await page.getByRole('navigation').getByRole('link', { name: 'Галерея', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Здесь начнётся ваша коллекция' })).toBeVisible()
  expect(app.jobs).toHaveLength(0)
})

test('IMAGE-001 cancellation uses server state and never settles locally', async ({ page }) => {
  const app = await workspace(page); app.autoFinish = false
  await estimate(page)
  await page.getByRole('button', { name: 'Подтвердить создание' }).click()
  await expect(page.getByTestId('job-status')).toHaveText('В очереди')
  await page.getByRole('button', { name: 'Отменить задание', exact: true }).click()
  await page.getByRole('button', { name: 'Подтвердить отмену' }).click()
  await expect(page.getByTestId('job-status')).toHaveText('Отменено')
  expect(app.balance).toBe(100); expect(app.reserved).toBe(0)
  expect(app.requests.filter(r => r.path.endsWith('/cancel'))).toHaveLength(1)
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

test('IMAGE-001 guest and unverified identity never submit using platform hints', async ({ page }) => {
  const app = await workspace(page); app.signedIn = false
  await page.goto('/image')
  await expect(page.getByRole('heading', { name: 'Войдите, чтобы продолжить' })).toBeVisible()
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


test('CHANGE-001 A confirmation shows the server reserve beside the touch action', async ({ page }, info) => {
  const app = await workspace(page); app.cost = 19
  await estimate(page)
  const dialog = page.getByRole('dialog')
  const confirm = dialog.getByRole('button', { name: 'Подтвердить создание', exact: true })
  await expect(confirm.getByTestId('quote-submit-price')).toHaveText('Резерв: 19 балл.')
  await expect(confirm).toHaveAttribute('aria-describedby', 'quote-reserve')
  await expect(dialog.locator('#quote-reserve')).toHaveText('19 балл.')
  await confirm.scrollIntoViewIfNeeded()
  const box = (await confirm.boundingBox())!, panel = (await dialog.boundingBox())!
  expect(box.height).toBeGreaterThanOrEqual(48)
  expect(box.x).toBeGreaterThanOrEqual(panel.x)
  expect(box.x + box.width).toBeLessThanOrEqual(panel.x + panel.width + 1)
  if (page.viewportSize()!.width <= 700) {
    const title = (await confirm.getByText('Подтвердить создание', { exact: true }).boundingBox())!
    const price = (await confirm.getByTestId('quote-submit-price').boundingBox())!
    expect(price.y).toBeGreaterThanOrEqual(title.y + title.height)
  }
  expect(app.jobs).toHaveLength(0)
  await noOverflow(page)
  await page.screenshot({ path: info.outputPath('confirmation-price.png'), fullPage: true })
})


test('CHANGE-001 C failure classification requires the exact pre-admission protocol', () => {
  for (const code of ['provider_unavailable', 'image_size_restricted', 'action_budget_exceeded']) {
    expect(rejectedBeforeAdmission(new ApiError(409, code))).toBe(true)
    expect(rejectedBeforeAdmission(new ApiError(500, code))).toBe(false)
    expect(rejectedBeforeAdmission(new ApiError(503, code))).toBe(false)
  }
  for (const code of ['idempotency_conflict', 'quote_already_used', 'unknown', 'toString', '__proto__']) {
    expect(rejectedBeforeAdmission(new ApiError(409, code))).toBe(false)
  }
  expect(rejectedBeforeAdmission(new Error('connection lost'))).toBe(false)
  expect(rejectedBeforeAdmission({ status: 409, code: 'plan_restricted' })).toBe(false)
})

test('CHANGE-001 C definite rejections free only the pending ID and never create a job', async ({ page }) => {
  const app = await workspace(page)
  let code = ''; let submissions = 0
  await page.route('**/api/v1/jobs', route => {
    if (route.request().method() !== 'POST') return route.fallback()
    submissions++
    return route.fulfill({ status: 409, json: { error: { code } } })
  })
  for (const [next, text] of [
    ['provider_unavailable', 'Исполнитель сейчас недоступен'],
    ['image_size_restricted', 'Этот размер не разрешён'],
    ['action_budget_exceeded', 'Стоимость превышает лимит'],
  ]) {
    code = next
    await estimate(page)
    await page.getByRole('button', { name: 'Подтвердить создание', exact: true }).click()
    await expect(page.getByRole('alert')).toContainText(text)
    await expect(page.getByRole('button', { name: 'Проверить прежний запрос' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: 'Рассчитать стоимость' })).toBeEnabled()
    expect(await page.evaluate(id => sessionStorage.getItem(`izo-pending-submit:${id}`), owner)).toBeNull()
  }
  expect(submissions).toBe(3)
  expect(app.jobs).toHaveLength(0); expect(app.balance).toBe(100); expect(app.reserved).toBe(0)
})

test('CHANGE-001 C a familiar code inside server failure still reuses the pending ID', async ({ page }) => {
  const app = await workspace(page); const calls: unknown[] = []
  await page.route('**/api/v1/jobs', route => {
    if (route.request().method() !== 'POST') return route.fallback()
    calls.push(route.request().postDataJSON())
    return route.fulfill({ status: 500, json: { error: { code: 'plan_restricted' } } })
  })
  await estimate(page)
  await page.getByRole('button', { name: 'Подтвердить создание', exact: true }).click()
  await expect(page.getByRole('alert')).toContainText('Результат отправки пока неизвестен')
  await page.reload()
  await expect(page.getByRole('button', { name: 'Рассчитать стоимость' })).toBeDisabled()
  await page.getByRole('button', { name: 'Проверить прежний запрос' }).click()
  await expect(page.getByRole('alert')).toContainText('Результат отправки пока неизвестен')
  expect(calls).toHaveLength(2); expect(calls[0]).toEqual(calls[1])
  expect(app.jobs).toHaveLength(0)
})
