import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { gunzipSync } from 'node:zlib'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const parts = [0, 1, 2, 3].map(index => fileURLToPath(
  new URL(`../../../packages/contracts/openapi.json.gz.b64.part${index}`, import.meta.url)))
const cacheDir = fileURLToPath(new URL('../node_modules/.cache', import.meta.url))
const temporary = `${cacheDir}/izo-openapi.json`
const cli = fileURLToPath(new URL('../node_modules/openapi-typescript/bin/cli.js', import.meta.url))
const output = fileURLToPath(new URL('../src/shared/api.generated.ts', import.meta.url))

mkdirSync(cacheDir, { recursive: true })
try {
  const encoded = parts.map(path => readFileSync(path, 'ascii')).join('')
  writeFileSync(temporary, gunzipSync(Buffer.from(encoded, 'base64')))
  const result = spawnSync(process.execPath, [cli, temporary, '-o', output], { stdio: 'inherit' })
  if (result.error) throw result.error
  if (result.status !== 0) process.exitCode = result.status ?? 1
} finally {
  rmSync(temporary, { force: true })
}
