// Isolated account setup and live search before/after retained-volume restart.
import { writeFile } from 'node:fs/promises'
import { expect } from '@playwright/test'
import { command } from './chat-message-edit-live.mjs'
import { marker, other, literal, input, ids, path, checkRows, panel, query, pages,
  rename, logout, snapshot, searchHistory, openGraph } from './chat-search-ui-live.mjs'

async function run(phase, context, authenticate, state, legacyPage, folder, observe) {
  const origin = new URL(legacyPage.url()).origin
  if (process.env.IZO_ENVIRONMENT !== 'test' || process.env.IZO_CHAT_ACCEPTANCE !== 'isolated'
    || !['http://localhost:8080', 'http://127.0.0.1:18080'].includes(origin)) throw new Error('Isolated search stack required')
  const ctx = await context(true)
  const report = { phase, origin, source_sha: process.env.IZO_SOURCE_SHA, build_sha: process.env.IZO_BUILD_SHA,
    status: 'RUNNING', requests: [], admissions: [], has_touch: true }
  try {
    const page = await ctx.newPage()
    page.on('response', response => {
      const url = new URL(response.url())
      if (url.pathname === '/api/v1/chat/threads' && response.request().method() === 'GET')
        report.requests.push({ q: url.searchParams.get('q'), cursor: url.searchParams.get('cursor'), status: response.status() })
    })
    page.on('request', request => {
      const url = new URL(request.url())
      if (request.method() === 'POST' && url.pathname.startsWith('/api/v1/chat/') && url.pathname !== '/api/v1/chat/threads')
        report.admissions.push(url.pathname)
    })
    let proof = state.search
    await authenticate(page, proof?.email ?? 'search@local.izo', state.passphrase, phase === 'before')
    if (phase === 'before') {
      const seeded = []
      for (let index = 0; index < 151; index++) seeded.push(await command(page, 'threads', 'POST', {
        title: `${index < 103 ? marker : other} ${String(index).padStart(3, '0')}${index === 0 ? ` ${literal}` : ''}`,
      }, 201))
      const ordered = await pages(page, null, 151), matching = new Set(ids(seeded.slice(0, 103)))
      proof = { email: 'search@local.izo', ids: ids(ordered.threads), literal: seeded[0].id,
        matches: ids(ordered.threads).flatMap((id, index) => matching.has(id) ? [index] : []) }
      proof.target = proof.matches.find(index => index >= 100)
      proof.foreign = (await command(legacyPage, 'threads', 'POST', { title: `${marker} foreign` }, 201)).id
    }
    expect(proof.ids).toHaveLength(151); expect(proof.matches).toHaveLength(103); expect(proof.target).toBeGreaterThanOrEqual(100)
    const ordinary = await pages(page, null, 151), matches = proof.matches.map(index => proof.ids[index])
    expect(ids(ordinary.threads)).toEqual(proof.ids)
    const searched = await pages(page, '  аРхИв izO  ', 103)
    expect(ids(searched.threads)).toEqual(matches)
    expect((await command(page, `threads/${proof.foreign}`, 'GET', undefined, 404)).error.code).toBe('thread_not_found')
    report.ordinary = { ids: proof.ids, pages: ordinary.lengths }; report.search = { ids: matches, pages: searched.lengths, target_rank: proof.target + 1 }
    report.viewports = await searchHistory(page, proof, ordinary, matches, phase, folder)
    if (phase === 'before') {
      const original = ordinary.threads.find(thread => thread.id === matches[0]), title = 'Renamed IZO'
      await query(page, marker); await rename(page, original.title, title)
      expect(ids((await pages(page, marker, 102)).threads)).toEqual(matches.slice(1))
      await query(page, title); await rename(page, title, original.title)
      expect(ids((await pages(page, marker, 103)).threads)).toEqual(matches)
      report.rename_membership = [103, 102, 103]
    }
    const baseline = await snapshot(legacyPage, state.edit), contexts = structuredClone(state.edit.contexts)
    const cursor = (await command(page, path(marker))).next_cursor
    await logout(page); await authenticate(page, state.email, state.passphrase)
    await panel(page); await expect(input(page)).toHaveCount(0)
    expect(ids((await query(page, marker)).threads)).toEqual([proof.foreign])
    expect((await command(page, path(marker, cursor), 'GET', undefined, 400)).error.code).toBe('invalid_thread_cursor')
    await openGraph(page, state.edit, baseline, phase, folder)
    expect(await observe(state.edit)).toEqual(contexts)
    report.graph = { revision: baseline.graph.revision, active_branch_id: baseline.graph.active_branch_id,
      selected: baseline.graph.turns.map(turn => turn.selected_attempt_id), branches: 3, physical_messages: baseline.detail.messages.length,
      retained_contexts: contexts.length, unchanged: true }
    await logout(page); await authenticate(page, proof.email, state.passphrase)
    await panel(page); await expect(input(page)).toHaveCount(0)
    await checkRows(page, proof.ids.slice(0, 50)); await query(page, marker)
    await checkRows(page, matches.slice(0, 50))
    report.account_switch = 'A -> B -> A'; expect(report.admissions).toEqual([])
    expect(Buffer.byteLength(JSON.stringify(proof))).toBeLessThanOrEqual(12288)
    expect(Buffer.byteLength(JSON.stringify({ ...state, search: proof }))).toBeLessThanOrEqual(65536)
    report.status = 'PASS'
    console.log(`CHAT_SEARCH_${phase.toUpperCase()}_OK: 151 owned / 103 matches / UI, isolation, retained Graph/context`)
    return proof
  } catch (error) { report.status = 'FAIL'; report.error = String(error.stack ?? error); throw error }
  finally {
    try { await writeFile(`${folder}/search-${phase}-${new URL(origin).port}.json`, JSON.stringify(report, null, 2)) }
    finally { await ctx.close() }
  }
}
export const searchBefore = (...args) => run('before', ...args)
export const searchAfter = (...args) => run('after', ...args)
