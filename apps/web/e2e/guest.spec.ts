import { expect, test, type Page, type Route } from '@playwright/test'
import { workspace } from './workspace-fixtures'

const guestId = '11111111-1111-4111-8111-111111111111'
const quoteId = '22222222-2222-4222-8222-222222222222'
const jobId = '33333333-3333-4333-8333-333333333333'
const csrf = 'g'.repeat(43)

function guestView() {
  return { account_id: guestId, csrf_token: csrf, expires_at: 2_000_000_000,
    remaining_jobs: 1, trial_credits: 3 }
}
function failedJob() {
  return { id: jobId, status: 'failed', capability_id: 'test.image.v1', prompt: 'guest browser trial',
    width: 512, height: 512, reserved_credits: 1, charged_credits: 0, asset_id: null,
    error_code: 'provider_failed', cancel_requested: false, created_at: 1_700_000_000,
    updated_at: 1_700_000_001, attempt_count: 1, test_only: true }
}

async function mockGuest(page: Page) {
  let started = false
  let created = false
  const calls: string[] = []
  await page.route('**/api/v1/guest/**', async (route: Route) => {
    const request = route.request(); const url = new URL(request.url())
    calls.push(`${request.method()} ${url.pathname}`)
    if (url.pathname === '/api/v1/guest/me') {
      return started ? route.fulfill({ json: guestView() })
        : route.fulfill({ status: 401, json: { error: { code: 'guest_required' } } })
    }
    if (url.pathname === '/api/v1/guest/start' && request.method() === 'POST') {
      started = true; return route.fulfill({ status: 201, json: guestView() })
    }
    if (url.pathname === '/api/v1/guest/quotes' && request.method() === 'POST') {
      return route.fulfill({ status: 201, json: { id: quoteId, capability_id: 'test.image.v1',
        prompt: 'guest browser trial', width: 512, height: 512, credits: 1,
        expires_at: 2_000_000_000, test_only: true, notice: 'Пробный режим' } })
    }
    if (url.pathname === '/api/v1/guest/jobs' && request.method() === 'POST') {
      created = true; return route.fulfill({ status: 201, json: { ...failedJob(), status: 'queued',
        error_code: null, attempt_count: 0 } })
    }
    if (url.pathname === '/api/v1/guest/jobs' && request.method() === 'GET') {
      return route.fulfill({ json: { jobs: created ? [failedJob()] : [], next_offset: null } })
    }
    if (url.pathname === `/api/v1/guest/jobs/${jobId}`) return route.fulfill({ json: failedJob() })
    return route.fulfill({ status: 404, json: { error: { code: 'not_found' } } })
  })
  return { calls, activate: () => { started = true }, created: () => created }
}

test('GUEST-001 unsigned visitor can run one trial and recover it after reload', async ({ page }) => {
  const app = await workspace(page); app.signedIn = false
  const guest = await mockGuest(page)
  await page.goto('/image')
  await page.getByLabel('Описание').fill('guest browser trial')
  await page.getByRole('button', { name: 'Создать пробную работу' }).click()
  await expect(page.getByText('Создаём работу…')).toBeVisible()
  await expect(page.getByText('Хотите продолжить?')).toBeVisible({ timeout: 5_000 })
  expect(guest.created()).toBe(true)
  expect(guest.calls).toContain('POST /api/v1/guest/start')
  expect(guest.calls).toContain('POST /api/v1/guest/quotes')
  expect(guest.calls).toContain('POST /api/v1/guest/jobs')

  await page.reload()
  await expect(page.getByText('Хотите продолжить?')).toBeVisible()
  expect(guest.calls).toContain('GET /api/v1/guest/jobs')
  expect(app.jobs).toHaveLength(0)
})

test('GUEST-001 registration claims the guest instead of creating a second account', async ({ page }) => {
  const app = await workspace(page); app.signedIn = false
  const guest = await mockGuest(page); guest.activate()
  let claimBody: Record<string, unknown> | null = null
  await page.route('**/api/v1/guest/claim', async route => {
    claimBody = route.request().postDataJSON()
    app.signedIn = true
    app.account = { ...app.account, id: guestId, email: 'claimed@example.invalid',
      display_name: 'Claimed Guest', email_verified: false }
    return route.fulfill({ status: 201, json: { account: app.account, csrf_token: 'c'.repeat(43) } })
  })
  await page.goto('/register')
  await expect(page.getByText('Пробная работа останется в этом аккаунте')).toBeVisible()
  await page.getByLabel('Имя').fill('Claimed Guest')
  await page.getByLabel('Электронная почта').fill('claimed@example.invalid')
  await page.getByLabel('Пароль').fill('synthetic-password-only')
  await page.getByRole('button', { name: 'Создать аккаунт' }).click()
  await expect.poll(() => claimBody).not.toBeNull()
  expect(claimBody).toEqual({ email: 'claimed@example.invalid', password: 'synthetic-password-only',
    display_name: 'Claimed Guest' })
  await expect(page).toHaveURL(/\/$/)
  expect(app.account.id).toBe(guestId)
})
