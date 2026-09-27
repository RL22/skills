#!/usr/bin/env node
// One page at desktop, tablet and phone widths, side by side, at a single shared scale.
// A responsive bundle manifest is the atomic commit marker for all three captures. Snapshot and
// screenshot artifacts are generation-specific, so an interrupted recapture cannot mix generations.
import { randomUUID, createHash } from 'node:crypto';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compile, NOTE_GUTTER } from './trace.mjs';
import { describeSource, SNAPSHOT_FORMAT_VERSION } from './snapshot.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const USAGE = 'usage: responsive.mjs <url|file.html> -o <dir>/<name> [--overrides o.json] [--recapture] [--scale 0.42]';
export const RESPONSIVE_BUNDLE_VERSION = 1;
export const BREAKPOINTS = [
  { key: 'desktop', label: 'Desktop', viewport: { width: 1280, height: 800, mobile: false }, args: ['--width', '1280', '--height', '800'] },
  { key: 'tablet', label: 'Tablet', viewport: { width: 768, height: 1024, mobile: false }, args: ['--width', '768', '--height', '1024'] },
  { key: 'phone', label: 'Phone', viewport: { width: 390, height: 844, mobile: true }, args: ['--mobile'] },
];

const sha256 = (value) => createHash('sha256').update(value).digest('hex');
const equalViewport = (a, b) => a && a.width === b.width && a.height === b.height && !!a.mobile === !!b.mobile;

function atomicWriteJson(file, value) {
  const tmp = join(dirname(resolve(file)), `.${basename(file)}.${process.pid}.tmp`);
  writeFileSync(tmp, JSON.stringify(value, null, 1) + '\n');
  renameSync(tmp, file);
}

function overridesFor(ov, key) {
  const { breakpoints = {}, notes = [], ...base } = ov;
  const own = breakpoints[key] || {};
  const merge = (a, b) => (Array.isArray(a) || Array.isArray(b) ? [...(a || []), ...(b || [])] : a && b && typeof a === 'object' ? { ...a, ...b } : b ?? a);
  const out = { ...base };
  for (const [k, v] of Object.entries(own)) out[k] = merge(base[k], v);
  out.notes = [...notes.filter((n) => !n.breakpoint || n.breakpoint === key), ...(own.notes || [])];
  return out;
}

export function composeResponsive(snaps, ov = {}, scale = 0.42) {
  if (!(Number.isFinite(scale) && scale > 0)) throw new Error(`scale must be a positive number (got ${scale})`);
  const M = 44, gap = 60, top = M + (ov.title ? 60 : 0);
  const items = [];
  let x = M;
  snaps.forEach((snap, i) => {
    const bp = BREAKPOINTS[i];
    const o = overridesFor(ov, bp.key);
    const left = o.notes.some((n) => n.side === 'left') ? NOTE_GUTTER : 0;
    const right = o.notes.some((n) => (n.side ?? 'right') === 'right') ? NOTE_GUTTER : 0;
    x += left;
    items.push({ type: 'heading', id: `${bp.key}-label`, text: `${bp.label} · ${snap.viewport.width}px`, size: 18, x, y: top });
    const spec = compile(snap, { ...o, title: undefined }, { scale, origin: { x, y: top + 40 }, prefix: `${bp.key}-` });
    items.push(...spec.items);
    x += Math.round(snap.viewport.width * scale) + right + gap;
  });
  return {
    paper: ov.paper ?? 'grid',
    seed: ov.seed ?? 7,
    ...(ov.title ? { title: ov.title } : {}),
    source: { url: snaps[0].url, capturedAt: snaps.map((s) => s.capturedAt), traced: 'responsive.mjs v2' },
    items,
  };
}

export function validateCaptureBundle(manifestFile, manifest, requestedSource) {
  try {
    if (manifest.version !== RESPONSIVE_BUNDLE_VERSION) throw new Error(`bundle format ${manifest.version} is not ${RESPONSIVE_BUNDLE_VERSION}`);
    if (manifest.snapshotVersion !== SNAPSHOT_FORMAT_VERSION) throw new Error(`snapshot format ${manifest.snapshotVersion} is not ${SNAPSHOT_FORMAT_VERSION}`);
    if (manifest.source?.identity !== requestedSource.identity) throw new Error('source identity does not match the requested source');
    if (!Array.isArray(manifest.captures) || manifest.captures.length !== BREAKPOINTS.length) throw new Error('bundle does not contain exactly three captures');
    const dir = dirname(resolve(manifestFile));
    const snaps = BREAKPOINTS.map((bp) => {
      const entry = manifest.captures.find((capture) => capture.key === bp.key);
      if (!entry || !equalViewport(entry.viewport, bp.viewport)) throw new Error(`${bp.key} bundle viewport is stale`);
      const snapshotFile = join(dir, entry.snapshot);
      const snap = JSON.parse(readFileSync(snapshotFile, 'utf8'));
      if (snap.version !== SNAPSHOT_FORMAT_VERSION) throw new Error(`${bp.key} snapshot format is stale`);
      if (!snap.generation || snap.screenshot?.file !== `capture-${snap.generation}.png`) throw new Error(`${bp.key} snapshot generation record is invalid`);
      if (snap.source?.identity !== requestedSource.identity) throw new Error(`${bp.key} snapshot source does not match`);
      if (!equalViewport(snap.viewport, bp.viewport)) throw new Error(`${bp.key} snapshot viewport is stale`);
      if (!snap.screenshot?.file || !snap.screenshot.sha256) throw new Error(`${bp.key} snapshot has no screenshot integrity record`);
      const screenshot = readFileSync(join(dirname(snapshotFile), snap.screenshot.file));
      if (sha256(screenshot) !== snap.screenshot.sha256) throw new Error(`${bp.key} screenshot integrity check failed`);
      return snap;
    });
    return { valid: true, snaps };
  } catch (error) {
    return { valid: false, reason: error.message };
  }
}

function runSnapshot({ file, target, breakpoint }) {
  execFileSync(process.execPath, [join(HERE, 'snapshot.mjs'), target, '-o', file, ...breakpoint.args], { stdio: ['ignore', 'ignore', 'pipe'] });
}

export function captureBundle(base, target, source, staleReason, capture = runSnapshot) {
  const generation = randomUUID();
  const captures = [];
  try {
    for (const bp of BREAKPOINTS) {
      const file = `${base}.${generation}.${bp.key}.snap.json`;
      capture({ file, target, breakpoint: bp });
      captures.push({ key: bp.key, viewport: bp.viewport, snapshot: basename(file) });
    }
  } catch (error) {
    const detail = error.stderr?.toString().trim() || error.message;
    throw new Error(`recapture failed${staleReason ? ` after cache rejection (${staleReason})` : ''}: ${detail}`);
  }
  const manifest = { version: RESPONSIVE_BUNDLE_VERSION, snapshotVersion: SNAPSHOT_FORMAT_VERSION, generation, source, captures };
  const manifestFile = `${base}.responsive.snap.json`;
  const checked = validateCaptureBundle(manifestFile, manifest, source);
  if (!checked.valid) throw new Error(`new capture bundle is invalid: ${checked.reason}`);
  atomicWriteJson(manifestFile, manifest);
  return { snaps: checked.snaps, state: staleReason ? `recaptured: ${staleReason}` : 'captured' };
}

function main() {
  const argv = process.argv.slice(2);
  const a = { scale: 0.42 };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '-o') a.out = argv[++i];
    else if (k === '--overrides') a.overrides = argv[++i];
    else if (k === '--recapture') a.recapture = true;
    else if (k === '--scale') { a.scale = Number(argv[++i]); if (!(Number.isFinite(a.scale) && a.scale > 0)) { console.error('--scale must be a positive number'); process.exit(1); } }
    else if (k === '-h' || k === '--help') { console.log(USAGE); process.exit(0); }
    else if (k.startsWith('-')) { console.error(`unknown option ${k}\n${USAGE}`); process.exit(1); }
    else rest.push(k);
  }
  if (rest.length !== 1 || !a.out) { console.error(USAGE); process.exit(1); }
  const base = resolve(a.out.replace(/\.json$/, ''));
  const manifestFile = `${base}.responsive.snap.json`;
  try {
    const requested = describeSource(rest[0]).provenance;
    let cached;
    let staleReason;
    if (existsSync(manifestFile)) {
      const manifest = JSON.parse(readFileSync(manifestFile, 'utf8'));
      cached = validateCaptureBundle(manifestFile, manifest, requested);
      if (!cached.valid) staleReason = cached.reason;
    } else staleReason = 'no responsive capture bundle';
    const bundle = a.recapture || !cached?.valid
      ? captureBundle(base, rest[0], requested, a.recapture ? 'recapture requested' : staleReason)
      : { snaps: cached.snaps, state: 'cache hit' };
    const ov = a.overrides ? JSON.parse(readFileSync(a.overrides, 'utf8')) : {};
    const spec = composeResponsive(bundle.snaps, ov, a.scale);
    atomicWriteJson(`${base}.json`, spec);
    console.log(JSON.stringify({ out: `${base}.json`, bundle: manifestFile, cache: bundle.state, items: spec.items.length }));
  } catch (e) {
    console.error(`responsive error: ${e.message}`);
    process.exit(1);
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
