import { test, expect } from '@playwright/test'
import { workspace } from './workspace-fixtures'

test('API-001 studio can select the real fal capability without a provider-specific transport', async ({ page }) => {
  const app = await workspace(page)
  app.capabilities = ['fal.flux2.klein.4b']
  await page.goto('/image')
  await expect(page.getByLabel('Исполнитель')).toHaveValue('fal.flux2.klein.4b')
  await expect(page.getByText('fal.ai · реальная AI-модель')).toBeVisible()
  await page.getByLabel('Описание', { exact: true }).fill('Реальная модель через общий серверный job')
  await page.getByRole('button', { name: 'Рассчитать стоимость' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('Реальная AI-генерация через fal.ai.')
  await expect(dialog).toContainText('Реальный AI-вызов')
  await expect(dialog).toContainText('Да')
  const quote = app.requests.find(r => r.path === '/api/v1/jobs/quotes')!
  expect(quote.body?.capability_id).toBe('fal.flux2.klein.4b')
  expect(app.jobs).toHaveLength(0)
})

test('API-001 real provider job remains the same common JobView surface', async ({ page }) => {
  const app = await workspace(page)
  app.capabilities = ['fal.flux2.klein.4b']
  await page.goto('/image')
  await page.getByLabel('Описание', { exact: true }).fill('Общий путь результата')
  await page.getByRole('button', { name: 'Рассчитать стоимость' }).click()
  await page.getByRole('button', { name: 'Подтвердить создание' }).click()
  await expect(page.getByTestId('job-status')).toHaveText('Готово')
  await expect(page.getByText('FLUX.2 [klein] 4B · fal.ai.')).toBeVisible()
  expect(app.jobs).toHaveLength(1)
  expect(app.jobs[0].test_only).toBe(false)
})
