import { expect, test, type Page } from '@playwright/test'
import { branches, editFixture, editRow, editor, gate, openEditThread } from './chat-message-edit-fixture'
import { asset } from './workspace-fixtures'

const imageId = '22222222-2222-4222-8222-999999999999'
const attachment = { ...asset(imageId), asset_id: imageId, media_type: 'image/png' as const }

const composer = (page: Page) => page.getByRole('textbox', { name: 'Сообщение', exact: true })
const save = (page: Page) => page.getByRole('button', { name: 'Сохранить и отправить', exact: true })
const cancel = (page: Page) => page.getByRole('button', { name: 'Отмена', exact: true })
async function open(page: Page) { await page.goto('/'); await openEditThread(page) }

for (const close of ['Escape', 'Отмена']) test(`Edit ${close} retains original DOM, copy and composer focus`, async ({ page }) => {
  const fixture = await editFixture(page)
  await open(page)
  const message = fixture.active().turns[0].user_message, row = editRow(page, message.id)
  const original = row.locator('[data-message-id]'), trigger = row.getByRole('button', { name: 'Изменить' })
  await original.evaluate(node => { (node as HTMLElement).dataset.identity = 'original' })
  await composer(page).fill('Мой черновик')
  await composer(page).evaluate(node => { (node as HTMLElement).dataset.identity = 'composer' })
  await row.getByRole('button', { name: 'Копировать', exact: true }).click()
  await trigger.click()
  await expect(editor(page)).toBeFocused()
  await expect(save(page)).toBeDisabled()
  await editor(page).fill('Изменённый черновик')
  if (close === 'Escape') await editor(page).press('Escape')
  else await cancel(page).click()
  await expect(trigger).toBeFocused()
  await expect(original).toHaveAttribute('data-identity', 'original')
  await expect(original).toContainText(message.content)
  await expect(composer(page)).toHaveValue('Мой черновик')
  await expect(composer(page)).toHaveAttribute('data-identity', 'composer')
  await expect(page.locator(`[data-message-id="${message.id}"]`)).toHaveCount(1)
  expect(fixture.state.commands).toHaveLength(0)
})

test('Save creates a visible child, preserves prefix anchors, draft, model and the original branch', async ({ page }) => {
  const fixture = await editFixture(page)
  const parent = fixture.active(), source = parent.turns[1]
  fixture.state.pause.events = gate()
  await open(page)
  await composer(page).fill('Черновик следующего сообщения')
  const prefix = editRow(page, parent.turns[0].user_message.id)
  await prefix.evaluate(node => { (node as HTMLElement).dataset.identity = 'prefix' })
  await editRow(page, source.user_message.id).getByRole('button', { name: 'Изменить' }).click()
  await expect(page.getByRole('form', { name: 'Редактирование сообщения' })).toContainText('deepseek-flash')
  await editor(page).fill('Новый вопрос')
  await save(page).click()
  await expect.poll(() => fixture.state.events.length).toBe(1)
  await expect(page.getByText('Новый вопрос', { exact: true })).toBeVisible()
  await expect(branches(page)).toBeDisabled()
  await expect(page.locator('.chat-branch-controls')).toBeFocused()
  await expect(prefix).toHaveAttribute('data-identity', 'prefix')
  await expect(composer(page)).toHaveValue('Черновик следующего сообщения')
  expect(parent.turns.map(turn => turn.user_message.content)).toEqual(['Вопрос 1', 'Вопрос 2', 'Вопрос 3'])
  const command = fixture.state.commands.find(item => item.path.endsWith('/edit'))!
  expect(command.body).toMatchObject({ text: 'Новый вопрос', branch_id: parent.meta.id,
    source_attempt_id: source.selected_attempt_id, expected_revision: 1 })
  expect(command.body).not.toHaveProperty('attachment_ids')
  fixture.state.pause.events.release()
  await expect(branches(page)).toBeEnabled()
  await expect(page.getByText('Ответ на: Новый вопрос', { exact: true })).toBeVisible()
  const child = fixture.state.active
  await branches(page).selectOption(parent.meta.id)
  await expect(page.getByText('Вопрос 3', { exact: true })).toBeVisible()
  await expect(page.getByText('Новый вопрос', { exact: true })).toHaveCount(0)
  await branches(page).selectOption(child)
  await page.reload(); await openEditThread(page)
  await expect(branches(page)).toHaveValue(child)
  await expect(page.getByText('Новый вопрос', { exact: true })).toBeVisible()
})

test('an async accepted save respects deliberate focus outside the editor', async ({ page }) => {
  const fixture = await editFixture(page)
  fixture.state.pause.edit = gate()
  await open(page)
  await editRow(page, fixture.active().turns[1].user_message.id).getByRole('button', { name: 'Изменить' }).click()
  await editor(page).fill('Отредактировано')
  await save(page).click()
  await expect.poll(() => fixture.state.commands.length).toBe(1)
  await composer(page).fill('Продолжаю писать')
  await composer(page).focus()
  fixture.finish(fixture.state.commands[0].body.request_id)
  fixture.state.pause.edit.release()
  await expect(page.getByText('Отредактировано', { exact: true })).toBeVisible()
  await expect(composer(page)).toHaveValue('Продолжаю писать')
  await expect(composer(page)).toBeFocused()
  expect(fixture.state.events).toHaveLength(0)
})

test('server rejection preserves draft, images, source renderer and a working cancel', async ({ page }) => {
  const fixture = await editFixture(page)
  const source = fixture.active().turns[0]
  source.user_message.attachments = [attachment]
  fixture.state.reject = 'message_unchanged'
  await open(page)
  const row = editRow(page, source.user_message.id), image = row.locator('.chat-message-image')
  await image.evaluate(node => { (node as HTMLElement).dataset.identity = 'asset' })
  await row.getByRole('button', { name: 'Изменить' }).click()
  await editor(page).fill('Черновик для проверки')
  await save(page).click()
  await expect(row.getByRole('alert').last()).toBeVisible()
  await expect(editor(page)).toHaveValue('Черновик для проверки')
  await expect(image).toHaveAttribute('data-identity', 'asset')
  await expect(row.locator('[data-message-id]')).toHaveCount(1)
  await cancel(page).click()
  await expect(row.getByRole('button', { name: 'Изменить' })).toBeFocused()
  expect(fixture.all.size).toBe(1)
})

test('opening persisted CRLF never creates a change; actual input and reversion follow server text', async ({ page }) => {
  const fixture = await editFixture(page)
  fixture.active().turns[0].user_message.content = 'A\r\nB'
  await open(page)
  const trigger = editRow(page, fixture.active().turns[0].user_message.id).getByRole('button', { name: 'Изменить' })
  await trigger.click()
  await expect(save(page)).toBeDisabled()
  await composer(page).focus(); await editor(page).focus()
  await expect(save(page)).toBeDisabled()
  await cancel(page).click(); await trigger.click()
  await expect(save(page)).toBeDisabled()
  await editor(page).fill('A\nB!')
  await expect(save(page)).toBeEnabled()
  await editor(page).press('Backspace')
  await expect(save(page)).toBeEnabled()
  await cancel(page).click(); await trigger.click()
  await expect(save(page)).toBeDisabled()
  expect(fixture.state.commands).toHaveLength(0)
})

const unchanged = 'Сообщение не изменено'
const cases: { name: string; original: string; draft: string; error?: string; images?: boolean }[] = [
  { name: 'exact', original: 'A', draft: 'A', error: unchanged },
  { name: 'ordinary boundaries', original: 'A', draft: '\t A\r\n', error: unchanged },
  { name: 'NEL', original: 'A', draft: '\x85A\x85', error: unchanged },
  { name: 'C0 separators', original: 'A', draft: '\x1cA\x1d\x1e\x1f', error: unchanged },
  { name: 'Unicode spaces', original: 'A', draft: '\xa0\u2003A\u202f\u3000', error: unchanged },
  { name: 'BOM retained', original: 'A', draft: '\ufeffA\ufeff' },
  { name: 'zero width retained', original: 'A', draft: '\u200bA\u200b' },
  { name: 'interior spaces', original: 'A B', draft: 'A  B' },
  { name: 'interior CRLF', original: 'A\r\nB', draft: 'A\nB' },
  { name: 'NFC versus NFD', original: 'é', draft: 'e\u0301' },
  { name: 'case preserved', original: 'a', draft: 'A' },
  { name: 'raw 6000 unchanged', original: 'A'.repeat(5999), draft: ' ' + 'A'.repeat(5999), error: unchanged },
  { name: 'raw 6001 before strip', original: 'A'.repeat(6000), draft: ' ' + 'A'.repeat(6000), error: '6000' },
  { name: '6000 supplementary codepoints', original: '😀'.repeat(5999), draft: '😀'.repeat(6000) },
  { name: '6001 supplementary codepoints', original: '😀'.repeat(6000), draft: '😀'.repeat(6001), error: '6000' },
  { name: 'NUL', original: 'A', draft: 'A\0', error: 'недопустимый' },
  { name: 'image only unchanged', original: '', draft: ' \x85 ', images: true, error: unchanged },
  { name: 'retained image caption removed', original: 'Подпись', draft: ' \x85 ', images: true },
  { name: 'text only cleared', original: 'A', draft: ' \x85 ', error: 'Введите' },
]
for (const entry of cases) test(`D5 ${entry.name}: no premature admission or lost raw codepoints`, async ({ page }, info) => {
  test.skip(!['phone-small', 'laptop'].includes(info.project.name))
  const fixture = await editFixture(page, 1), message = fixture.active().turns[0].user_message
  message.content = entry.original
  if (entry.images) message.attachments = [attachment]
  await open(page)
  await editRow(page, message.id).getByRole('button', { name: 'Изменить' }).click()
  // Trigger input even when CRLF already renders as LF.
  await editor(page).fill('temporary input')
  await editor(page).fill(entry.draft)
  if (entry.error) {
    await expect(save(page)).toBeDisabled()
    await expect(page.getByRole('form', { name: 'Редактирование сообщения' })).toContainText(entry.error)
  } else await expect(save(page)).toBeEnabled()
  expect(fixture.state.commands).toHaveLength(0)
  expect(fixture.all.size).toBe(1)
})

test('all Python boundary whitespace and concurrent unchanged submissions stay inert', async ({ page }) => {
  const fixture = await editFixture(page, 1)
  fixture.active().turns[0].user_message.content = 'A'
  const boundary = [...Array(5)].map((_, n) => n + 9).concat([28, 29, 30, 31, 32, 133, 160, 5760],
    [...Array(11)].map((_, n) => n + 8192), [8232, 8233, 8239, 8287, 12288])
  expect(boundary).toHaveLength(29)
  await open(page)
  await editRow(page, fixture.active().turns[0].user_message.id).getByRole('button', { name: 'Изменить' }).click()
  await editor(page).fill(String.fromCodePoint(...boundary) + 'A' + String.fromCodePoint(...boundary))
  await expect(save(page)).toBeDisabled()
  await page.getByRole('form', { name: 'Редактирование сообщения' }).evaluate(form => {
    (form as HTMLFormElement).requestSubmit(); (form as HTMLFormElement).requestSubmit()
  })
  expect(fixture.state.commands).toHaveLength(0)
  expect(fixture.state.revision).toBe(1)
})

for (const theme of ['light', 'dark']) test(`${theme}: editor respects viewport, coarse targets and an older reading anchor`, async ({ page }, info) => {
  test.skip(!['phone-small', 'laptop'].includes(info.project.name))
  const fixture = await editFixture(page, 60)
  await page.addInitScript(value => localStorage.setItem('izo-theme', value), theme)
  await open(page)
  await page.getByRole('button', { name: 'Загрузить ранние сообщения', exact: true }).click()
  await expect(page.locator('.chat-turn-user')).toHaveCount(60)
  const row = editRow(page, fixture.active().turns[20].user_message.id)
  await row.scrollIntoViewIfNeeded()
  const anchor = await row.boundingBox()
  const trigger = row.getByRole('button', { name: 'Изменить' })
  await trigger.click(); await editor(page).fill('Длинный текст '.repeat(150))
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
  const bounds = await editor(page).boundingBox()
  expect(bounds!.x).toBeGreaterThanOrEqual(0)
  expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
  if (info.project.name === 'phone-small') expect((await cancel(page).boundingBox())!.height).toBeGreaterThanOrEqual(44)
  await cancel(page).click()
  await expect.poll(async () => Math.abs((await row.boundingBox())!.y - anchor!.y)).toBeLessThan(4)
})
