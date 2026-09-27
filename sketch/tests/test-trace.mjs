#!/usr/bin/env node
// Trace pipeline test on a local fixture (no network):
//   snapshot twice → identical nodes · compile twice → identical spec · rules hold · spec renders clean.
import { execFileSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { compile } from '../scripts/trace.mjs';
import { renderSpec } from '../scripts/render.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const SNAP = join(HERE, '..', 'scripts', 'snapshot.mjs');
const fixture = join(HERE, 'fixtures', 'landing.html');
const tmp = mkdtempSync(join(tmpdir(), 'sketch-trace-'));
const snap = (name) => { const out = join(tmp, name); execFileSync('node', [SNAP, fixture, '-o', out], { stdio: 'pipe' }); return JSON.parse(readFileSync(out, 'utf8')); };

let failed = 0;
const check = (name, fn) => { try { fn(); console.log(`PASS ${name}`); } catch (e) { failed++; console.log(`FAIL ${name}: ${e.message}`); } };

const a = snap('a.snap.json'), b = snap('b.snap.json');
const strip = (s) => JSON.stringify({ ...s, capturedAt: null });
check('snapshot is repeatable', () => assert.equal(strip(a), strip(b)));

const spec = compile(a);
check('compile is a pure function', () => assert.equal(JSON.stringify(spec), JSON.stringify(compile({ ...JSON.parse(JSON.stringify(b)), capturedAt: a.capturedAt }))));

const items = spec.items;
const texts = items.filter((i) => i.type === 'text').map((i) => i.text);
check('exactly one primary, and it is "Get started"', () => {
  const p = items.filter((i) => i.type === 'button' && i.variant === 'primary');
  assert.equal(p.length, 1); assert.equal(p[0].label, 'Get started');
});
check('outline button keeps its label', () => assert.ok(items.some((i) => i.type === 'button' && i.variant === 'outline' && i.label === 'See examples')));
check('3-word button label stays real', () => assert.ok(items.some((i) => i.type === 'button' && i.label === 'Join the waitlist')));
check('h1 keeps real words', () => assert.ok(texts.join(' ').includes('Ship landing pages')));
check('nav links keep real words', () => ['Product', 'Pricing', 'Customers', 'Log in'].forEach((t) => assert.ok(texts.includes(t), t)));
check('body copy is squiggles', () => assert.ok(!texts.some((t) => t.includes('Pick a starting point'))));
check('fixed cookie bar is dropped', () => assert.ok(!items.some((i) => i.label === 'Accept all') && !texts.some((t) => /cookies/.test(t))));
check('header svg becomes the logo', () => assert.equal(items.filter((i) => i.type === 'logo').length, 1));
check('hero background image becomes an X-box', () => assert.ok(items.some((i) => i.type === 'image')));
check('three cards', () => assert.equal(items.filter((i) => i.type === 'card').length, 3));
check('email input keeps its placeholder', () => assert.ok(items.some((i) => i.type === 'input' && i.placeholder === 'you@company.com') || items.some((i) => i.type === 'input')));

const ov = { hide: ['text=See examples'], primary: 'text=Join the waitlist', label: { 'text=Get started': 'Start free' }, real: ['text=Pages load in under a second on any connection.'], notes: [{ at: 'text=Get started', text: 'one CTA above the fold', side: 'right' }] };
const spec2 = compile(a, ov);
check('overrides: hide / primary / label / real / note', () => {
  const it = spec2.items;
  assert.ok(!it.some((i) => i.label === 'See examples'));
  assert.equal(it.find((i) => i.variant === 'primary')?.label, 'Join the waitlist');
  assert.equal(it.filter((i) => i.variant === 'primary').length, 1);
  assert.ok(it.some((i) => i.label === 'Start free'));
  assert.ok(it.some((i) => i.type === 'text' && i.text.startsWith('Pages load')));
  assert.ok(it.some((i) => i.type === 'note' && i.to));
});

const r = await renderSpec(spec2);
check('traced spec renders clean', () => assert.deepEqual(r.warnings, []));
writeFileSync(join(tmp, 'trace.png'), r.image);
console.log(`artifacts: ${tmp}`);
process.exit(failed ? 1 : 0);
