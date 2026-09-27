#!/usr/bin/env node
// Render a case-study-imgs board spec (JSON) to PNG, JPEG, or SVG.
//   node render.mjs board.json [-o out.png|out.jpg|out.svg] [--scale 2] [--seed N] [--paper grid|plain|white] [--strict] [--html]
// Exit codes: 0 ok, 1 usage/spec/render error, 2 rendered-with-warnings under --strict.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium as loadChromium } from './lib/deps.mjs';

const HERE = dirname(fileURLToPath(import.meta.url));
const LIB = ['vendor/rough.js', 'lib/tokens.js', 'lib/core.js', 'lib/components.js', 'lib/pages.js', 'lib/diagrams.js', 'lib/board.js'];
const FONTS = { 'Architects Daughter': 'ArchitectsDaughter.woff2', Caveat: 'Caveat.woff2', 'Nanum Pen Script': 'NanumPenScript.woff2' };
const FORMATS = { '.png': 'png', '.jpg': 'jpeg', '.jpeg': 'jpeg', '.svg': 'svg' };
const USAGE = 'usage: render.mjs <spec.json> [-o out.png|out.jpg|out.svg] [--scale 2] [--seed N] [--paper grid|plain|white] [--strict] [--html]';

function die(msg) { console.error(msg); process.exit(1); }

function parseArgs(argv) {
  const a = { scale: 2 };
  const rest = [];
  const val = (i, k) => { const v = argv[i]; if (v == null || v.startsWith('--')) die(`${k} needs a value\n${USAGE}`); return v; };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '-o' || k === '--out') a.out = val(++i, k);
    else if (k === '--scale') a.scale = Number(val(++i, k));
    else if (k === '--seed') a.seed = Number(val(++i, k));
    else if (k === '--paper') a.paper = val(++i, k);
    else if (k === '--html') a.html = true;
    else if (k === '--strict') a.strict = true;
    else if (k === '-h' || k === '--help') a.help = true;
    else if (k.startsWith('-')) die(`unknown option ${k}\n${USAGE}`);
    else rest.push(k);
  }
  if (rest.length > 1) die(`expected one spec file, got ${rest.length}\n${USAGE}`);
  if (!(a.scale > 0)) die('--scale must be a positive number');
  if (a.seed != null && !Number.isInteger(a.seed)) die('--seed must be an integer');
  if (a.paper && !['grid', 'plain', 'white'].includes(a.paper)) die('--paper must be grid, plain, or white');
  a.spec = rest[0];
  return a;
}

function fontCss() {
  return Object.entries(FONTS).map(([fam, file]) => {
    const b64 = readFileSync(join(HERE, 'vendor/fonts', file)).toString('base64');
    return `@font-face{font-family:"${fam}";src:url(data:font/woff2;base64,${b64}) format("woff2");}`;
  }).join('\n');
}

export function buildHtml() {
  const js = LIB.map((f) => readFileSync(join(HERE, f), 'utf8')).join('\n;\n');
  return `<!doctype html><html><head><meta charset="utf-8"><style>${fontCss()}
html,body{margin:0;padding:0;background:#fff}svg{display:block}</style></head>
<body><svg id="board" xmlns="http://www.w3.org/2000/svg"></svg><script>${js}</script></body></html>`;
}

export async function renderSpec(spec, { scale = 2, browser, format = 'png', quality = 88 } = {}) {
  const own = !browser;
  browser = browser || (await (await loadChromium()).launch());
  let page;
  try {
    page = await browser.newPage({ deviceScaleFactor: scale, viewport: { width: 800, height: 600 } });
    await page.setContent(buildHtml());
    await page.evaluate(async (fams) => { await Promise.all(fams.map((f) => document.fonts.load(`16px "${f}"`))); await document.fonts.ready; }, Object.keys(FONTS));
    const res = await page.evaluate((s) => {
      try { return CSI.render(s, document.getElementById('board')); } catch (e) { return { error: e.message }; }
    }, spec);
    if (res.error) throw new Error(res.error);
    let image = null, svg = null;
    if (format === 'svg') {
      // self-contained SVG: fonts travel with the file
      svg = await page.evaluate((css) => {
        const el = document.getElementById('board').cloneNode(true);
        const st = document.createElementNS('http://www.w3.org/2000/svg', 'style');
        st.textContent = css;
        el.insertBefore(st, el.firstChild);
        return el.outerHTML;
      }, fontCss());
    } else {
      await page.setViewportSize({ width: res.width, height: res.height });
      image = await page.locator('#board').screenshot(format === 'jpeg' ? { type: 'jpeg', quality, animations: 'disabled' } : { type: 'png', animations: 'disabled' });
    }
    return { ...res, image, svg, browserVersion: browser.version() };
  } finally {
    if (page) await page.close().catch(() => {});
    if (own) await browser.close();
  }
}

async function main() {
  const a = parseArgs(process.argv.slice(2));
  if (a.help || !a.spec) { console.log(USAGE); process.exit(a.help ? 0 : 1); }
  const specPath = resolve(a.spec);
  let spec;
  try { spec = JSON.parse(readFileSync(specPath, 'utf8')); } catch (e) { die(`spec error: ${e.message}`); }
  if (a.seed != null) spec.seed = a.seed;
  if (a.paper) spec.paper = a.paper;
  if (a.html) writeFileSync(specPath.replace(/(\.json)?$/i, '.debug.html'), buildHtml());
  const out = resolve(a.out || specPath.replace(/\.json$/i, '') + '.png');
  if (out === specPath) die('refusing to overwrite the input spec — pass -o');
  const format = FORMATS[extname(out).toLowerCase()];
  if (!format) die(`unsupported output extension "${extname(out)}" — use .png, .jpg, or .svg`);
  try {
    const r = await renderSpec(spec, { scale: a.scale, format });
    writeFileSync(out, format === 'svg' ? r.svg : r.image);
    console.log(JSON.stringify({ out, width: r.width, height: r.height, scale: a.scale, browser: r.browserVersion, warnings: r.warnings }));
    if (a.strict && r.warnings.length) process.exit(2);
  } catch (e) {
    die(`render error: ${e.message}`);
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
