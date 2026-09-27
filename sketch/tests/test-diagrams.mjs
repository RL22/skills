#!/usr/bin/env node
// Regression tests for diagram components (tree, legend, journey, badge), tabs, clip-aware sizing,
// responsive composition and determinism. One shared Chromium for every render.
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { chromium } from 'playwright-core';
import { renderSpec } from '../scripts/render.mjs';
import { composeResponsive } from '../scripts/responsive.mjs';
import { compile } from '../scripts/trace.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const FIX = join(HERE, 'fixtures', 'responsive');
const loadSnap = (k) => JSON.parse(readFileSync(join(FIX, `landing.${k}.snap.json`), 'utf8'));
const snaps = ['desktop', 'tablet', 'phone'].map(loadSnap);

let failed = 0;
const check = async (name, fn) => {
  try { await fn(); console.log(`PASS ${name}`); } catch (e) { failed++; console.log(`FAIL ${name}: ${e.message}`); }
};

const browser = await chromium.launch();
const render = (spec, o = {}) => renderSpec(spec, { browser, ...o });
const timeout = (p, ms = 20000) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error(`timed out after ${ms}ms`)), ms))]);
const rejectsWith = async (spec, re) => {
  let err;
  try { await timeout(render(spec)); } catch (e) { err = e; }
  assert.ok(err, 'expected render to reject');
  assert.doesNotMatch(err.message, /timed out/, 'render hung');
  if (re) assert.match(err.message, re);
};

try {
  // 1. legend cols validation
  for (const cols of [0, -1, '2']) {
    await check(`legend cols ${JSON.stringify(cols)} rejects mentioning legend.cols`, () =>
      rejectsWith({ items: [{ type: 'legend', cols, items: ['one', 'two'] }] }, /legend\.cols/));
  }

  // 2. grid cols 0
  await check('grid cols 0 rejects', () =>
    rejectsWith({ items: [{ type: 'grid', cols: 0, children: [{ type: 'button', label: 'x' }] }] }, /grid\.cols/));

  // 3. tree shapes
  await check('tree with root only renders', async () => {
    const r = await render({ items: [{ type: 'tree', root: { id: 'r', label: 'Home' } }] });
    assert.ok(r.boxes.r);
    assert.deepEqual(r.warnings, []);
  });
  await check('tree root with one section and no pages renders', async () => {
    const r = await render({ items: [{ type: 'tree', root: { id: 'r', label: 'Home', children: [{ id: 's', label: 'Docs' }] } }] });
    assert.ok(r.boxes.r && r.boxes.s);
    assert.ok(r.boxes.s.y > r.boxes.r.y, 'section sits below root');
    assert.deepEqual(r.warnings, []);
  });
  await check('branching tree: a1 right of a, b below a at same x', async () => {
    const root = { id: 'r', label: 'Home', children: [{ id: 's', label: 'Section', children: [
      { id: 'g', label: 'G', children: [{ id: 'a', label: 'A', children: [{ id: 'a1', label: 'A1' }] }, { id: 'b', label: 'B' }] },
    ] }] };
    const r = await render({ items: [{ type: 'tree', root }] });
    const { a, a1, b } = r.boxes;
    assert.ok(a && a1 && b, 'all nodes registered');
    assert.equal(a1.y, a.y, 'a1 on a\'s row');
    assert.ok(a1.x > a.x + a.w - 1, 'a1 right of a');
    assert.ok(b.y > a.y, 'b on a lower row');
    assert.equal(b.x, a.x, 'b at the same x as a');
    assert.deepEqual(r.warnings, []);
  });

  // 4. badge
  await check('badge as a component (no target) renders', async () => {
    const r = await render({ items: [{ type: 'badge', id: 'bd', label: 'new' }] });
    assert.ok(r.boxes.bd && r.boxes.bd.w > 0);
    assert.deepEqual(r.warnings, []);
  });
  await check('badge annotation with unknown target throws', () =>
    rejectsWith({ items: [{ type: 'card', id: 'c', children: [] }, { type: 'badge', n: 1, target: 'nope' }] }, /unknown id "nope"/));

  // 5. journey
  await check('journey with phases: [] throws', () =>
    rejectsWith({ items: [{ type: 'journey', w: 600, phases: [] }] }, /journey/));
  await check('journey with one phase and one point renders clean', async () => {
    const r = await render({ items: [{ type: 'journey', w: 600, phases: [{ title: 'Discover', actions: ['search'], points: [{ score: 1, touch: 'web', note: 'finds it' }] }] }] });
    assert.deepEqual(r.warnings, []);
  });

  // 6. tabs squeezed
  const inBoard = (r) => Object.entries(r.boxes).forEach(([id, b]) => {
    assert.ok(b.x >= 0 && b.y >= 0, `${id} at negative coords`);
    assert.ok(b.x + b.w <= r.width && b.y + b.h <= r.height, `${id} (${b.x},${b.y},${b.w},${b.h}) outside ${r.width}x${r.height}`);
  });
  await check('tabs w 40 with 10 items: no warnings, boxes within board', async () => {
    const items = Array.from({ length: 10 }, (_, i) => `Tab ${i + 1}`);
    const r = await render({ items: [{ type: 'tabs', id: 'tb', w: 40, items, active: 3 }] });
    assert.deepEqual(r.warnings, []);
    inBoard(r);
  });
  await check('page template "tabs" at w 120: no warnings, boxes within board', async () => {
    const r = await render({ items: [{ type: 'page', id: 'pt', template: 'tabs', w: 120 }] });
    assert.deepEqual(r.warnings, []);
    inBoard(r);
  });

  // 7. clip-aware sizing
  await check('clipped overflow warns "clipped" and board ignores clipped geometry', async () => {
    const r = await render({ items: [{ type: 'screen', id: 'sc', clip: true, w: 100, h: 100, children: [{ type: 'image', w: 300, h: 40 }] }] });
    assert.ok(r.warnings.some((w) => /clipped/.test(w)), `warnings: ${JSON.stringify(r.warnings)}`);
    assert.ok(r.width < 250, `board width ${r.width}`);
  });

  // 8. composeResponsive
  await check('compose: ids unique across breakpoints', () => {
    const spec = composeResponsive(snaps, {});
    const ids = spec.items.map((i) => i.id).filter(Boolean);
    assert.equal(new Set(ids).size, ids.length);
  });
  for (const s of [0, -1, NaN]) {
    await check(`compose: scale ${s} throws`, () => assert.throws(() => composeResponsive(snaps, {}, s), /scale/));
  }
  const notesOf = (spec) => spec.items.filter((i) => i.type === 'note');
  await check('compose: note without breakpoint lands on every frame (3)', () => {
    const spec = composeResponsive(snaps, { notes: [{ at: 'text=Get started', text: 'CTA' }] });
    const n = notesOf(spec);
    assert.equal(n.length, 3);
    assert.deepEqual(n.map((x) => x.near).sort(), ['desktop-page', 'phone-page', 'tablet-page']);
  });
  await check('compose: note with breakpoint phone lands once, on phone', () => {
    const spec = composeResponsive(snaps, { notes: [{ at: 'text=Get started', text: 'CTA', breakpoint: 'phone' }] });
    const n = notesOf(spec);
    assert.equal(n.length, 1);
    assert.equal(n[0].near, 'phone-page');
  });
  await check('compose: left-side note keeps every item x >= 0 (spec and render)', async () => {
    const spec = composeResponsive(snaps, { notes: [{ at: 'text=Get started', text: 'primary action', side: 'left' }] });
    spec.items.filter((i) => i.x != null).forEach((i) => assert.ok(i.x >= 0, `${i.id} x=${i.x}`));
    const r = await render(spec);
    Object.entries(r.boxes).forEach(([id, b]) => assert.ok(b.x >= 0, `${id} rendered at x=${b.x}`));
    assert.ok(!r.warnings.some((w) => /negative/.test(w)), JSON.stringify(r.warnings));
  });
  await check('compose: breakpoints.phone.hide removes node only from phone', () => {
    const matcher = 'text=See examples';
    const has = (spec, pre) => spec.items.some((i) => i.id.startsWith(pre) && i.label === 'See examples');
    const base = composeResponsive(snaps, {});
    ['desktop-', 'tablet-', 'phone-'].forEach((p) => assert.ok(has(base, p), `baseline missing on ${p}`));
    const spec = composeResponsive(snaps, { breakpoints: { phone: { hide: [matcher] } } });
    assert.ok(has(spec, 'desktop-') && has(spec, 'tablet-'), 'hidden from a non-phone frame');
    assert.ok(!has(spec, 'phone-'), 'still present on phone');
  });

  // 9. compile purity
  await check('compile is pure: same output twice, input not mutated', () => {
    const snap = loadSnap('desktop');
    const before = structuredClone(snap);
    const ov = { notes: [{ at: 'text=Get started', text: 'x' }], hide: ['text=See examples'] };
    const a = JSON.stringify(compile(snap, ov)), b = JSON.stringify(compile(snap, ov));
    assert.equal(a, b);
    assert.deepEqual(snap, before);
  });

  // 10. determinism
  await check('render is deterministic (tree + legend + journey + page): identical PNG bytes', async () => {
    const spec = {
      seed: 21,
      items: [
        { type: 'tree', root: { id: 'r', label: 'Home', badge: 1, children: [{ id: 's', label: 'Blog', template: 'blog', children: [{ id: 'p', label: 'Post' }] }] } },
        { type: 'legend', cols: 2, items: ['Home page', 'Blog index'] },
        { type: 'journey', w: 700, phases: [{ title: 'Find', points: [{ score: 1, note: 'ok' }] }, { title: 'Buy', points: [{ score: -1, touch: 'email' }] }] },
        { type: 'page', id: 'pg', template: 'tabs', w: 150 },
      ],
    };
    const [a, b] = [await render(spec), await render(spec)];
    assert.ok(a.image.length > 1000);
    assert.ok(Buffer.compare(a.image, b.image) === 0, 'PNG bytes differ');
  });
} finally {
  await browser.close();
}
process.exit(failed ? 1 : 0);
