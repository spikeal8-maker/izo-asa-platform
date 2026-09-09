import { test, expect } from '@playwright/test'
import { fakeApi, createWork, noOverflow } from './demo-fixture'

test.beforeEach(async ({ page }) => { await fakeApi(page) })

test('U-19 empty state has no invented personal works', async ({ page }, info) => {
  await page.goto('/gallery')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Галерея')
  await expect(page.getByText('Здесь начнётся ваша коллекция')).toBeVisible()
  await expect(page.locator('.asset-card')).toHaveCount(0)
  const clearance = await page.getByLabel('Поиск работ').evaluate(input => {
    const icon = input.parentElement!.querySelector('svg')!
    const textStart = input.getBoundingClientRect().left + parseFloat(getComputedStyle(input).paddingLeft)
    return textStart - icon.getBoundingClientRect().right
  })
  expect(clearance).toBeGreaterThan(4)
  await noOverflow(page)
  await page.screenshot({ path: info.outputPath('gallery-empty.png'), fullPage: true })
})

test('U-19/U-20 @smoke list, filter, navigation, refresh, reuse and delete', async ({ page }, info) => {
  await createWork(page, 'Тёплый горизонт')
  await createWork(page, 'Геометрия тишины')
  await page.getByRole('navigation').getByRole('link', { name: 'Галерея', exact: true }).click()
  await expect(page.locator('.asset-card')).toHaveCount(2)
  await page.getByRole('button', { name: 'Local · демо', exact: true }).click()
  await expect(page.getByText('Ничего не найдено', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Сбросить фильтры' }).click()
  await page.getByLabel('Поиск работ').fill('Геометрия')
  await expect(page.locator('.asset-card')).toHaveCount(1)
  await page.getByLabel('Поиск работ').fill('')
  await page.screenshot({ path: info.outputPath('gallery.png'), fullPage: true })
  await page.locator('.asset-card').first().click()
  const url = page.url()
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Геометрия тишины')
  await page.screenshot({ path: info.outputPath('asset.png'), fullPage: true })
  await page.getByRole('link', { name: 'Использовать настройки' }).click()
  await expect(page.getByLabel('Описание', { exact: true })).toHaveValue('Геометрия тишины')
  await page.goBack()
  await expect(page).toHaveURL(url)
  await page.getByRole('button', { name: 'Удалить демо-работу' }).click()
  await page.getByRole('button', { name: 'Удалить пример', exact: true }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Работа не найдена')
  await noOverflow(page)
})

test('zero demo balance does not remove gallery access, reset is explicit', async ({ page }) => {
  await createWork(page)
  await page.getByRole('button', { name: 'О состоянии' }).click()
  await page.getByLabel('Нулевой демо-баланс').check()
  await page.getByRole('button', { name: 'Понятно' }).click()
  await expect(page.getByRole('button', { name: /Создать демо/ })).toBeDisabled()
  await page.getByRole('navigation').getByRole('link', { name: 'Галерея', exact: true }).click()
  await expect(page.locator('.asset-card')).toHaveCount(1)
  await page.getByRole('button', { name: 'О состоянии' }).click()
  await page.getByRole('button', { name: 'Сбросить демо', exact: true }).click()
  await page.getByRole('button', { name: 'Подтвердить сброс' }).click()
  await expect(page.locator('.asset-card')).toHaveCount(0)
})

test('storage denied is honest; unknown deep links and dark mode remain usable', async ({ page }, info) => {
  await page.addInitScript(() => { Storage.prototype.setItem = () => { throw new DOMException('Test storage denied', 'SecurityError') } })
  await page.goto('/gallery/not-owned')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Работа не найдена')
  await expect(page.getByRole('alert')).toContainText('Хранение в этой вкладке недоступно')
  await page.getByRole('button', { name: 'Переключить тему' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await page.goto('/unknown-page')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Страница не найдена')
  await page.getByRole('button', { name: 'Переключить тему' }).click()
  await noOverflow(page)
  await page.screenshot({ path: info.outputPath('dark-error.png'), fullPage: true })
})
