#!/usr/bin/env node
// Every page template renders warning-free at thumbnail (130px) and large (300px) widths.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderSpec } from '../scripts/render.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(HERE, '..', 'scripts', 'lib', 'pages.js'), 'utf8');
const names = [...src.matchAll(/^\s*P(?:\.([a-z0-9]+)|\['([a-z0-9-]+)'\])\s*=/gm)].map((m) => m[1] || m[2]);
let fail = 0;
for (const w of [130, 300]) {
  const spec = { width: w * 8 + 400, gap: 30, seed: 3, items: names.map((t) => ({ type: 'page', template: t, w })) };
  try {
    const r = await renderSpec(spec, { format: 'jpeg' });
    if (process.argv.includes('--out')) writeFileSync(join(HERE, `pages-${w}.jpg`), r.image);
    if (r.warnings.length) { fail++; console.log(`FAIL pages@${w}: ${JSON.stringify(r.warnings)}`); }
    else console.log(`PASS ${names.length} page templates @${w}px`);
  } catch (e) { fail++; console.log(`FAIL pages@${w}: ${e.message}`); }
}
process.exit(fail ? 1 : 0);
