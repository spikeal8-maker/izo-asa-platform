// Real browser -> built web/Caddy -> FastAPI -> PostgreSQL -> test-only streaming provider.
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { chromium, expect } from '@playwright/test'

if (process.env.IZO_ENVIRONMENT !== 'test' || process.env.IZO_CHAT_ACCEPTANCE !== 'isolated')
  throw new Error('Explicit isolated Chat stack required')
const phase = process.argv[3]
if (!['before', 'after'].includes(phase)) throw new Error('Expected before or after')
const file = process.argv[2]
const origin = process.env.IZO_CHAT_ORIGIN ?? 'http://localhost:8080'
const localPreview = process.env.IZO_CHAT_LOCAL_PREVIEW === 'true'
const evidence = 'apps/web/test-results/chat-live'
await mkdir(evidence, { recursive: true })
const browser = await chromium.launch()

async function context() {
  const result = await browser.newContext({
    baseURL: origin, viewport: { width: 1440, height: 900 },
  })
  await result.route('**/*', route =>
    new URL(route.request().url()).origin === origin ? route.continue() : route.abort())
  return result
}

async function login(page, email, passphrase) {
  await page.goto('/login')
  await page.getByLabel('Электронная почта').fill(email)
  await page.getByLabel('Пароль', { exact: true }).fill(passphrase)
  await page.getByRole('button', { name: 'Войти', exact: true }).click()
  await page.waitForURL(url => url.origin === origin && url.pathname === '/')
}

async function previewSession(page) {
  const bootstrap = page.waitForResponse(response =>
    response.url().endsWith('/api/v1/auth/local-preview'))
  await page.goto('/')
  const response = await bootstrap
  expect(response.status()).toBe(200)
  await expect(page).toHaveURL(url => url.origin === origin && url.pathname === '/')
  await expect(page.getByLabel('Электронная почта')).toHaveCount(0)
  const auth = await page.evaluate(async () => {
    const result = await fetch('/api/v1/auth/me', {
      credentials: 'same-origin', cache: 'no-store',
    })
    if (!result.ok) throw new Error('auth me failed')
    return result.json()
  })
  expect(auth.account.email).toBe('preview@local.izo')
  return auth
}

async function expectDeepSeekConnected(page) {
  const settings = page.getByRole('button', { name: 'Настройки DeepSeek и OpenRouter' })
  await expect(settings).toBeVisible({ timeout: 15000 })
  await settings.click()
  const card = page.locator('.chat-provider-card').filter({ hasText: 'DeepSeek' })
  await expect(card.locator('.chat-credential-status'))
    .toContainText('подключён', { timeout: 15000 })
  await settings.click()
}

async function chooseFlash(page) {
  const selector = page.locator('button.chat-model-selector')
  await expect(selector).toContainText('DeepSeek Flash')
  await selector.click()
  const menu = page.getByRole('menu', { name: 'Модели' })
  await expect(menu.getByRole('menuitemradio')).toHaveCount(3)
  await expect(menu.getByRole('menuitemradio', { name: /OpenRouter Auto/ })).toBeDisabled()
  await menu.getByRole('menuitemradio', { name: /DeepSeek Flash/ }).click()
  await expect(selector).toContainText('DeepSeek Flash')
}

async function send(page, text) {
  const input = page.getByRole('textbox', { name: 'Сообщение' })
  await input.fill(text)
  const waiting = page.waitForResponse(response =>
    response.url().includes('/api/v1/chat/requests/')
      && response.url().endsWith('/events'))
  await page.getByRole('button', { name: 'Отправить' }).click()
  const stream = await waiting
  expect(stream.status()).toBe(200)
  expect(stream.headers()['content-type']).toContain('text/event-stream')
  await expect(page.locator('.chat-assistant-message').last())
    .toContainText('Ответ DeepSeek test:', { timeout: 15000 })
  await expect(page.getByRole('button', { name: 'Отправить' })).toBeVisible()
}

async function serverThreads(page) {
  return page.evaluate(async () => {
    const response = await fetch('/api/v1/chat/threads', {
      credentials: 'same-origin', cache: 'no-store',
    })
    if (!response.ok) throw new Error('thread list failed')
    return response.json()
  })
}

const email = 'preview@local.izo'
const passphrase = 'fixture-passphrase-2026'
try {
  if (phase === 'before') {
    const ctx = await context()
    const page = await ctx.newPage()
    let auth
    if (localPreview) {
      auth = await previewSession(page)
    } else {
      await page.goto('/register')
      await page.getByLabel('Имя', { exact: true }).fill('Preview Chat')
      await page.getByLabel('Электронная почта').fill(email)
      await page.getByLabel('Пароль', { exact: true }).fill(passphrase)
      await page.getByRole('button', { name: 'Создать аккаунт' }).click()
      await page.waitForURL(url => url.origin === origin && url.pathname === '/')
      auth = await page.evaluate(async () => (await fetch('/api/v1/auth/me')).json())
    }

    const settings = page.getByRole('button', { name: 'Настройки DeepSeek и OpenRouter' })
    await expect(settings).toBeVisible({ timeout: 15000 })
    await settings.click()
    const deepSeekCard = page.locator('.chat-provider-card').filter({ hasText: 'DeepSeek' })
    await deepSeekCard.getByRole('button', { name: 'Добавить ключ' }).click()
    const tokenInput = deepSeekCard.getByLabel('Новый API key DeepSeek')
    await expect(tokenInput).toBeVisible()
    await tokenInput.fill('x'.repeat(32))
    await deepSeekCard.getByRole('button', {
      name: 'Сохранить и проверить', exact: true,
    }).click()
    await expect(deepSeekCard.locator('.chat-credential-status'))
      .toContainText('Подключён', { timeout: 15000 })
    await expect(tokenInput).toHaveValue('')
    await settings.click()

    await chooseFlash(page)
    await send(page, 'Первый вопрос D1')
    await expect(page.locator('.chat-assistant-message').last())
      .toContainText('Первый вопрос D1')

    await send(page, 'Уточни это')
    const last = page.locator('.chat-assistant-message').last()
    await expect(last).toContainText('Уточни это')
    await expect(last).toContainText('Контекст: Первый вопрос D1')

    const list = await serverThreads(page)
    expect(list.threads).toHaveLength(1)
    const state = {
      email, passphrase, account_id: auth.account.id,
      thread_id: list.threads[0].id, title: list.threads[0].title,
      first: 'Ответ DeepSeek test: Первый вопрос D1',
      follow: 'Контекст: Первый вопрос D1',
    }
    await writeFile(file, JSON.stringify(state), { mode: 0o600 })
    await page.screenshot({
      path: evidence + '/chat-before-restart.png', fullPage: true,
    })
    await ctx.close()
    console.log(localPreview
      ? 'CHAT_BROWSER_BEFORE_OK: auto-session -> encrypted BYOK verify -> model -> SSE -> contextual follow-up'
      : 'CHAT_BROWSER_BEFORE_OK: register -> encrypted BYOK verify -> SSE -> contextual follow-up')
  } else {
    const raw = await readFile(file, 'utf8')
    if (raw.length > 65536) throw new Error('Chat acceptance state exceeds limit')
    const state = JSON.parse(raw)
    const ctx = await context()
    const page = await ctx.newPage()
    let auth
    if (localPreview) auth = await previewSession(page)
    else {
      await login(page, state.email, state.passphrase)
      auth = await page.evaluate(async () => (await fetch('/api/v1/auth/me')).json())
    }
    expect(auth.account.id).toBe(state.account_id)

    await expectDeepSeekConnected(page)
    const item = page.getByRole('button', { name: state.title, exact: true })
    await item.click()
    await expect(page.locator('.chat-turn-user')).toHaveCount(2)
    await expect(page.locator('.chat-assistant-message')).toHaveCount(2)
    await expect(page.locator('.chat-assistant-message').first()).toContainText(state.first)
    await expect(page.locator('.chat-assistant-message').last()).toContainText(state.follow)

    if (localPreview) {
      await send(page, 'После restart')
      await expect(page.locator('.chat-assistant-message').last()).toContainText('После restart')
    }

    await page.reload()
    await expectDeepSeekConnected(page)
    await page.getByRole('button', { name: state.title, exact: true }).click()
    await expect(page.locator('.chat-assistant-message')).toHaveCount(localPreview ? 3 : 2)
    await expect(page.locator('.chat-assistant-message').last())
      .toContainText(localPreview ? 'После restart' : state.follow)
    await page.screenshot({
      path: evidence + '/chat-after-restart.png', fullPage: true,
    })
    await page.setViewportSize({ width: 390, height: 844 })
    await expect.poll(() => page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    )).toBe(true)
    await page.screenshot({
      path: evidence + '/chat-after-restart-phone.png', fullPage: true,
    })
    await ctx.close()
    console.log(localPreview
      ? 'CHAT_BROWSER_AFTER_OK: auto-session reused account -> credential -> durable thread -> F5'
      : 'CHAT_BROWSER_AFTER_OK: login -> credential -> durable thread -> reload after Compose restart')
  }
} finally {
  await browser.close()
}
