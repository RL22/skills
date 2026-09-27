#!/usr/bin/env node
// Freeze a page into a snapshot: every visible element's role, box, and text, captured under fixed
// conditions (viewport, reduced motion, fixed clock/locale/timezone, trackers blocked, lazy content
// loaded). trace.mjs compiles the snapshot; re-running trace never touches the network.
//   node snapshot.mjs <url|file.html> -o page.snap.json [--mobile] [--width 1280] [--height 800]
// Writes a generation-addressed viewport screenshot beside the snapshot and references it from the JSON.
import { createHash } from 'node:crypto';
import { existsSync, readFileSync, realpathSync, renameSync, statSync, unlinkSync, writeFileSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { chromium as loadChromium } from './lib/deps.mjs';

const BLOCK = /google-analytics|googletagmanager|doubleclick|googlesyndication|facebook\.net|connect\.facebook|hotjar|segment\.(io|com)|intercom|hs-scripts|hs-analytics|clarity\.ms|fullstory|mixpanel|amplitude|sentry|newrelic|nr-data|tiktok|linkedin\.com\/px|snap\.licdn|bat\.bing|crisp\.chat|drift\.com|zdassets/;
const USAGE = 'usage: snapshot.mjs <url|file.html> -o page.snap.json [--mobile] [--width 1280] [--height 800]';
export const SNAPSHOT_FORMAT_VERSION = 2;

const sha256 = (value) => createHash('sha256').update(value).digest('hex');

export function describeSource(target) {
  let local;
  if (target.startsWith('file:')) local = fileURLToPath(target);
  else if (existsSync(target)) local = target;
  if (local) {
    const canonicalPath = realpathSync(resolve(local));
    const contentSha256 = sha256(readFileSync(canonicalPath));
    return {
      url: pathToFileURL(canonicalPath).href,
      provenance: {
        kind: 'file',
        identity: sha256(`file\0${canonicalPath}\0${contentSha256}`),
        displayUrl: `file:${basename(canonicalPath)}`,
        contentSha256,
      },
      localPath: canonicalPath,
    };
  }
  const url = /^https?:\/\//.test(target) ? new URL(target).href : `https://${target}`;
  return { url, provenance: { kind: 'url', identity: sha256(`url\0${url}`), displayUrl: url } };
}

function sameUnderlyingFile(sourcePath, outputPath) {
  const source = realpathSync(sourcePath);
  const output = resolve(outputPath);
  if (source === output) return true;
  if (!existsSync(output)) return false;
  const a = statSync(source), b = statSync(output);
  return a.dev === b.dev && a.ino === b.ino;
}

function atomicWriteJson(file, value) {
  const tmp = join(dirname(resolve(file)), `.${basename(file)}.${process.pid}.tmp`);
  writeFileSync(tmp, JSON.stringify(value, null, 1) + '\n');
  renameSync(tmp, file);
}

function parseArgs(argv) {
  const a = { width: 1280, height: 800 };
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '-o' || k === '--out') a.out = argv[++i];
    else if (k === '--width') a.width = Number(argv[++i]);
    else if (k === '--height') a.height = Number(argv[++i]);
    else if (k === '--mobile') { a.mobile = true; a.width = 390; a.height = 844; }
    else if (k === '-h' || k === '--help') { console.log(USAGE); process.exit(0); }
    else if (k.startsWith('-')) { console.error(`unknown option ${k}\n${USAGE}`); process.exit(1); }
    else rest.push(k);
  }
  if (rest.length !== 1 || !a.out) { console.error(USAGE); process.exit(1); }
  a.target = rest[0];
  return a;
}

// Runs inside the page. Pure DOM reads; returns plain data.
function extract() {
  const W = innerWidth;
  const round = (v) => Math.round(v);
  const transparent = (c) => !c || c === 'transparent' || /rgba\([^)]*,\s*0\)$/.test(c);
  const pageBg = [document.body, document.documentElement].map((e) => getComputedStyle(e).backgroundColor).find((c) => !transparent(c)) || 'rgb(255, 255, 255)';
  const BLOCKY = new Set(['block', 'flex', 'grid', 'table', 'list-item', 'table-row', 'table-cell', 'flow-root']);
  const SKIP = new Set(['script', 'style', 'noscript', 'template', 'head', 'meta', 'link', 'title']);
  const TEXT_INPUT = new Set(['text', 'email', 'search', 'password', 'number', 'tel', 'url', 'date', 'datetime-local', 'month', 'week', 'time', '']);
  const out = [];

  const words = (s) => (s.trim() ? s.trim().split(/\s+/).length : 0);
  const clean = (s) => (s || '').replace(/\s+/g, ' ').trim().slice(0, 200);
  const box = (r) => ({ x: round(r.left + scrollX), y: round(r.top + scrollY), w: round(r.width), h: round(r.height) });
  const visibleBorder = (st) => ['Top', 'Right', 'Bottom', 'Left'].filter((s) => parseFloat(st[`border${s}Width`]) >= 1 && st[`border${s}Style`] !== 'none' && !transparent(st[`border${s}Color`])).length;
  const hasBlockChild = (el) => [...el.children].some((c) => BLOCKY.has(getComputedStyle(c).display));
  const directText = (el) => [...el.childNodes].some((n) => n.nodeType === 3 && /\p{L}|\p{N}/u.test(n.textContent));
  function lineRects(range) {
    const lines = [];
    for (const r of range.getClientRects()) {
      if (r.width < 2 || r.height < 2) continue;
      const b = box(r);
      const L = lines.find((l) => Math.abs(l.y - b.y) <= 3);
      if (L) { const x2 = Math.max(L.x + L.w, b.x + b.w); L.x = Math.min(L.x, b.x); L.w = x2 - L.x; L.h = Math.max(L.h, b.h); }
      else lines.push(b);
    }
    return lines.sort((a, b) => a.y - b.y || a.x - b.x);
  }
  // lines with the exact words rendered on each (measured per word, so wraps match the page)
  function wordLines(el) {
    const lines = [];
    const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = tw.nextNode(); n; n = tw.nextNode()) {
      const re = /\S+/g;
      let m;
      while ((m = re.exec(n.textContent))) {
        const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
        const rc = r.getClientRects()[0];
        if (!rc || rc.width < 1) continue;
        const b = box(rc);
        let L = lines.find((l) => Math.abs(l.y + l.h / 2 - (b.y + b.h / 2)) <= Math.max(l.h, b.h) / 2);
        if (!L) { L = { ...b, words: [] }; lines.push(L); }
        const x2 = Math.max(L.x + L.w, b.x + b.w); L.x = Math.min(L.x, b.x); L.w = x2 - L.x;
        const y2 = Math.max(L.y + L.h, b.y + b.h); L.y = Math.min(L.y, b.y); L.h = y2 - L.y;
        L.words.push(m[0]);
      }
    }
    const tt = getComputedStyle(el).textTransform;
    const cased = (w) => (tt === 'uppercase' ? w.toUpperCase() : tt === 'lowercase' ? w.toLowerCase() : tt === 'capitalize' ? w.charAt(0).toUpperCase() + w.slice(1) : w);
    return lines.sort((a, b) => a.y - b.y || a.x - b.x).map(({ words, ...l }) => ({ ...l, text: words.map(cased).join(' ') }));
  }
  function seg(el) {
    let n = 1;
    for (let s = el.previousElementSibling; s; s = s.previousElementSibling) if (s.tagName === el.tagName) n++;
    return `${el.tagName.toLowerCase()}:${n}`;
  }

  function walk(el, path, ctx, parentBg) {
    const t = el.tagName.toLowerCase();
    if (SKIP.has(t)) return;
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden' || parseFloat(st.opacity) === 0) return;
    const r = el.getBoundingClientRect();
    const b = box(r);
    const here = `${path}>${seg(el)}`;
    const c = {
      inNav: ctx.inNav || t === 'nav' || el.getAttribute('role') === 'navigation',
      inHeader: ctx.inHeader || t === 'header' || el.getAttribute('role') === 'banner',
      inFooter: ctx.inFooter || t === 'footer' || el.getAttribute('role') === 'contentinfo',
      inA: ctx.inA || t === 'a',
      pos: st.position === 'fixed' || st.position === 'sticky' ? st.position : ctx.pos,
      ids: el.id ? [...ctx.ids, el.id] : ctx.ids,
    };
    const bg = transparent(st.backgroundColor) ? parentBg : st.backgroundColor;
    const onScreen = b.w >= 2 && b.h >= 2 && b.x + b.w > 0 && b.x < W;
    const emit = (kind, extra = {}) => onScreen && out.push({
      kind, ...b, path: here, ids: c.ids, cls: [...el.classList].slice(0, 4),
      pos: c.pos || null, inNav: c.inNav, inHeader: c.inHeader, inFooter: c.inFooter, ...extra,
    });
    const kids = () => {
      const list = el.shadowRoot ? [...el.shadowRoot.children] : t === 'slot' ? el.assignedElements() : [...el.children];
      for (const k of list) walk(k, here, c, bg);
    };

    const role = el.getAttribute('role');
    if (role === 'button' && ['svg', 'img'].includes(t))
      return emit('button', { text: '', aria: clean(el.getAttribute('aria-label') || el.getAttribute('title')), filled: false, boxed: false, bg, border: 0 });
    if (['img', 'picture', 'video', 'canvas', 'iframe', 'object', 'embed', 'svg'].includes(t)) {
      if ((b.w >= 40 && b.h >= 40) || (b.w >= 40 && b.h >= 12 && b.w >= 2 * b.h)) emit(t === 'video' ? 'video' : t === 'iframe' || t === 'object' || t === 'embed' ? 'embed' : 'image', { alt: clean(el.getAttribute('alt') || el.getAttribute('aria-label')), wordmark: b.h < 40 });
      else emit('icon');
      return;
    }
    if (t === 'input') {
      const type = (el.getAttribute('type') || '').toLowerCase();
      if (type === 'hidden') return;
      if (type === 'checkbox' || type === 'radio') return emit(type, { checked: el.checked });
      if (['submit', 'button', 'reset'].includes(type)) return emit('button', { text: clean(el.value), aria: clean(el.getAttribute('aria-label')), filled: !transparent(st.backgroundColor), boxed: true, bg, border: visibleBorder(st) });
      if (TEXT_INPUT.has(type)) return emit('input', { text: clean(el.getAttribute('placeholder') || el.getAttribute('aria-label')) });
      return emit('input', {});
    }
    if (t === 'textarea') return emit('textarea', { text: clean(el.getAttribute('placeholder')) });
    if (t === 'select') return emit('dropdown', { text: clean(el.selectedOptions[0]?.textContent) });
    if (t === 'hr') return emit('divider');
    if (/^h[1-6]$/.test(t) || role === 'heading') {
      return emit('heading', { level: /^h[1-6]$/.test(t) ? Number(t[1]) : Number(el.getAttribute('aria-level') || 2), text: clean(el.innerText), fontSize: parseFloat(st.fontSize), lines: wordLines(el) });
    }
    const txt = clean(el.innerText);
    const filled = !transparent(st.backgroundColor) && st.backgroundColor !== parentBg;
    const border = visibleBorder(st);
    const pseudoBox = ['::before', '::after'].some((p) => { const ps = getComputedStyle(el, p); return ps.content !== 'none' && (!transparent(ps.backgroundColor) || visibleBorder(ps) >= 3); });
    const boxed = filled || border >= 3 || st.boxShadow !== 'none' || pseudoBox;
    const buttonish = t === 'button' || role === 'button' ||
      (t === 'a' && boxed && b.h >= 20 && b.h <= 90 && words(txt) <= 6);
    if (buttonish) return emit('button', { text: txt, aria: clean(el.getAttribute('aria-label') || el.getAttribute('title')), filled, boxed, bg: st.backgroundColor, border });

    if (st.backgroundImage.includes('url(') && b.w >= 60 && b.h >= 40) emit('image', { bgImage: true });
    else if (t !== 'body' && t !== 'html' && b.w >= 80 && b.h >= 40 && b.w < W * 0.97 && (border >= 3 || filled))
      emit('box', { filled, border });

    // a text block owns words itself (or wraps a single inline child); a bare row of links is a nav, walk into it
    const ownsText = directText(el) || (el.children.length <= 1 && !el.querySelector('a,button,[role=button]'));
    if (txt && ownsText && !hasBlockChild(el) && [...el.querySelectorAll('img,svg,video,canvas,iframe,input,textarea,select,button')].length === 0) {
      const range = document.createRange(); range.selectNodeContents(el);
      emit('text', { text: txt, words: words(txt), fontSize: parseFloat(st.fontSize), fontWeight: Number(st.fontWeight) || 400, link: c.inA, lines: lineRects(range) });
      return;
    }
    if (directText(el)) {
      for (const n of el.childNodes) {
        if (n.nodeType !== 3 || !n.textContent.trim()) continue;
        const range = document.createRange(); range.selectNodeContents(n);
        const s = clean(n.textContent);
        emit('text', { text: s, words: words(s), fontSize: parseFloat(st.fontSize), fontWeight: Number(st.fontWeight) || 400, link: c.inA, lines: lineRects(range) });
      }
    }
    kids();
  }

  walk(document.body, 'html:1', { ids: [], pos: null }, pageBg);
  const docHeight = Math.max(document.documentElement.scrollHeight, document.body.scrollHeight);
  return { title: document.title, pageBg, docHeight, layout: { width: innerWidth, height: innerHeight }, nodes: out };
}

async function main() {
  const a = parseArgs(process.argv.slice(2));
  const source = describeSource(a.target);
  if (source.localPath && sameUnderlyingFile(source.localPath, a.out)) {
    throw new Error('source and output refer to the same file');
  }
  const url = source.url;
  const browser = await (await loadChromium()).launch();
  try {
    const context = await browser.newContext({
      viewport: { width: a.width, height: a.height }, deviceScaleFactor: 1, isMobile: !!a.mobile, hasTouch: !!a.mobile,
      reducedMotion: 'reduce', colorScheme: 'light', locale: 'en-US', timezoneId: 'UTC',
    });
    await context.route('**/*', (route) => (BLOCK.test(route.request().url()) ? route.abort() : route.continue()));
    const page = await context.newPage();
    await page.clock.setFixedTime(new Date('2026-01-01T12:00:00Z'));
    try { await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 }); }
    catch { await page.goto(url, { waitUntil: 'load', timeout: 30000 }); }
    await page.addStyleTag({ content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important;scroll-behavior:auto!important}' });
    // trigger lazy content, then return to the top
    await page.evaluate(async () => {
      const step = innerHeight * 0.8;
      for (let y = 0; y < document.documentElement.scrollHeight && y < 30000; y += step) { scrollTo(0, y); await new Promise((r) => setTimeout(r, 120)); }
      scrollTo(0, 0);
    });
    await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
    await page.evaluate(() => document.fonts.ready);
    const data = await page.evaluate(extract);
    const outputDir = dirname(resolve(a.out));
    const pendingShot = join(outputDir, `.${basename(a.out)}.${process.pid}.pending.png`);
    await page.screenshot({ path: pendingShot });
    const screenshotSha256 = sha256(readFileSync(pendingShot));
    const generation = sha256(`snapshot\0${SNAPSHOT_FORMAT_VERSION}\0${source.provenance.identity}\0${a.width}x${a.height}x${!!a.mobile}\0${screenshotSha256}`).slice(0, 20);
    const shot = join(outputDir, `capture-${generation}.png`);
    if (existsSync(shot) && sha256(readFileSync(shot)) === screenshotSha256) unlinkSync(pendingShot);
    else renameSync(pendingShot, shot);
    const snap = {
      version: SNAPSHOT_FORMAT_VERSION,
      generation,
      url: source.provenance.displayUrl,
      source: source.provenance,
      capturedAt: new Date().toISOString(), chromium: browser.version(),
      viewport: { width: a.width, height: a.height, mobile: !!a.mobile }, ...data,
      screenshot: { file: basename(shot), sha256: screenshotSha256 },
    };
    atomicWriteJson(a.out, snap);
    console.log(JSON.stringify({ out: resolve(a.out), screenshot: resolve(shot), nodes: snap.nodes.length, docHeight: snap.docHeight }));
  } finally {
    await browser.close();
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((e) => { console.error(`snapshot error: ${e.message}`); process.exit(1); });
}
