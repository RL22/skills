#!/usr/bin/env node
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { describeSource, SNAPSHOT_FORMAT_VERSION } from '../scripts/snapshot.mjs';
import { BREAKPOINTS, captureBundle, RESPONSIVE_BUNDLE_VERSION, validateCaptureBundle } from '../scripts/responsive.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const SNAPSHOT = join(HERE, '..', 'scripts', 'snapshot.mjs');
const tmp = mkdtempSync(join(tmpdir(), 'sketch-capture-'));
const sha256 = (value) => createHash('sha256').update(value).digest('hex');
let failed = 0;
const check = async (name, fn) => {
  try { await fn(); console.log(`PASS ${name}`); }
  catch (error) { failed++; console.log(`FAIL ${name}: ${error.stack || error.message}`); }
};

function fixture(name, body = '<!doctype html><title>fixture</title>') {
  const file = join(tmp, name);
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, body);
  return file;
}

function makeBundle(base, source) {
  const captures = BREAKPOINTS.map((bp) => {
    const generation = `old-${bp.key}`;
    const screenshotFile = `capture-${generation}.png`;
    const screenshot = Buffer.from(`screenshot:${bp.key}`);
    writeFileSync(join(tmp, screenshotFile), screenshot);
    const snapshotFile = `old-${bp.key}.snap.json`;
    writeFileSync(join(tmp, snapshotFile), JSON.stringify({
      version: SNAPSHOT_FORMAT_VERSION,
      generation,
      url: source.displayUrl,
      source,
      capturedAt: '2026-01-01T00:00:00.000Z',
      viewport: bp.viewport,
      screenshot: { file: screenshotFile, sha256: sha256(screenshot) },
      layout: { width: bp.viewport.width, height: bp.viewport.height },
      docHeight: bp.viewport.height,
      nodes: [],
    }));
    return { key: bp.key, viewport: bp.viewport, snapshot: snapshotFile };
  });
  const manifest = { version: RESPONSIVE_BUNDLE_VERSION, snapshotVersion: SNAPSHOT_FORMAT_VERSION, generation: 'old', source, captures };
  const manifestFile = `${base}.responsive.snap.json`;
  writeFileSync(manifestFile, JSON.stringify(manifest, null, 1) + '\n');
  return { manifest, manifestFile };
}

await check('snapshot rejects source overwrite before browser launch or output', () => {
  const source = fixture('overwrite.html', 'do not overwrite');
  const before = readFileSync(source, 'utf8');
  const result = spawnSync(process.execPath, [SNAPSHOT, source, '-o', source], { encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /same file/);
  assert.equal(result.stdout, '');
  assert.equal(readFileSync(source, 'utf8'), before);
});

await check('snapshot rejects a symlink alias of the source', () => {
  const source = fixture('alias-source.html', 'keep this too');
  const alias = join(tmp, 'alias.snap.json');
  symlinkSync(source, alias);
  const result = spawnSync(process.execPath, [SNAPSHOT, source, '-o', alias], { encoding: 'utf8' });
  assert.notEqual(result.status, 0);
  assert.match(result.stderr, /same file/);
  assert.equal(readFileSync(source, 'utf8'), 'keep this too');
});

await check('same-basename local files have distinct provenance identities', () => {
  const one = fixture('one/page.html', 'same bytes');
  const two = fixture('two/page.html', 'same bytes');
  const a = describeSource(one).provenance;
  const b = describeSource(two).provenance;
  assert.equal(a.displayUrl, b.displayUrl);
  assert.notEqual(a.identity, b.identity);
});

await check('stale URL identity is rejected instead of reused', () => {
  const base = join(tmp, 'url-cache');
  const oldSource = describeSource('https://example.test/old').provenance;
  const { manifest, manifestFile } = makeBundle(base, oldSource);
  const requested = describeSource('https://example.test/new').provenance;
  const result = validateCaptureBundle(manifestFile, manifest, requested);
  assert.equal(result.valid, false);
  assert.match(result.reason, /source identity/);
});

await check('mismatched viewport and format versions invalidate the bundle', () => {
  const source = describeSource(fixture('format.html')).provenance;
  const base = join(tmp, 'format-cache');
  const { manifest, manifestFile } = makeBundle(base, source);
  const staleViewport = structuredClone(manifest);
  staleViewport.captures[1].viewport.width++;
  assert.match(validateCaptureBundle(manifestFile, staleViewport, source).reason, /viewport is stale/);
  const snapshotFile = join(tmp, manifest.captures[0].snapshot);
  const snapshot = JSON.parse(readFileSync(snapshotFile, 'utf8'));
  writeFileSync(snapshotFile, JSON.stringify({ ...snapshot, version: snapshot.version - 1 }));
  assert.match(validateCaptureBundle(manifestFile, manifest, source).reason, /snapshot format is stale/);
});

await check('interrupted recapture preserves the old complete three-breakpoint bundle', () => {
  const target = fixture('interrupt.html');
  const source = describeSource(target).provenance;
  const base = join(tmp, 'interrupt');
  const { manifest, manifestFile } = makeBundle(base, source);
  const before = readFileSync(manifestFile, 'utf8');
  let calls = 0;
  assert.throws(() => captureBundle(base, target, source, 'recapture requested', ({ file }) => {
    calls++;
    if (calls === 2) throw new Error('simulated capture interruption');
    writeFileSync(file, '{"partial":true}\n');
  }), /simulated capture interruption/);
  assert.equal(readFileSync(manifestFile, 'utf8'), before);
  const after = validateCaptureBundle(manifestFile, JSON.parse(before), source);
  assert.equal(after.valid, true);
  assert.equal(after.snaps.length, 3);
  assert.deepEqual(JSON.parse(before), manifest);
});

console.log(`artifacts: ${tmp}`);
process.exit(failed ? 1 : 0);
