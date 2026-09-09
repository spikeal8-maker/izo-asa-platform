import { expect, type Page } from '@playwright/test'

export async function fakeApi(page: Page) {
  await page.route('**/api/v1/foundation', route => route.fulfill({ json: { stage: 'foundation', build_sha: 'unreleased', capabilities: [] } }))
}
export async function createWork(page: Page, prompt = 'Тестовая архитектурная композиция') {
  await page.goto('/image')
  if (prompt === 'Геометрия тишины') await page.getByRole('button', { name: 'Атмосфера', exact: false }).click()
  await page.getByLabel('Описание', { exact: true }).fill(prompt)
  await page.getByRole('button', { name: /Создать демо/ }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  // Two synchronous events exercise the UI guard before React renders disabled.
  await page.getByRole('button', { name: 'Подтвердить демо-запуск' }).evaluate(node => { (node as HTMLButtonElement).click(); (node as HTMLButtonElement).click() })
  await expect(page.getByRole('link', { name: 'Открыть работу', exact: false })).toBeVisible()
}
export async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
}
