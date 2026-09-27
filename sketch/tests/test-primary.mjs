#!/usr/bin/env node
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { compile } from '../scripts/trace.mjs';
import { composeResponsive } from '../scripts/responsive.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const fixture = (breakpoint) => JSON.parse(readFileSync(join(HERE, 'fixtures', 'responsive', `landing.${breakpoint}.snap.json`), 'utf8'));
const snaps = ['desktop', 'tablet', 'phone'].map(fixture);
const primaries = (spec) => spec.items.filter((item) => item.type === 'button' && item.variant === 'primary');
const missingSelector = 'text=This button does not exist';
const missingError = /override primary: no button matches selector "text=This button does not exist"; update the selector or use primary: false/;

let failed = 0;
const check = (name, fn) => {
  try {
    fn();
    console.log(`PASS ${name}`);
  } catch (error) {
    failed++;
    console.log(`FAIL ${name}: ${error.message}`);
  }
};

check('compile: a matching selector yields exactly one primary', () => {
  const spec = compile(snaps[0], { primary: 'text=Join the waitlist' });
  assert.equal(primaries(spec).length, 1);
  assert.equal(primaries(spec)[0].label, 'Join the waitlist');
  assert.equal(JSON.stringify(spec), JSON.stringify(compile(snaps[0], { primary: 'text=Join the waitlist' })));
});

check('compile: primary false yields no primary', () => {
  assert.equal(primaries(compile(snaps[0], { primary: false })).length, 0);
});

check('compile: an unmatched explicit selector throws an actionable error', () => {
  assert.throws(() => compile(snaps[0], { primary: missingSelector }), missingError);
});

check('composeResponsive: a matching selector yields one primary per fixture snapshot', () => {
  const spec = composeResponsive(snaps, { primary: 'text=Get started' });
  const selected = primaries(spec);
  assert.equal(selected.length, snaps.length);
  assert.deepEqual(selected.map((item) => item.label), snaps.map(() => 'Get started'));
  assert.equal(JSON.stringify(spec), JSON.stringify(composeResponsive(snaps, { primary: 'text=Get started' })));
});

check('composeResponsive: primary false yields no primary', () => {
  assert.equal(primaries(composeResponsive(snaps, { primary: false })).length, 0);
});

check('composeResponsive: an unmatched explicit selector propagates the actionable error', () => {
  assert.throws(() => composeResponsive(snaps, { primary: missingSelector }), missingError);
});

process.exit(failed ? 1 : 0);
