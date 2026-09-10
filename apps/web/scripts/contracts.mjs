import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { gunzipSync } from 'node:zlib'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const schema = fileURLToPath(new URL('../../../packages/contracts/openapi.json.gz.b64', import.meta.url))
const cacheDir = fileURLToPath(new URL('../node_modules/.cache', import.meta.url))
const temporary = `${cacheDir}/izo-openapi.json`
const cli = fileURLToPath(new URL('../node_modules/openapi-typescript/bin/cli.js', import.meta.url))
const output = fileURLToPath(new URL('../src/shared/api.generated.ts', import.meta.url))

function compressedSnapshot() {
  const encoded = readFileSync(schema, 'ascii').replace(/\s+/g, '')
  if (!encoded || encoded.length % 4 !== 0 || !/^[A-Za-z0-9+/]+={0,2}$/.test(encoded))
    throw new Error('Invalid OpenAPI snapshot encoding')
  const compressed = Buffer.from(encoded, 'base64')
  if (compressed.toString('base64') !== encoded) throw new Error('Non-canonical OpenAPI snapshot encoding')
  return compressed
}

mkdirSync(cacheDir, { recursive: true })
try {
  writeFileSync(temporary, gunzipSync(compressedSnapshot()))
  const result = spawnSync(process.execPath, [cli, temporary, '-o', output], { stdio: 'inherit' })
  if (result.error) throw result.error
  if (result.status !== 0) process.exitCode = result.status ?? 1
} finally {
  rmSync(temporary, { force: true })
}
