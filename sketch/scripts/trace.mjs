#!/usr/bin/env node
// Compile a snapshot (snapshot.mjs) into a sketch spec by fixed rules — no model in the loop.
// Same snapshot + same overrides ⇒ byte-identical spec.
//   node trace.mjs page.snap.json -o page.json [--overrides page.overrides.json] [--full] [--width 760]
// Rules (the "trace grammar"):
//   image/video/embed → X-box · small svg/img → icon (first header icon → logo, unless a header wordmark came first)
//   h1 → always real words · h2–h3 ≤ 8 words → real, else thick squiggle · body text → one squiggle per line
//   nav/header/footer links ≤ 3 words → real words · boxed buttons: label ≤ 3 words real, else squiggle
//   unboxed buttons (dropdown triggers, text buttons) → link text · wide short logos → small X-box
//   icon-only buttons → hamburger when aria-label says menu/nav, else a small icon
//   the single highest-contrast filled button → hatched primary; other boxed buttons → outline
//   bordered or tinted containers → card outline · fixed/sticky nodes below the top 20% → dropped (banners, chat)
//   everything clipped to the viewport; a large image behind ≥ 3 text nodes is decoration → dropped
//   below the fold: text, controls and icons that don't fit entirely are dropped; images and cards are clipped
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const USAGE = 'usage: trace.mjs page.snap.json -o page.json [--overrides o.json] [--full] [--width 760]';

// ---------- overrides matching ----------
// "text=Exact label" | "#id" (node or ancestor id) | ".class" (node's own) | "html:1>body:1>…" (path or ancestor path)
function matches(m, n) {
  if (m.startsWith('text=')) return (n.text || '').trim() === m.slice(5).trim();
  if (m.startsWith('#')) return (n.ids || []).includes(m.slice(1));
  if (m.startsWith('.')) return (n.cls || []).includes(m.slice(1));
  return n.path === m || n.path.startsWith(m + '>');
}
const any = (list, n) => (list || []).some((m) => matches(m, n));

// ---------- colour ----------
function rgb(c) { const m = /rgba?\(([^)]+)\)/.exec(c || ''); if (!m) return null; const [r, g, b, a = 1] = m[1].split(',').map(Number); return { r, g, b, a }; }
function lum(c) { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); }
function contrast(a, b) { const A = rgb(a), B = rgb(b); if (!A || !B || A.a === 0) return 1; const x = lum(A), y = lum(B); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); }

function hash(s) { let h = 5381; for (const ch of s) h = ((h * 33) ^ ch.charCodeAt(0)) >>> 0; return h % 100000; }
const r1 = (v) => Math.round(v * 10) / 10;
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

export const NOTE_GUTTER = 240;
export function compile(snap, ov = {}, opts = {}) {
  // layout viewport: differs from the device viewport when a mobile page has no <meta name="viewport">
  const vw = snap.layout?.width ?? snap.viewport.width, vh = snap.layout?.height ?? snap.viewport.height, mobile = snap.viewport.mobile;
  const frameW = snap.viewport.width;
  const full = opts.full ?? ov.full ?? false;
  const sketchW = opts.width ?? ov.width ?? (mobile ? 300 : 760);
  const s = opts.scale != null ? opts.scale * frameW / vw : sketchW / vw;
  const pre = opts.prefix ?? '';
  const maxY = full ? Math.min(snap.docHeight, vh * (ov.maxViewports ?? 4)) : vh;
  const notes = ov.notes || [];
  const M = 44, left = notes.some((n) => n.side === 'left') ? NOTE_GUTTER : 0;
  const chromeH = mobile ? 26 : 24;
  const X0 = opts.origin?.x ?? M + left, Y0 = (opts.origin?.y ?? M + (ov.title ? 60 : 0)) + chromeH;
  const X = (x) => r1(X0 + x * s), Y = (y) => r1(Y0 + y * s);

  // 1. filter
  const CLIPPABLE = new Set(['image', 'video', 'embed', 'box']);
  let nodes = snap.nodes.filter((n) => {
    if (any(ov.hide, n)) return false;
    if (any(ov.keep, n)) return true;
    if (n.y >= maxY || n.x >= vw || n.x + n.w <= 0) return false;
    if (n.pos === 'fixed' && n.y > vh * 0.2) return false; // cookie bars, chat bubbles
    if (!CLIPPABLE.has(n.kind) && !n.lines && n.y + n.h > maxY + 2) return false; // cut off by the fold
    return true;
  }).map((n) => {
    const x = Math.max(0, n.x), w = Math.min(n.x + n.w, vw) - x; // clip to the viewport
    return { ...n, x, w, kind: Object.entries(ov.as || {}).find(([m]) => matches(m, n))?.[1] ?? n.kind };
  });
  // clip text lines to the viewport
  nodes = nodes.map((n) => (n.lines ? { ...n, lines: n.lines.map((l) => { const x = Math.max(0, l.x); return { ...l, x, w: Math.min(l.x + l.w, vw) - x }; }).filter((l) => l.w > 2) } : n));
  // duplicates: overlay copies (same kind + text, boxes overlap ≥ 90%) keep the first
  const overlap = (a, b) => { const ix = Math.max(0, Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)), iy = Math.max(0, Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y)); return (ix * iy) / Math.max(1, Math.min(a.w * a.h, b.w * b.h)); };
  nodes = nodes.filter((n, i) => !nodes.slice(0, i).some((m) => m.kind === n.kind && (m.text || '') === (n.text || '') && overlap(m, n) >= 0.9));
  // decoration: a big image with ≥ 3 text/heading/button nodes centred on top of it
  const inside = (m, n) => { const cx = n.x + n.w / 2, cy = n.y + n.h / 2; return cx > m.x && cx < m.x + m.w && cy > m.y && cy < m.y + m.h; };
  const decor = new Set(nodes.filter((m) => m.kind === 'image' && !any(ov.keep, m) && m.w * Math.min(m.h, maxY - m.y) >= vw * vh * 0.2 &&
    nodes.filter((n) => ['text', 'heading', 'button'].includes(n.kind) && inside(m, n)).length >= 3));
  nodes = nodes.filter((n) => !decor.has(n));

  // 2. primary: forced by overrides, else the highest-contrast filled button (contrast ≥ 1.6)
  const buttons = nodes.filter((n) => n.kind === 'button');
  const primarySelector = typeof ov.primary === 'string' ? ov.primary : null;
  let primary = primarySelector == null ? null : buttons.find((n) => matches(primarySelector, n));
  if (primarySelector != null && !primary) {
    throw new Error(`override primary: no button matches selector "${primarySelector}"; update the selector or use primary: false`);
  }
  if (!primary && ov.primary !== false) {
    let best = 0;
    for (const n of buttons) {
      if (!n.filled) continue;
      const c = contrast(n.bg, snap.pageBg);
      const score = c * Math.sqrt(n.w * n.h) * (n.y < vh ? 1.5 : 1);
      if (c >= 1.6 && score > best) { best = score; primary = n; }
    }
  }

  const realWord = (n, limit) => !any(ov.squiggle, n) && (any(ov.real, n) || (labelOf(n) || '').split(/\s+/).filter(Boolean).length <= limit);
  const undouble = (t) => { const w = (t || '').split(' '); const h = w.length / 2; return w.length % 2 === 0 && w.slice(0, h).join(' ') === w.slice(h).join(' ') ? w.slice(0, h).join(' ') : t; }; // "Sign in Sign in" hover copies
  const labelOf = (n) => { const l = Object.entries(ov.label || {}).find(([m]) => matches(m, n)); return l ? l[1] : undouble(n.text); };

  const items = [];
  const idOf = new Map();
  let k = 0;
  const push = (n, item) => { const id = `${pre}t${++k}`; idOf.set(n, id); items.push({ id, ...item }); };
  const clipH = (n) => Math.min(n.h, maxY - n.y);
  let logoDone = false;

  // screen frame first, then boxes (largest first) so content draws on top
  items.push({ type: 'screen', id: `${pre}page`, chrome: mobile ? 'phone' : 'browser', x: X0, y: Y0 - chromeH, w: r1(vw * s), h: r1(maxY * s + chromeH) });
  const boxes = nodes.filter((n) => n.kind === 'box' && n.w * n.h >= vw * vh * 0.012).sort((a, b) => b.w * b.h - a.w * a.h || a.y - b.y).slice(0, 40);
  for (const n of boxes) push(n, { type: 'card', x: X(n.x), y: Y(n.y), w: r1(n.w * s), h: r1(clipH(n) * s), children: [] });

  for (const n of nodes) {
    const w = r1(n.w * s), h = r1(clipH(n) * s);
    switch (n.kind) {
      case 'image': case 'video': case 'embed':
        if ((w >= 10 && h >= 10) || (n.wordmark && w >= 14 && h >= 4)) {
          if (n.wordmark && (n.inHeader || n.inNav)) logoDone = true; // a header wordmark is the logo
          push(n, { type: n.kind === 'video' ? 'video' : n.kind === 'embed' ? 'placeholder' : 'image', ...(n.kind === 'embed' ? { label: 'embed' } : {}), x: X(n.x), y: Y(n.y), w, h });
        }
        break;
      case 'icon': {
        const d = clamp(Math.min(n.w, n.h) * s, 6, 30);
        if (d < 7) break;
        if (!logoDone && (n.inHeader || n.inNav)) { logoDone = true; push(n, { type: 'logo', x: X(n.x), y: Y(n.y), d: r1(clamp(d, 14, 30)) }); }
        else push(n, { type: 'icons', n: 1, x: X(n.x), y: Y(n.y), d: r1(clamp(d, 7, 16)) });
        break;
      }
      case 'button': {
        const text = labelOf(n);
        if (!text) { // icon-only button: hamburger when it opens a menu, else a small icon
          const d = r1(clamp(Math.min(n.w, n.h) * s * 0.7, 8, 20));
          if (/menu|nav|navigation/i.test(n.aria || '')) push(n, { type: 'burger', x: r1(X(n.x) + (w - d) / 2), y: r1(Y(n.y) + (h - d * 0.8) / 2), d });
          else if (d >= 8) push(n, { type: 'icons', n: 1, x: r1(X(n.x) + (w - d) / 2), y: r1(Y(n.y) + (h - d) / 2), d });
          break;
        }
        if (!(n.boxed ?? (n.filled || n.border >= 3)) && n !== primary) { // text button → link text
          const size = r1(clamp(h * 0.62, 10, 16));
          if (realWord(n, 3)) push(n, { type: 'text', text, size, overflow: 'fit', x: X(n.x), y: r1(Y(n.y) + (h - size * 1.35) / 2), w: r1(w + 6) });
          else push(n, { type: 'squiggle', x: X(n.x), y: r1(Y(n.y) + (h - 11) / 2), w });
          break;
        }
        const bh = r1(clamp(h, 16, 44));
        push(n, {
          type: 'button', x: X(n.x), y: r1(Y(n.y) + (h - bh) / 2), w: r1(Math.max(w, 24)), h: bh,
          variant: n === primary ? 'primary' : 'outline',
          label: text && realWord(n, 3) ? text : text ? '~' : undefined,
        });
        break;
      }
      case 'input': case 'textarea': case 'dropdown': {
        const t = n.kind === 'dropdown' ? 'dropdown' : 'input';
        const text = labelOf(n);
        const item = { type: t, x: X(n.x), y: Y(n.y), w };
        if (t === 'input') { item.h = r1(Math.max(h, 18)); if (n.kind === 'textarea') item.rows = Math.max(1, Math.round(h / 22)); }
        if (text && realWord(n, 3)) item[t === 'dropdown' ? 'value' : 'placeholder'] = text;
        push(n, item);
        break;
      }
      case 'checkbox': case 'radio':
        push(n, { type: n.kind, x: X(n.x), y: Y(n.y), checked: !!n.checked });
        break;
      case 'divider':
        push(n, { type: 'divider', x: X(n.x), y: Y(n.y), w });
        break;
      case 'heading': {
        const lines = (n.lines || []).filter((l) => l.y + l.h <= maxY + 2);
        const real = n.level === 1 ? !any(ov.squiggle, n) : n.level <= 3 ? realWord(n, 8) : any(ov.real, n);
        const text = labelOf(n) || '';
        const ws = text.split(/\s+/).filter(Boolean);
        const total = lines.reduce((a, l) => a + l.w, 0) || 1;
        let wi = 0;
        lines.forEach((l, i) => {
          const size = r1(clamp(Math.min(n.fontSize * s, l.h * s * 0.85), 11, 34));
          let part = l.text; // exact words from the snapshot; proportional split only for overridden labels
          if (part == null || labelOf(n) !== n.text) { const take = i === lines.length - 1 ? ws.length - wi : Math.round(ws.length * (l.w / total)); part = ws.slice(wi, wi + take).join(' '); wi += take; }
          if (real && part) push(i === 0 ? n : {}, { type: 'text', text: part, size, overflow: 'fit', x: X(l.x), y: r1(Y(l.y) + (l.h * s - size * 1.35) / 2), w: r1(l.w * s + 8) });
          else push(i === 0 ? n : {}, { type: 'squiggle', thick: true, x: X(l.x), y: r1(Y(l.y) + (l.h * s - 14) / 2), w: r1(l.w * s) });
        });
        break;
      }
      case 'text': {
        const lines = (n.lines || []).filter((l) => l.y + l.h <= maxY + 2);
        const navish = n.inNav || n.inHeader || n.inFooter;
        const real = any(ov.real, n) || (!any(ov.squiggle, n) && navish && n.link && n.words <= 3);
        if (real && lines.length) {
          const l = lines[0], size = r1(clamp(n.fontSize * s, 10, 16));
          push(n, { type: 'text', text: labelOf(n), size, overflow: 'fit', x: X(l.x), y: r1(Y(l.y) + (l.h * s - size * 1.35) / 2), w: r1(l.w * s + 6) });
          break;
        }
        const thick = n.fontWeight >= 600 || n.fontSize >= 20;
        lines.forEach((l, i) => {
          const lw = r1(l.w * s);
          if (lw >= 8) push(i === 0 ? n : {}, { type: 'squiggle', thick, x: X(l.x), y: r1(Y(l.y) + (l.h * s - (thick ? 14 : 11)) / 2), w: lw });
        });
        break;
      }
    }
  }

  // notes from overrides: anchored to the first matching node
  for (const note of notes) {
    const target = nodes.find((n) => matches(note.at, n) && idOf.has(n));
    if (!target) throw new Error(`override note: nothing matches "${note.at}"`);
    const side = note.side || 'right';
    const fy = clamp((target.y + target.h / 2) / maxY, 0.05, 0.95);
    items.push({ type: 'note', text: note.text, near: `${pre}page`, side, offset: 36, fy: r1(fy * 100) / 100, to: idOf.get(target), ...(note.ink ? { ink: note.ink } : {}) });
  }

  return {
    paper: ov.paper ?? 'grid',
    seed: ov.seed ?? hash(snap.url),
    ...(ov.title ? { title: ov.title } : {}),
    source: { url: snap.url, capturedAt: snap.capturedAt, viewport: snap.viewport, traced: 'trace.mjs v1' },
    items,
  };
}

function main() {
  const argv = process.argv.slice(2);
  const a = {};
  const rest = [];
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    if (k === '-o' || k === '--out') a.out = argv[++i];
    else if (k === '--overrides') a.overrides = argv[++i];
    else if (k === '--full') a.full = true;
    else if (k === '--width') a.width = Number(argv[++i]);
    else if (k === '-h' || k === '--help') { console.log(USAGE); process.exit(0); }
    else if (k.startsWith('-')) { console.error(`unknown option ${k}\n${USAGE}`); process.exit(1); }
    else rest.push(k);
  }
  if (rest.length !== 1 || !a.out) { console.error(USAGE); process.exit(1); }
  try {
    const snap = JSON.parse(readFileSync(rest[0], 'utf8'));
    const ov = a.overrides ? JSON.parse(readFileSync(a.overrides, 'utf8')) : {};
    const spec = compile(snap, ov, { full: a.full, width: a.width });
    if (resolve(a.out) === resolve(rest[0])) throw new Error('refusing to overwrite the snapshot — pass a different -o');
    writeFileSync(a.out, JSON.stringify(spec, null, 1) + '\n');
    console.log(JSON.stringify({ out: resolve(a.out), items: spec.items.length }));
  } catch (e) {
    console.error(`trace error: ${e.message}`);
    process.exit(1);
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) main();
