#!/usr/bin/env node
// Tier-0 merge gate: every examples/*.json must render with zero warnings, and rendering twice
// with the same seed must be byte-identical (on this machine's pinned Chromium).
//   node check.mjs [spec.json ...] [--update-previews]   (previews = examples/*.jpg, only on PASS)
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium as loadChromium } from './lib/deps.mjs';
import { renderSpec } from './render.mjs';

const EX = join(dirname(fileURLToPath(import.meta.url)), '..', 'examples');
const args = process.argv.slice(2);
const update = args.includes('--update-previews');
const named = args.filter((a) => !a.startsWith('--'));
const files = named.length ? named : readdirSync(EX).filter((f) => f.endsWith('.json')).map((f) => join(EX, f));

const browser = await (await loadChromium()).launch();
let fail = 0;
try {
  console.log(`chromium ${browser.version()}`);
  for (const f of files) {
    const name = f.split('/').pop();
    try {
      const spec = JSON.parse(readFileSync(f, 'utf8'));
      const a = await renderSpec(spec, { browser });
      const b = await renderSpec(spec, { browser });
      const same = Buffer.compare(a.image, b.image) === 0;
      const ok = same && a.warnings.length === 0;
      if (!ok) fail++;
      if (ok && update) writeFileSync(f.replace(/\.json$/, '.jpg'), (await renderSpec(spec, { browser, format: 'jpeg' })).image);
      console.log(`${ok ? 'PASS' : 'FAIL'} ${name}  ${a.width}x${a.height}  deterministic=${same}  warnings=${JSON.stringify(a.warnings)}`);
    } catch (e) { fail++; console.log(`FAIL ${name}  error=${e.message}`); }
  }
} finally {
  await browser.close();
}
process.exit(fail ? 1 : 0);
