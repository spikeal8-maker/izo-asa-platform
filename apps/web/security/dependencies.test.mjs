import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import test from 'node:test';

// Resolve the parser actually used by the code generator, not an unrelated root copy.
const project = createRequire(new URL('../package.json', import.meta.url));
const generator = createRequire(project.resolve('openapi-typescript'));
const redocly = createRequire(generator.resolve('@redocly/openapi-core'));
const yaml = redocly('js-yaml');

function patched(version) {
  const match = /^(\d+)\.(\d+)\.(\d+)$/.exec(version);
  if (!match) return false;
  const [major, minor, patch] = match.slice(1).map(Number);
  return (major === 4 && (minor > 3 || (minor === 3 && patch >= 2)))
    || (major === 3 && (minor > 15 || (minor === 15 && patch >= 2)))
    || major >= 5;
}

test('SEC-001 resolved js-yaml and every locked copy exclude the affected v3/v4 range', () => {
  assert.ok(patched(redocly('js-yaml/package.json').version));
  const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url), 'utf8'));
  const parsers = Object.entries(lock.packages).filter(([path]) => /(^|\/)node_modules\/js-yaml$/.test(path));
  assert.ok(parsers.length > 0, 'The generator parser must not disappear silently');
  for (const [path, entry] of parsers) assert.ok(patched(entry.version), path);
});

test('SEC-001 empty merge sources consume the explicit work budget', () => {
  // Tiny local input, four mappings: demonstrates the bug without a load/DoS test.
  const source = 'base: &empty [{}, {}, {}, {}]\nvalue: { <<: *empty }\n';
  assert.throws(() => yaml.load(source, { maxTotalMergeKeys: 2 }), /maxTotalMergeKeys/);
});

test('SEC-001 ordinary YAML merge remains compatible', () => {
  const source = 'defaults: &defaults {kind: image}\njob: {<<: *defaults, count: 1}\n';
  assert.deepEqual(yaml.load(source, { maxTotalMergeKeys: 8 }).job, { kind: 'image', count: 1 });
});

test('SEC-001 the real generated OpenAPI JSON remains readable by the parser', () => {
  const path = fileURLToPath(new URL('../../../packages/contracts/openapi.json', import.meta.url));
  const text = readFileSync(path, 'utf8');
  const parsed = yaml.load(text);
  assert.deepEqual(parsed, JSON.parse(text));
  assert.ok(parsed.paths['/api/v1/credits'], 'Credits API must remain in the source schema');
});
