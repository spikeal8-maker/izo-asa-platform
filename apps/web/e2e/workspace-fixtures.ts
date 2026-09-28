import { createHash, randomUUID } from 'node:crypto'
import { expect, type Page } from '@playwright/test'

export const owner = `11111111-1111-4111-8111-1111111111${Number(process.env.TEST_WORKER_INDEX ?? 0).toString(16).padStart(2, '0')}`
export const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAGUlEQVR4nGMUaVrFQApgIkn1qIZRDUNKAwAFNgFgLuDeBwAAAABJRU5ErkJggg==', 'base64')
export const hash = createHash('sha256').update(png).digest('hex')
export function asset(id = randomUUID()) {
  return { id, kind: 'image', content_type: 'image/png', byte_size: png.length,
    width: 16, height: 16, sha256: hash, created_at: 1788980000 }
}
export async function workspace(page: Page) {
  const state = {
    account: { id: owner, public_code: '1111222233334444', display_name: 'Тестовый пользователь',
      email: 'workspace@example.invalid', email_verified: true, state: 'active', permissions: [] as string[] },
    signedIn: true, configured: true, balance: 100, reserved: 0, cost: 7,
    capabilities: ['test.image.v1'] as string[],
    quoteError: '', assetError: '', uncertainOnce: false, autoFinish: true, badImage: false, evilTicket: false,
    requests: [] as { method: string; path: string; body: Record<string, any> | null }[],
    jobs: [] as Record<string, any>[], assets: [] as ReturnType<typeof asset>[],
    quotes: new Map<string, Record<string, any>>(), operations: new Map<string, string>(),
    contentReads: 0, tickets: 0, uploads: new Map<string, Record<string, any>>(),
    uploadOperations: new Map<string, string>(), uploadError: '', uploadUncertainOnce: false,
  }
  function finish(job: Record<string, any>) {
    if (job.status === 'succeeded') return
    job.status = 'succeeded'; job.charged_credits = state.cost; job.reserved_credits = 0
    job.asset_id = randomUUID(); job.attempt_count = 1
    state.balance -= state.cost; state.reserved -= state.cost
    state.assets.push(asset(job.asset_id))
  }
  await page.route('**/api/v1/**', async route => {
    const req = route.request(), url = new URL(req.url()), path = url.pathname
    const body = req.postData() && req.headers()['content-type'] !== 'application/octet-stream'
      ? req.postDataJSON() : null
    state.requests.push({ method: req.method(), path, body })
    const answer = (value: unknown, status = 200) => route.fulfill({ status, json: value })
    const denied = (code: string, status = 409) => answer({ error: { code } }, status)
    if (path === '/api/v1/foundation') return answer({ stage: 'foundation', build_sha: 'unreleased', capabilities: [] })
    if (!state.signedIn) return denied('auth_required', 401)
    if (path === '/api/v1/auth/me') return answer({ account: state.account, csrf_token: 'workspace-csrf' })
    if (path === '/api/v1/credits') return answer({ account_id: owner,
      balance: { balance: state.balance, available: state.balance - state.reserved, reserved: state.reserved, sequence: 1 }, entries: [], next_before: null })
    if (path === '/api/v1/entitlements') return answer({ account_id: owner, configured: state.configured,
      policy: { capability_ids: state.capabilities, executors: ['api'], image_sizes: [{ width: 64, height: 64 }, { width: 128, height: 64 }] } })
    if (path === '/api/v1/chat/policy') return answer({
      revision: 'browser-fixture', default_model: 'deepseek-flash',
      models: [{ id: 'deepseek-flash', label: 'DeepSeek Flash', provider: 'deepseek' },
        { id: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro', provider: 'deepseek' },
        { id: 'openrouter-auto', label: 'Автовыбор OpenRouter', provider: 'openrouter' }],
      max_input_chars: 6000, max_output_tokens: 2048,
    })
    if (path === '/api/v1/chat/credentials') return answer({ credentials: [
      { configured: true, enabled: true, verified: true, revision: 1, generation: 1, provider: 'deepseek' },
      { configured: false, enabled: false, verified: false, revision: null, generation: null, provider: 'openrouter' },
    ] })
    if (path === '/api/v1/chat/catalog/openrouter') return answer({ models: [], stale: false, fetched_at: 1 })
    if (path === '/api/v1/chat/threads' && req.method() === 'GET') return answer({ threads: [] })
    if (req.method() === 'POST') {
      expect(req.headers()['x-csrf-token']).toBe('workspace-csrf')
      expect(req.headers()['x-izo-request']).toBe('web')
    }
    if (path === '/api/v1/jobs/quotes') {
      if (state.quoteError) return denied(state.quoteError)
      const real = body.capability_id === 'fal.flux2.klein.4b'
      const quote = { ...body, id: randomUUID(), credits: state.cost, expires_at: Math.floor(Date.now() / 1000) + 120,
        test_only: !real, notice: real ? 'Реальная AI-генерация через fal.ai.' : 'Диагностический PNG, не AI. Расходуются тестовые баллы.' }
      state.quotes.set(quote.id, quote)
      return answer(quote, 201)
    }
    if (path === '/api/v1/jobs' && req.method() === 'POST') {
      const old = state.operations.get(body.operation_id)
      if (old) return answer(state.jobs.find(job => job.id === old), 201)
      const quote = state.quotes.get(body.quote_id)
      if (!quote) return denied('quote_expired')
      const job = { id: randomUUID(), status: 'queued', capability_id: quote.capability_id,
        prompt: quote.prompt, width: quote.width, height: quote.height, reserved_credits: state.cost, charged_credits: 0,
        asset_id: null, error_code: null, cancel_requested: false, created_at: 1788980000, updated_at: 1788980000,
        attempt_count: 0, test_only: quote.test_only }
      state.jobs.push(job); state.operations.set(body.operation_id, job.id); state.reserved += state.cost
      if (state.uncertainOnce) { state.uncertainOnce = false; return denied('temporary', 503) }
      return answer(job, 201)
    }
    if (path === '/api/v1/jobs') return answer({ jobs: state.jobs, next_offset: null })
    if (path.startsWith('/api/v1/jobs/')) {
      const id = path.split('/')[4], job = state.jobs.find(item => item.id === id)
      if (!job) return denied('not_found', 404)
      if (path.endsWith('/cancel')) {
        if (job.status === 'queued') { job.status = 'cancelled'; state.reserved -= state.cost; job.reserved_credits = 0 }
        job.cancel_requested = true
      } else if (state.autoFinish && job.status === 'queued') finish(job)
      return answer(job)
    }
    if (path === '/api/v1/media/uploads' && req.method() === 'POST') {
      if (state.uploadError) return denied(state.uploadError, 409)
      const previous = state.uploadOperations.get(body.operation_id)
      if (previous) return answer(state.uploads.get(previous), 201)
      const upload = { id: randomUUID(), status: 'pending', asset_id: null,
        expires_at: Math.floor(Date.now() / 1000) + 600, reserved_bytes: body.byte_size }
      state.uploadOperations.set(body.operation_id, upload.id)
      state.uploads.set(upload.id, upload)
      return answer(upload, 201)
    }
    if (path.startsWith('/api/v1/media/uploads/')) {
      const id = path.split('/')[5], upload = state.uploads.get(id)
      if (!upload) return denied('not_found', 404)
      if (path.endsWith('/content') && req.method() === 'POST') {
        if (upload.status === 'pending') {
          upload.status = 'ready'; upload.asset_id = randomUUID(); upload.reserved_bytes = 0
          state.assets.push(asset(upload.asset_id))
        }
        if (state.uploadUncertainOnce) { state.uploadUncertainOnce = false; return denied('temporary', 503) }
      }
      return answer(upload)
    }
    if (path === '/api/v1/media/assets') {
      if (state.assetError) return denied(state.assetError, 503)
      const offset = Number(url.searchParams.get('offset') ?? 0), limit = Number(url.searchParams.get('limit') ?? 20)
      return answer({ assets: state.assets.slice(offset, offset + limit),
        next_offset: offset + limit < state.assets.length ? offset + limit : null,
        used_bytes: state.assets.length * png.length, reserved_bytes: 0 })
    }
    if (path.startsWith('/api/v1/media/assets/')) {
      const id = path.split('/')[5], current = state.assets.find(item => item.id === id)
      if (!current) return denied('not_found', 404)
      if (path.endsWith('/download')) {
        state.tickets++
        return answer({ url: state.evilTicket ? 'https://example.invalid/foreign.png'
          : `/api/v1/media/assets/${id}/content?ticket=${'a'.repeat(43)}`, expires_at: Math.floor(Date.now() / 1000) + 120 })
      }
      if (path.endsWith('/content')) {
        state.contentReads++
        return route.fulfill({ contentType: 'image/png', body: state.badImage ? Buffer.from('broken') : png,
          headers: { 'content-disposition': `attachment; filename="${id}.png"` } })
      }
      return answer(current)
    }
    return denied('not_found', 404)
  })
  return state
}
export async function estimate(page: Page, prompt = 'Проверка сохранённого серверного результата') {
  await page.goto('/image')
  await expect(page.getByTestId('studio-available')).toBeVisible()
  await page.getByLabel('Описание', { exact: true }).fill(prompt)
  await page.getByRole('button', { name: 'Рассчитать стоимость' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
}
export async function create(page: Page, prompt?: string) {
  await estimate(page, prompt)
  await page.getByRole('button', { name: 'Подтвердить создание' }).click()
  await page.waitForURL('**/jobs/*')
  await expect(page.getByTestId('job-status')).toHaveText('Готово')
}
export async function noOverflow(page: Page) {
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
}

export const visionThread = { id: '11111111-1111-4111-8111-111111111129', title: 'Изображение',
  created_at: 1, updated_at: 1 }
const visionPrice = { currency: 'RUB', input_kopeks_per_million: 100,
  output_kopeks_per_million: 100, image_kopeks_per_image: null }
export const visionPolicy = { revision: 'vision-fixture', default_model: 'deepseek-flash',
  models: [{ id: 'deepseek-flash', label: 'DeepSeek Flash', provider: 'deepseek',
    text: true, vision: true, price: visionPrice }, { id: 'deepseek-text', label: 'DeepSeek Text',
    provider: 'deepseek', text: true, vision: false, price: visionPrice }], max_input_chars: 6000,
  max_output_tokens: 2048, max_attachments: 5, max_image_bytes: 12 * 1024 * 1024 }

export async function visionProvider(page: Page, vision: () => boolean) {
  await page.route('**/api/v1/chat/catalog/openrouter', route => route.fulfill({ json: {
    stale: false, fetched_at: 100, models: [{ id: 'anthropic/vision-test', name: 'Vision Test',
      provider: 'anthropic', context_length: 100000, vision: vision(),
      input_per_million_usd: null, output_per_million_usd: null }],
  } }))
  await page.route('**/api/v1/chat/credentials', route => route.fulfill({ json: { credentials:
    ['deepseek', 'openrouter'].map(provider => ({ configured: true, enabled: true,
      verified: true, revision: 1, generation: 1, provider })) } }))
}

export async function chatWorkspace(page: Page, existing = false) {
  const app = await workspace(page)
  const messages: Record<string, unknown>[] = []
  const admitted: Record<string, any>[] = []
  await page.route('**/api/v1/chat/policy', route => route.fulfill({ json: visionPolicy }))
  await page.route('**/api/v1/chat/threads', route => route.request().method() === 'POST'
    ? route.fulfill({ json: visionThread })
    : route.fulfill({ json: { threads: existing || admitted.length ? [visionThread] : [] } }))
  await page.route(`**/api/v1/chat/threads/${visionThread.id}`,
    route => route.fulfill({ json: { thread: visionThread, messages } }))
  await page.route(`**/api/v1/chat/threads/${visionThread.id}/requests`, route => {
    const body = route.request().postDataJSON()
    admitted.push(body)
    messages.push({ id: randomUUID(), request_id: body.request_id, role: 'user', sequence: 1,
      content: body.text, state: 'complete', created_at: 1, updated_at: 1,
      attachments: body.attachment_ids.map((id: string) => ({ id: randomUUID(), asset_id: id,
        media_type: 'image/png', byte_size: png.length, width: 16, height: 16,
        sha256: app.assets.find(asset => asset.id === id)!.sha256, created_at: 1 })) })
    return route.fulfill({ json: { id: body.request_id, thread_id: visionThread.id, state: 'pending' } })
  })
  await page.route('**/api/v1/chat/requests/*/events', route => route.fulfill({
    headers: { 'content-type': 'text/event-stream' }, body: 'event: message.completed\ndata: {}\n\n',
  }))
  return { app, admitted }
}
