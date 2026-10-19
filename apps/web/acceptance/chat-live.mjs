// Real browser -> built web/Caddy -> FastAPI -> PostgreSQL -> test-only streaming provider.
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { chromium, expect } from '@playwright/test'
import { graphBefore, graphAfter } from './chat-graph-live.mjs'

if (process.env.IZO_ENVIRONMENT !== 'test' || process.env.IZO_CHAT_ACCEPTANCE !== 'isolated')
  throw new Error('Explicit isolated Chat stack required')
const phase = process.argv[3]
if (!['before', 'after'].includes(phase)) throw new Error('Expected before or after')
const file = process.argv[2]
const origin = process.env.IZO_CHAT_ORIGIN ?? 'http://localhost:8080'
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

async function rename(page, oldTitle, title) {
  const row = page.locator('.chat-history-row').filter({
    has: page.getByRole('button', { name: oldTitle, exact: true }),
  })
  await row.getByRole('button', { name: 'Переименовать', exact: true }).click()
  await page.getByRole('textbox', { name: 'Название чата', exact: true }).fill(title)
  await page.getByRole('button', { name: 'Сохранить', exact: true }).click()
  await expect(page.getByRole('button', { name: title, exact: true })).toBeVisible()
}

async function concurrentRename(page) {
  return page.evaluate(async () => {
    const auth = await (await fetch('/api/v1/auth/me')).json()
    const policy = await (await fetch('/api/v1/chat/policy')).json()
    async function command(path, method, data) {
      const response = await fetch(`/api/v1/chat/${path}`, { method,
        credentials: 'same-origin', headers: { 'Content-Type': 'application/json',
          'X-CSRF-Token': auth.csrf_token, 'X-IZO-Request': 'web' }, body: JSON.stringify(data) })
      if (!response.ok) throw new Error(`Concurrent rename command failed: ${response.status}`)
      return response.json()
    }
    const thread = await command('threads', 'POST', { title: null })
    const requestId = crypto.randomUUID()
    await Promise.all([
      command(`threads/${thread.id}`, 'PATCH', { title: 'Новый чат' }),
      command(`threads/${thread.id}/requests`, 'POST', {
        request_id: requestId, text: 'Проверка первого сообщения и ручного имени',
        model: policy.default_model, attachment_ids: [],
      }),
    ])
    let detail = await (await fetch(`/api/v1/chat/threads/${thread.id}`)).json()
    if (detail.thread.title !== 'Новый чат') throw new Error('First message overwrote manual title')
    const title = 'Название после одновременных запросов'
    await Promise.all([
      command(`threads/${thread.id}`, 'PATCH', { title }),
      fetch(`/api/v1/chat/requests/${requestId}/events`).then(async response => {
        if (!response.ok) throw new Error('Isolated provider stream failed')
        await response.text()
      }),
    ])
    detail = await (await fetch(`/api/v1/chat/threads/${thread.id}`)).json()
    if (detail.thread.title !== title || detail.messages.length !== 2)
      throw new Error('Concurrent rename lost title or messages')
    return { id: thread.id, title }
  })
}

const email = 'preview@local.izo'
const passphrase = 'fixture-passphrase-2026'
try {
  if (phase === 'before') {
    const ctx = await context()
    const page = await ctx.newPage()
    await page.goto('/register')
    await page.getByLabel('Имя', { exact: true }).fill('Preview Chat')
    await page.getByLabel('Электронная почта').fill(email)
    await page.getByLabel('Пароль', { exact: true }).fill(passphrase)
    await page.getByRole('button', { name: 'Создать аккаунт' }).click()
    await page.waitForURL(url => url.origin === origin && url.pathname === '/')

    const tokenInput = page.getByLabel('API ключ DeepSeek')
    await expect(tokenInput).toBeVisible({ timeout: 15000 })
    await tokenInput.fill('x'.repeat(32))
    await page.getByRole('button', {
      name: /Сохранить и проверить|Заменить и проверить/,
    }).click()
    await expect(page.getByRole('button', { name: 'DeepSeek подключён' }))
      .toBeVisible({ timeout: 15000 })

    await send(page, 'Первый вопрос D1')
    await expect(page.locator('.chat-assistant-message').last())
      .toContainText('Первый вопрос D1')

    await send(page, 'Уточни это')
    const last = page.locator('.chat-assistant-message').last()
    await expect(last).toContainText('Уточни это')
    await expect(last).toContainText('Контекст: Первый вопрос D1')

    const list = await serverThreads(page)
    expect(list.threads).toHaveLength(1)
    const title = 'Урок робототехники — сохранено'
    await rename(page, list.threads[0].title, title)
    expect((await serverThreads(page)).threads[0].title).toBe(title)
    await expect(page.locator('.chat-turn-user')).toHaveCount(2)
    await expect(page.locator('.chat-assistant-message')).toHaveCount(2)
    const race = await concurrentRename(page)
    const state = {
      email, passphrase, thread_id: list.threads[0].id,
      title, race,
      first: 'Ответ DeepSeek test: Первый вопрос D1',
      follow: 'Контекст: Первый вопрос D1',
    }
    await page.screenshot({
      path: evidence + '/chat-before-restart.png', fullPage: true,
    })
    state.graph = await graphBefore(page, evidence)
    await writeFile(file, JSON.stringify(state), { mode: 0o600 })
    await ctx.close()
    console.log(
      'CHAT_BROWSER_BEFORE_OK: register -> BYOK -> SSE -> follow-up -> rename -> concurrent first-message rename',
    )
  } else {
    const raw = await readFile(file, 'utf8')
    if (raw.length > 65536) throw new Error('Chat acceptance state exceeds limit')
    const state = JSON.parse(raw)
    const ctx = await context()
    const page = await ctx.newPage()
    await login(page, state.email, state.passphrase)

    await expect(page.getByRole('button', { name: 'DeepSeek подключён' })).toBeVisible()
    const durable = await serverThreads(page)
    expect(durable.threads.find(thread => thread.id === state.thread_id)?.title).toBe(state.title)
    expect(durable.threads.find(thread => thread.id === state.race.id)?.title).toBe(state.race.title)
    const item = page.getByRole('button', { name: state.title, exact: true })
    await item.click()
    await expect(page.locator('.chat-turn-user')).toHaveCount(2)
    await expect(page.locator('.chat-assistant-message')).toHaveCount(2)
    await expect(page.locator('.chat-assistant-message').first()).toContainText(state.first)
    await expect(page.locator('.chat-assistant-message').last()).toContainText(state.follow)

    await page.reload()
    await expect(page.getByRole('button', { name: 'DeepSeek подключён' })).toBeVisible()
    await page.getByRole('button', { name: state.title, exact: true }).click()
    await expect(page.locator('.chat-assistant-message')).toHaveCount(2)
    await expect(page.locator('.chat-assistant-message').last()).toContainText(state.follow)
    await page.screenshot({
      path: evidence + '/chat-after-restart.png', fullPage: true,
    })
    await page.setViewportSize({ width: 390, height: 844 })
    await page.getByRole('button', { name: 'Открыть панель' }).click()
    await rename(page, state.title, 'Мобильное переименование после перезапуска')
    await page.reload()
    await page.getByRole('button', { name: 'Открыть панель' }).click()
    await expect(page.getByRole('button', {
      name: 'Мобильное переименование после перезапуска', exact: true,
    })).toBeVisible()
    const drawer = page.locator('.chat-sidebar')
    await expect(drawer).toHaveAttribute('role', 'dialog')
    await expect(drawer).toHaveCSS('transform', 'matrix(1, 0, 0, 1, 0, 0)')
    await expect.poll(async () => (await drawer.boundingBox())?.height ?? 0).toBeGreaterThan(600)
    await expect.poll(() => page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    )).toBe(true)
    await page.screenshot({
      path: evidence + '/chat-after-restart-phone.png', fullPage: true, animations: 'disabled',
    })
    await graphAfter(page, state.graph, evidence)
    await ctx.close()
    console.log(
      'CHAT_BROWSER_AFTER_OK: login -> durable manual titles/messages -> reload -> mobile rename persistence after Compose restart',
    )
  }
} finally {
  await browser.close()
}
