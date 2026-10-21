// Real browser -> built web/Caddy -> FastAPI -> PostgreSQL -> test-only streaming provider.
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { join } from 'node:path'
import { chromium, expect } from '@playwright/test'
import { graphBefore, graphAfter } from './chat-graph-live.mjs'
import { editBefore, editAfter, contextCases, command, complete, terminal, button } from './chat-message-edit-live.mjs'
import { searchBefore, searchAfter } from './chat-thread-search-live.mjs'
import { rename } from './chat-search-ui-live.mjs'

if (process.env.IZO_ENVIRONMENT !== 'test' || process.env.IZO_CHAT_ACCEPTANCE !== 'isolated')
  throw new Error('Explicit isolated Chat stack required')
const phase = process.argv[3]
if (!['before', 'after'].includes(phase)) throw new Error('Expected before or after')
const file = process.argv[2]
const origin = process.env.IZO_CHAT_ORIGIN ?? 'http://localhost:8080'
const evidence = 'apps/web/test-results/chat-live'
await mkdir(evidence, { recursive: true })
const browser = await chromium.launch()

async function context(touch = false) {
  const result = await browser.newContext({
    baseURL: origin, viewport: { width: 1440, height: 900 }, hasTouch: touch,
  })
  await result.route('**/*', route =>
    new URL(route.request().url()).origin === origin ? route.continue() : route.abort())
  return result
}

async function authenticate(page, email, passphrase, register = false) {
  await page.goto(register ? '/register' : '/login')
  if (register) await page.getByLabel('Имя', { exact: true }).fill('Preview Chat')
  await page.getByLabel('Электронная почта').fill(email)
  await page.getByLabel('Пароль', { exact: true }).fill(passphrase)
  await button(page, register ? 'Создать аккаунт' : 'Войти').click()
  await page.waitForURL(url => url.origin === origin && url.pathname === '/')
}
const connected = page => button(page, 'DeepSeek подключён')

async function send(page, text) {
  const input = page.getByRole('textbox', { name: 'Сообщение' })
  await input.fill(text)
  const waiting = page.waitForResponse(response =>
    response.url().includes('/api/v1/chat/requests/')
      && response.url().endsWith('/events'))
  await button(page, 'Отправить').click()
  const stream = await waiting
  expect(stream.status()).toBe(200)
  expect(stream.headers()['content-type']).toContain('text/event-stream')
  await expect(page.locator('.chat-assistant-message').last())
    .toContainText('Ответ DeepSeek test:', { timeout: 15000 })
  await expect(button(page, 'Отправить')).toBeVisible()
}

const serverThreads = page => command(page, 'threads')

async function concurrentRename(page) {
  const policy = await command(page, 'policy'), thread = await command(page, 'threads', 'POST', { title: null }, 201)
  const requestId = randomUUID(), path = `threads/${thread.id}`
  await Promise.all([
    command(page, path, 'PATCH', { title: 'Новый чат' }),
    command(page, `${path}/requests`, 'POST', {
      request_id: requestId, text: 'Проверка первого сообщения и ручного имени',
      model: policy.default_model, attachment_ids: [],
    }, 202),
  ])
  expect((await command(page, path)).thread.title).toBe('Новый чат')
  const title = 'Название после одновременных запросов'
  await Promise.all([command(page, path, 'PATCH', { title }), complete(page, requestId)])
  const detail = await command(page, path)
  expect(detail.thread.title).toBe(title); expect(detail.messages).toHaveLength(2)
  return { id: thread.id, title }
}

async function editFollowup(page, proof) {
  const branch = proof.edits[0].receipt.created_branch.id, path = `threads/${proof.thread_id}`
  const selector = page.getByRole('combobox', { name: 'Ветка разговора', exact: true })
  await selector.selectOption(branch); await expect(selector).toBeEnabled()
  const admitted = page.waitForResponse(response => response.url().endsWith(`${path}/requests`))
  await send(page, 'Продолжение выбранной ветки')
  const response = await admitted, request = await response.json(), body = response.request().postDataJSON()
  expect(response.status()).toBe(202); expect(body.branch_id).toBe(branch)
  await terminal(page, request.id)
  const current = await command(page, `${path}/graph`), last = current.turns.at(-1)
  expect(current.active_branch_id).toBe(branch); expect(current.turns).toHaveLength(3)
  expect(current.turns.slice(0, 2)).toEqual(proof.edits[0].turns)
  proof.followup = { request_id: request.id, branch_id: branch, turn_id: last.id,
    revision: body.expected_revision + 1, kind: 'send',
    ids: current.turns.slice(0, -1).flatMap(turn => [turn.user_message.id, turn.selected_attempt.message.id]).concat(last.user_message.id) }
  proof.projections[branch] = current.turns
  proof.active_branch_id = branch; proof.revision = current.revision
  proof.physical_messages = (await command(page, path)).messages
}

async function editContexts(proof) {
  const preview = origin === 'http://127.0.0.1:18080'
  if (!preview && origin !== 'http://localhost:8080')
    throw new Error('Context observer requires isolated Compose')
  const cases = contextCases(proof)
  const code = `import json,sys
from uuid import UUID
import sqlalchemy as sa
from izo.config import Settings
from izo.accounts.repository import create_auth_engine
from izo.chat import tables as t
from izo.chat.graph_context import digest
config = Settings()
assert config.environment == 'test' and config.pg_host == 'postgres'
engine = create_auth_engine(config)
observed = []
with engine.connect().execution_options(postgresql_readonly=True) as conn:
    for expected in json.loads(sys.argv[1]):
        query = sa.select(t.contexts, sa.cast(t.contexts.c.snapshot, sa.Text).label('snapshot_text'))
        row = dict(conn.execute(query.where(t.contexts.c.request_id == UUID(expected['request_id']))).mappings().one())
        for key in ('request_id','thread_id','branch_id','turn_id','revision','kind'):
            assert str(row[key]) == str(expected[key]), key
        assert row['provenance'] == 'admission' and digest(row['snapshot']) == row['digest']
        messages = expected['expected']
        assert row['snapshot']['messages'] == [dict(id=m['id'], role=m['role'],
            content_digest=digest(m['content']), attachments=[]) for m in messages]
        observed.append(row)
engine.dispose()
print(json.dumps(observed,default=str,ensure_ascii=False))`
  const bundle = preview && process.env.RUNNER_TEMP && join(process.env.RUNNER_TEMP, 'izo-preview-clean', 'IZO-ASA-Chat-Preview')
  if (preview && !bundle) throw new Error('Missing exact clean-preview path')
  const args = ['compose', ...(preview ? ['-f', join(bundle, 'compose.yaml'), '-p', 'izo-chat-preview-clean', '--env-file', join(bundle, '.env')]
    : ['-f', 'compose.yaml', '-p', 'izo-foundation', '--env-file', '.env'])]
  const actual = JSON.parse(execFileSync('docker', [...args, 'exec', '-T', 'api', 'python', '-c', code, JSON.stringify(cases)],
    { encoding: 'utf8', timeout: 30000, maxBuffer: 262144 }))
  if (phase === 'after') expect(actual).toEqual(proof.contexts)
  else proof.contexts = actual
  await writeFile(`${evidence}/edit-${phase}-${preview ? 18080 : 8080}.json`, JSON.stringify({ phase, origin, proof, actual }, null, 2))
  console.log(`CHAT_EDIT_CONTEXT_${phase.toUpperCase()}_OK: ${actual.length} retained contexts`)
  return actual
}

const email = 'preview@local.izo'
const passphrase = 'fixture-passphrase-2026'
try {
  if (phase === 'before') {
    const ctx = await context()
    const page = await ctx.newPage()
    await authenticate(page, email, passphrase, true)

    const tokenInput = page.getByLabel('API ключ DeepSeek')
    await expect(tokenInput).toBeVisible({ timeout: 15000 })
    await tokenInput.fill('x'.repeat(32))
    await button(page, /Сохранить и проверить|Заменить и проверить/).click()
    await expect(connected(page))
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
    state.edit = await editBefore(page, evidence)
    await editFollowup(page, state.edit)
    await editContexts(state.edit)
    state.search = await searchBefore(context, authenticate, state, page, evidence, editContexts)
    await writeFile(file, JSON.stringify(state), { mode: 0o600 })
    await ctx.close()
    console.log(
      'CHAT_BROWSER_BEFORE_OK: register, BYOK, SSE, follow-up, rename, concurrent first-message rename',
    )
  } else {
    const raw = await readFile(file, 'utf8')
    if (raw.length > 65536) throw new Error('Chat acceptance state exceeds limit')
    const state = JSON.parse(raw)
    const ctx = await context()
    const page = await ctx.newPage()
    await authenticate(page, state.email, state.passphrase)

    await expect(connected(page)).toBeVisible()
    const durable = await serverThreads(page)
    expect(durable.threads.find(thread => thread.id === state.thread_id)?.title).toBe(state.title)
    expect(durable.threads.find(thread => thread.id === state.race.id)?.title).toBe(state.race.title)
    const item = button(page, state.title)
    await item.click()
    await expect(page.locator('.chat-turn-user')).toHaveCount(2)
    await expect(page.locator('.chat-assistant-message')).toHaveCount(2)
    await expect(page.locator('.chat-assistant-message').first()).toContainText(state.first)
    await expect(page.locator('.chat-assistant-message').last()).toContainText(state.follow)

    await page.reload()
    await expect(connected(page)).toBeVisible()
    await button(page, state.title).click()
    await expect(page.locator('.chat-assistant-message')).toHaveCount(2)
    await expect(page.locator('.chat-assistant-message').last()).toContainText(state.follow)
    await page.screenshot({
      path: evidence + '/chat-after-restart.png', fullPage: true,
    })
    await page.setViewportSize({ width: 390, height: 844 })
    await button(page, 'Открыть панель').click()
    await rename(page, state.title, 'Мобильное переименование после перезапуска')
    await page.reload()
    await button(page, 'Открыть панель').click()
    await expect(button(page, 'Мобильное переименование после перезапуска')).toBeVisible()
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
    await editAfter(page, state.edit, evidence)
    await editContexts(state.edit)
    await searchAfter(context, authenticate, state, page, evidence, editContexts)
    await ctx.close()
    console.log(
      'CHAT_BROWSER_AFTER_OK: login, durable titles/messages, reload, mobile rename after Compose restart',
    )
  }
} finally {
  await browser.close()
}
