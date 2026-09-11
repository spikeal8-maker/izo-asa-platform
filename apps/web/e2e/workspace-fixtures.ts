import { createHash, randomUUID } from 'node:crypto'
import { expect, type Page } from '@playwright/test'

export const owner = '11111111-1111-4111-8111-111111111111'
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
    contentReads: 0, tickets: 0,
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
    const body = req.postData() ? req.postDataJSON() : null
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
