import { test, expect, type Page } from '@playwright/test'

const account = { id: '11111111-1111-4111-8111-111111111111', public_code: 'shell-user',
  display_name: 'Александр', email: 'shell@example.invalid', email_verified: false, state: 'active', permissions: [] }
const auth = { account, csrf_token: 'c'.repeat(43) }

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/auth/me', route => route.fulfill({ status: 401, json: { error: { code: 'auth_required' } } }))
})

async function signedIn(page: Page) {
  await page.unroute('**/api/v1/auth/me')
  await page.route('**/api/v1/auth/me', route => route.fulfill({ json: auth }))
  await page.route('**/api/v1/credits', route => route.fulfill({ json: {
    account_id: account.id, balance: { balance: 123, available: 123, reserved: 0, sequence: 1 }, entries: [], next_before: null,
  } }))
  await page.route('**/api/v1/entitlements', route => route.fulfill({ json: {
    account_id: account.id, configured: true,
    policy: { capability_ids: ['fal.flux2.klein.4b'], executors: ['api'], image_sizes: [{ width: 64, height: 64 }] },
  } }))
  await page.route('**/api/v1/auth/logout', route => route.fulfill({ status: 204 }))
}

test('HEADER-SHELL-001 canonical routes share one global header', async ({ page }) => {
  for (const path of ['/', '/image', '/video', '/audio', '/3d', '/feed', '/gallery']) {
    await page.goto(path)
    await expect(page.getByTestId('global-header')).toHaveCount(1)
    await expect(page.getByRole('navigation', { name: 'Режимы ИЗО АСА' }).getByRole('link')).toHaveCount(5)
    await expect(page.getByText('Страница не найдена', { exact: true })).toHaveCount(0)
  }
})

test('HEADER-SHELL-001 legacy studio route redirects to canonical destination', async ({ page }) => {
  await page.goto('/studio/video')
  await expect(page).toHaveURL(/\/video$/)
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Видео')
})

test('HEADER-SHELL-001 unauthenticated header exposes login, destinations and neutral tokens only', async ({ page }) => {
  await page.goto('/')
  const header = page.getByTestId('global-header')
  await expect(header.locator('.brand-favicon')).toHaveAttribute('src', '/favicon.svg')
  await expect(header.locator('.brand-izo')).toHaveText('ИЗО')
  await expect(header.locator('.brand-asa')).toHaveText('АСА')
  await expect(header.locator('.brand-izo')).toHaveCSS('color', 'rgb(138, 90, 0)')
  await expect(header.locator('.brand-asa')).toHaveCSS('color', 'rgb(110, 69, 193)')
  await expect(header.getByRole('link', { name: 'Войти', exact: true })).toBeVisible()
  await expect(header.getByRole('link', { name: /Регистрация|Создать аккаунт/ })).toHaveCount(0)
  const explore = header.getByRole('navigation', { name: 'Лента и Галерея' })
  await expect(explore.getByRole('link', { name: 'Лента', exact: true })).toBeVisible()
  await expect(explore.getByRole('link', { name: 'Галерея', exact: true })).toBeVisible()
  await expect(explore.getByRole('link')).toHaveCount(2)
  const tokens = page.getByTestId('global-token-group')
  await expect(tokens.getByTestId('token-daily')).toContainText('0/0')
  await expect(tokens.getByTestId('token-main')).toContainText('0')
  await expect(tokens.locator('[data-icon="sun"]')).toHaveCount(1)
  await expect(tokens.locator('[data-icon="gem"]')).toHaveCount(1)
  await expect(tokens.locator('.token-caption')).toHaveCount(0)
  await expect(tokens).not.toContainText('—')
  await expect(header.locator('.guest-theme')).toHaveCount(0)
  await expect(header).not.toContainText('ASA Auto')
})

test('HEADER-SHELL-001 authenticated header uses real credits and avatar menu', async ({ page }) => {
  await signedIn(page)
  await page.goto('/')
  const header = page.getByTestId('global-header')
  await expect(header.getByRole('link', { name: 'Войти', exact: true })).toHaveCount(0)
  const tokens = page.getByTestId('global-token-group')
  await expect(tokens.getByTestId('token-daily')).toContainText('0/0')
  await expect(tokens.getByTestId('token-main')).toContainText('123')
  await expect(tokens.locator('[data-icon="sun"]')).toHaveCount(1)
  await expect(tokens.locator('[data-icon="gem"]')).toHaveCount(1)
  await expect(page.locator('.chat-sidebar-bottom')).toHaveCount(1)
  await expect(page.locator('.chat-profile-name')).toHaveText('Александр')
  await header.getByRole('button', { name: 'Профиль' }).click()
  const menu = page.getByRole('menu')
  await expect(menu.getByRole('menuitem', { name: 'Аккаунт' })).toBeVisible()
  await expect(menu.getByRole('menuitem', { name: 'Токены' })).toBeVisible()
  await expect(menu.getByRole('menuitem', { name: 'Настройки' })).toBeVisible()
  await expect(menu.getByRole('menuitem', { name: 'Помощь' })).toBeVisible()
  await expect(menu.locator('.social-link')).toHaveCount(4)
  await expect(menu.locator('.social-link[href]')).toHaveCount(2)
  await expect(menu.locator('.social-link[aria-disabled="true"]')).toHaveCount(2)
  await expect(menu.getByRole('menuitem', { name: 'Выйти' })).toBeVisible()
  await menu.getByRole('menuitemradio', { name: 'Тёмная' }).click()
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark')
  await expect(page.locator('html')).toHaveCSS('--color-brand', '#9d78ea')
})

test('HEADER-SHELL-001 desktop geometry stays compact and attached', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await page.goto('/')
  const header = await page.getByTestId('global-header').boundingBox()
  const chat = await page.locator('.chat-page').boundingBox()
  const sidebar = await page.locator('.chat-sidebar').boundingBox()
  expect(header?.x).toBe(0)
  expect(header?.height).toBeGreaterThanOrEqual(51)
  expect(header?.height).toBeLessThanOrEqual(53)
  expect(chat?.x).toBe(0)
  expect(sidebar?.x).toBe(0)
  expect(sidebar?.width).toBe(280)
})

test('SHELL-QUALITY-001 global header stays visible while long pages scroll', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await page.goto('/feed')
  expect(await page.evaluate(() => document.documentElement.scrollHeight > innerHeight)).toBe(true)
  await page.evaluate(() => scrollTo(0, 700))
  await page.waitForTimeout(50)
  const header = await page.getByTestId('global-header').boundingBox()
  expect(header?.y).toBe(0)
})

test('SHELL-QUALITY-001 minimum 320px header has no control collisions', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await page.setViewportSize({ width: 320, height: 568 })
  await page.goto('/')
  const result = await page.evaluate(() => {
    const visible = (element: Element) => {
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity) !== 0 && rect.width > 0
    }
    const controls = [...document.querySelectorAll(
      '.global-brand,.explore-nav .header-route,.token-pill,.login-button,.header-avatar',
    )].filter(visible).map(element => element.getBoundingClientRect())
    let collision = false
    for (let i = 0; i < controls.length; i++) for (let j = i + 1; j < controls.length; j++) {
      const a = controls[i], b = controls[j]
      if (Math.min(a.right, b.right) > Math.max(a.left, b.left)
        && Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top)) collision = true
    }
    return { collision, overflow: document.documentElement.scrollWidth > innerWidth }
  })
  expect(result.collision).toBe(false)
  expect(result.overflow).toBe(false)
})

test('SHELL-QUALITY-001 8K shell scales typography and controls while keeping chat bounded', async ({ page }, info) => {
  test.skip(info.project.name !== 'eight-k')
  await page.goto('/')
  const metrics = await page.evaluate(() => ({
    brand: parseFloat(getComputedStyle(document.querySelector('.global-brand')!).fontSize),
    product: parseFloat(getComputedStyle(document.querySelector('.product-tab')!).fontSize),
    heading: parseFloat(getComputedStyle(document.querySelector('.chat-start-state h1')!).fontSize),
    sidebar: document.querySelector('.chat-sidebar')!.getBoundingClientRect().width,
    composer: document.querySelector('.chat-composer-wrap')!.getBoundingClientRect().width,
    viewport: innerWidth,
  }))
  expect(metrics.brand).toBeGreaterThanOrEqual(34)
  expect(metrics.product).toBeGreaterThanOrEqual(28)
  expect(metrics.heading).toBeGreaterThanOrEqual(72)
  expect(metrics.sidebar).toBeGreaterThanOrEqual(600)
  expect(metrics.composer).toBeGreaterThanOrEqual(2100)
  expect(metrics.composer).toBeLessThan(metrics.viewport / 2)
})

test('SHELL-QUALITY-001 popup Escape closes and returns focus to the opener', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await signedIn(page)
  await page.goto('/')

  const avatar = page.getByTestId('global-header').getByRole('button', { name: 'Профиль' })
  await avatar.click()
  await page.keyboard.press('Escape')
  await expect(page.locator('.profile-menu')).toHaveCount(0)
  await expect(avatar).toBeFocused()

  const model = page.locator('.chat-model-selector')
  await model.click()
  await page.locator('.chat-model-menu').press('Escape')
  await expect(page.locator('.chat-model-menu')).toHaveCount(0)
  await expect(model).toBeFocused()
})

test('HEADER-SHELL-001 authenticated top and sidebar profile controls expose the same account menu', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await signedIn(page)
  await page.goto('/')
  const labels = ['Аккаунт', 'Токены', 'Настройки', 'Помощь']

  const topAvatar = page.getByTestId('global-header').getByRole('button', { name: 'Профиль' })
  await topAvatar.click()
  const topMenu = page.locator('.profile-menu')
  for (const label of labels) await expect(topMenu.getByRole('menuitem', { name: label })).toBeVisible()
  await expect(topMenu.getByText('Тема', { exact: true })).toBeVisible()
  await expect(topMenu.getByRole('menuitemradio', { name: 'Светлая' })).toBeVisible()
  await expect(topMenu.getByRole('menuitemradio', { name: 'Тёмная' })).toBeVisible()
  await expect(topMenu.locator('.social-link')).toHaveCount(4)
  await expect(topMenu.getByRole('menuitem', { name: 'Выйти' })).toBeVisible()
  await topAvatar.click()

  const bottom = page.locator('.chat-sidebar-bottom')
  await expect(bottom).toBeVisible()
  await bottom.getByRole('button', { name: 'Профиль в боковой панели' }).click()
  const bottomMenu = page.locator('.chat-profile-menu')
  for (const label of labels) await expect(bottomMenu.getByRole('menuitem', { name: label })).toBeVisible()
  await expect(bottomMenu.getByText('Тема', { exact: true })).toBeVisible()
  await expect(bottomMenu.getByRole('menuitemradio', { name: 'Светлая' })).toBeVisible()
  await expect(bottomMenu.getByRole('menuitemradio', { name: 'Тёмная' })).toBeVisible()
  await expect(bottomMenu.locator('.social-link')).toHaveCount(4)
  await expect(bottomMenu.getByRole('menuitem', { name: 'Выйти' })).toBeVisible()
})

test('chat-first home keeps V53 controls inside composer without fake server behaviour', async ({ page }) => {
  await page.goto('/')
  const composer = page.locator('.chat-composer')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Чем я могу помочь?')
  await expect(composer.getByRole('textbox', { name: 'Сообщение' })).toBeVisible()
  await expect(page.locator('.chat-toolbar .chat-model-selector')).toHaveCount(0)
  await expect(page.locator('.chat-new-mobile')).toHaveCount(0)

  const plus = composer.getByRole('button', { name: 'Добавить', exact: true })
  await expect(plus).toBeEnabled()
  await plus.click()
  const tools = page.getByRole('menu', { name: 'Инструменты' })
  for (const label of ['Добавить файл', 'Создать изображение', 'Создать видео', 'Создать звук', 'Создать 3D', 'Поиск в интернете']) {
    await expect(tools.getByRole('menuitem', { name: label, exact: true })).toBeVisible()
  }
  await tools.getByRole('menuitem', { name: 'Создать изображение', exact: true }).click()
  await expect(composer.getByRole('button', { name: 'Убрать инструмент: Создать изображение' })).toBeVisible()
  await plus.click()
  const selectedImage = page.getByRole('menu', { name: 'Инструменты' }).getByRole('menuitem', { name: 'Создать изображение' })
  await expect(selectedImage).toHaveAttribute('aria-pressed', 'true')
  await selectedImage.click()

  const model = composer.getByRole('button', { name: 'Выбрать модель' })
  await expect(model).toContainText('Авто')
  await model.click()
  const models = page.getByRole('menu', { name: 'Модели' })
  await expect(models.getByRole('menuitemradio', { name: 'Авто' })).toHaveAttribute('aria-checked', 'true')
  await expect(models.locator('.chat-model-category')).toHaveCount(5)
  for (const category of ['Текст', 'Изображения', 'Видео', 'Звук', '3D']) {
    await expect(models.locator('summary').filter({ hasText: category })).toBeVisible()
  }
  await page.locator('.chat-toolbar').click({ position: { x: 200, y: 10 } })
  await expect(page.getByRole('menu', { name: 'Модели' })).toHaveCount(0)

  await plus.click()
  await page.getByRole('menu', { name: 'Инструменты' }).getByRole('menuitem', { name: 'Поиск в интернете' }).click()
  await expect(composer.getByRole('button', { name: 'Убрать инструмент: Поиск в интернете' })).toBeVisible()

  const mic = composer.getByRole('button', { name: 'Микрофон' })
  await expect(mic).toBeEnabled()
  await expect(mic.locator('[data-icon="mic"]')).toHaveCount(1)

  await composer.getByRole('textbox', { name: 'Сообщение' }).fill('Проверка')
  await composer.getByRole('button', { name: 'Отправить' }).click()
  await expect(page.getByRole('status')).toContainText('пока не подключён к серверу')
})
test('HEADER-SHELL-001 authenticated model menu exposes only configured catalog entries', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await signedIn(page)
  await page.goto('/')
  const model = page.locator('.chat-composer').getByRole('button', { name: 'Выбрать модель' })
  await model.click()
  const menu = page.getByRole('menu', { name: 'Модели' })
  const image = menu.locator('.chat-model-category').filter({ hasText: 'Изображения' })
  await image.locator('summary').click()
  await expect(image.getByRole('menuitemradio', { name: 'FLUX.2 [klein] 4B' })).toBeVisible()
  await image.getByRole('menuitemradio', { name: 'FLUX.2 [klein] 4B' }).click()
  await expect(model).toContainText('FLUX.2 [klein] 4B')
})

test('HEADER-SHELL-001 mic uses analyser waveform and stops cleanly', async ({ page }, info) => {
  test.skip(info.project.name !== 'laptop')
  await page.addInitScript(() => {
    class FakeAnalyser {
      fftSize = 128
      smoothingTimeConstant = 0
      frequencyBinCount = 64
      getByteFrequencyData(target: Uint8Array) { target.fill(170) }
    }
    class FakeSource {
      connect() {}
      disconnect() {}
    }
    class FakeAudioContext {
      state = 'running'
      createAnalyser() { return new FakeAnalyser() }
      createMediaStreamSource() { return new FakeSource() }
      async resume() {}
      async close() { this.state = 'closed' }
    }
    Object.defineProperty(window, 'AudioContext', { configurable: true, value: FakeAudioContext })
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: async () => ({ getTracks: () => [{ stop() {}, addEventListener() {} }] }) },
    })
  })
  await page.goto('/')
  const composer = page.locator('.chat-composer')
  await composer.getByRole('button', { name: 'Микрофон' }).click()
  await expect(composer.getByRole('status', { name: 'Микрофон активен' })).toBeVisible()
  await expect(composer.locator('.chat-voice-waveform > span')).toHaveCount(48)
  await page.waitForTimeout(80)
  const transforms = await composer.locator('.chat-voice-waveform > span').evaluateAll(elements =>
    elements.map(element => (element as HTMLElement).style.transform))
  expect(transforms.some(value => value && value !== 'scaleY(0.08)')).toBe(true)
  await composer.getByRole('button', { name: 'Остановить микрофон' }).click()
  await expect(composer.locator('.chat-voice-waveform')).toHaveCount(0)
  await expect(composer.getByRole('textbox', { name: 'Сообщение' })).toBeVisible()
})

test('HEADER-SHELL-001 mobile chat shell follows visual viewport shrink', async ({ page }, info) => {
  test.skip(info.project.name !== 'phone')
  await page.goto('/')
  await page.getByRole('textbox', { name: 'Сообщение' }).focus()
  await page.setViewportSize({ width: 390, height: 560 })
  await page.waitForTimeout(80)
  const metrics = await page.evaluate(() => {
    const app = document.querySelector('.app.chat-shell')!.getBoundingClientRect()
    const header = document.querySelector('[data-testid="global-header"]')!.getBoundingClientRect()
    const composer = document.querySelector('.chat-composer')!.getBoundingClientRect()
    return {
      visualHeight: window.visualViewport?.height ?? innerHeight,
      cssHeight: parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--chat-viewport-height')),
      appTop: app.top, appBottom: app.bottom, headerTop: header.top, headerBottom: header.bottom,
      composerBottom: composer.bottom,
    }
  })
  expect(Math.abs(metrics.cssHeight - metrics.visualHeight)).toBeLessThanOrEqual(1)
  expect(metrics.appTop).toBeGreaterThanOrEqual(0)
  expect(metrics.headerTop).toBeGreaterThanOrEqual(0)
  expect(metrics.composerBottom).toBeLessThanOrEqual(metrics.visualHeight + 1)
})

test('HEADER-SHELL-001 file tool opens the system chooser and renders a removable attachment chip', async ({ page }) => {
  await page.goto('/')
  const composer = page.locator('.chat-composer')
  await composer.getByRole('button', { name: 'Добавить', exact: true }).click()
  const chooserPromise = page.waitForEvent('filechooser')
  await page.getByRole('menu', { name: 'Инструменты' }).getByRole('menuitem', { name: 'Добавить файл' }).click()
  const chooser = await chooserPromise
  await chooser.setFiles({ name: 'reference.txt', mimeType: 'text/plain', buffer: Buffer.from('reference') })
  await expect(composer.locator('.attachment-chip')).toContainText('reference.txt')
  await composer.getByRole('button', { name: 'Удалить вложение' }).click()
  await expect(composer.locator('.attachment-chip')).toHaveCount(0)
})

test('HEADER-SHELL-001 chat sidebar follows V53 controls and belongs only to chat', async ({ page }) => {
  await page.goto('/')
  const sidebar = page.locator('.chat-sidebar')
  await expect(sidebar).toHaveCount(1)
  const opener = page.getByRole('button', { name: 'Открыть панель' })
  if (await opener.isVisible()) await opener.click()
  await expect(sidebar.getByRole('button', { name: 'Новый чат' })).toHaveCount(1)
  await sidebar.getByRole('button', { name: 'Поиск чатов' }).click()
  await expect(sidebar.getByRole('textbox', { name: 'Поиск по чатам' })).toBeVisible()
  await expect(sidebar.getByText('Чаты', { exact: true })).toBeVisible()
  await expect(sidebar.locator('[data-icon="panel"]')).toHaveCount(1)
  await page.goto('/image')
  await expect(page.locator('.chat-sidebar')).toHaveCount(0)
})

test('HEADER-SHELL-001 chat search replaces history title and filters real local chats', async ({ page }) => {
  await page.goto('/')
  const composer = page.locator('.chat-composer')
  const sidebar = page.locator('.chat-sidebar')
  const openSidebar = async () => {
    const opener = page.getByRole('button', { name: 'Открыть панель' })
    if (await opener.isVisible()) await opener.click()
  }
  await composer.getByRole('textbox', { name: 'Сообщение' }).fill('Первый проект')
  await composer.getByRole('button', { name: 'Отправить' }).click()
  await openSidebar()
  await sidebar.getByRole('button', { name: 'Новый чат' }).click()
  await composer.getByRole('textbox', { name: 'Сообщение' }).fill('Второй проект')
  await composer.getByRole('button', { name: 'Отправить' }).click()
  await openSidebar()

  await expect(sidebar.getByRole('button', { name: 'Первый проект' })).toBeVisible()
  await expect(sidebar.getByRole('button', { name: 'Второй проект' })).toBeVisible()
  await sidebar.getByRole('button', { name: 'Поиск чатов' }).click()
  await expect(sidebar.getByText('История', { exact: true })).toHaveCount(0)
  const search = sidebar.getByRole('textbox', { name: 'Поиск по чатам' })
  await expect(search).toBeVisible()
  await search.fill('Первый')
  await expect(sidebar.getByRole('button', { name: 'Первый проект' })).toBeVisible()
  await expect(sidebar.getByRole('button', { name: 'Второй проект' })).toHaveCount(0)
})

test('HEADER-SHELL-001 mobile starts with chat sidebar collapsed', async ({ page }, info) => {
  test.skip(!info.project.name.startsWith('phone'))
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Открыть панель' })).toBeVisible()
  const box = await page.locator('.chat-sidebar').boundingBox()
  expect(box ? box.x + box.width : 1).toBeLessThanOrEqual(0)
})

test('HEADER-SHELL-001 mobile authenticated tokens reserve room for three digits', async ({ page }, info) => {
  test.skip(!info.project.name.startsWith('phone'))
  await signedIn(page)
  await page.goto('/')
  await expect(page.getByTestId('token-main')).toContainText('123')
  const width = (await page.getByTestId('token-main').boundingBox())?.width ?? 0
  expect(width).toBeGreaterThanOrEqual(46)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('help keeps the existing intent-driven visual WIP copy', async ({ page }) => {
  await page.goto('/help')
  await expect(page.getByText('Начните с обычного запроса и выберите инструмент, если нужен результат другого типа.', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Опишите задачу обычным языком. Прямые инструменты для изображений, видео, звука и 3D доступны отдельными разделами.', { exact: true })).toBeVisible()
})

test('feed remains a separate public explore page', async ({ page }) => {
  await page.goto('/feed')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Создавайте, смотрите и развивайте идеи')
  await expect(page.locator('.feed-card')).toHaveCount(6)
})

test('HEADER-SHELL-001 mobile keeps one compact header and five product destinations', async ({ page }, info) => {
  test.skip(!info.project.name.startsWith('phone'))
  await page.goto('/')
  const header = page.getByTestId('global-header')
  await expect(header.getByRole('link', { name: 'Лента', exact: true })).toBeVisible()
  await expect(header.getByRole('link', { name: 'Галерея', exact: true })).toBeVisible()
  await expect(header.getByRole('link', { name: 'Войти', exact: true })).toBeVisible()
  const products = page.getByRole('navigation', { name: 'Режимы ИЗО АСА' })
  await expect(products.getByRole('link')).toHaveCount(5)
  await expect(products.getByRole('link', { name: 'Изображение', exact: true })).toBeVisible()
  await expect(page.getByTestId('global-token-group').getByTestId('token-daily')).toContainText('0/0')
  await expect(page.getByTestId('global-token-group').getByTestId('token-main')).toContainText('0')
  const height = (await header.boundingBox())?.height ?? 0
  expect(height).toBeGreaterThanOrEqual(63)
  expect(height).toBeLessThanOrEqual(65)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('HEADER-SHELL-001 shell has no horizontal overflow at the configured viewport', async ({ page }) => {
  await page.goto('/')
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

test('8K feed uses wide canvas without stretching reading text', async ({ page }, info) => {
  test.skip(info.project.name !== 'eight-k')
  await page.goto('/feed')
  const grid = page.locator('.feed-grid')
  const columns = await grid.evaluate(element => getComputedStyle(element).gridTemplateColumns.split(' ').length)
  expect(columns).toBeGreaterThanOrEqual(8)
  expect((await grid.boundingBox())?.width ?? 0).toBeGreaterThan(4000)
  expect((await page.locator('.feed-hero-copy').boundingBox())?.width ?? 9999).toBeLessThan(1000)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
})

for (const host of ['telegram', 'max'] as const) {
  test(`host hint ${host} reuses shell and grants no account`, async ({ page }) => {
    await page.addInitScript(kind => {
      const w = window as Window & { Telegram?: object; WebApp?: object }
      if (kind === 'telegram') w.Telegram = { WebApp: { initDataUnsafe: { user: { id: 1 } } } }
      else w.WebApp = { initData: 'untrusted-test-input' }
    }, host)
    await page.goto('/login')
    await expect(page.locator('.app')).toHaveAttribute('data-platform', host)
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Войти')
    await expect(page.getByRole('button', { name: 'Войти', exact: true })).toBeVisible()
    await expect(page.getByTestId('server-account')).toHaveCount(0)
  })
}
