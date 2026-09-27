// Component library in sketch grammar. Each entry:
//   h(node, w, C)        -> height for a given width (pure — no RNG)
//   iw(node, C)          -> intrinsic width (optional; used when node.w is unset and fit applies)
//   fit                  -> true: shrink to intrinsic width by default
//   draw(C, node, x, y, w, h)
// Any string that is only "~" characters renders as a squiggle placeholder ("~" short, "~~~" long).
(function () {
  const T = CSI.tokens;
  const isSq = (s) => typeof s === 'string' && /^~+$/.test(s.trim());
  const sqW = (s) => 26 + s.trim().length * 22;

  function labelW(C, s, size, font) { return isSq(s) ? sqW(s) : C.measure(s, size ?? T.size.text, font); }
  // baseline y
  function label(C, s, x, y, o = {}) {
    if (s == null || s === '') return 0;
    const size = o.size ?? T.size.text;
    if (isSq(s)) {
      const w = o.w ?? sqW(s);
      const sx = o.anchor === 'middle' ? x - w / 2 : o.anchor === 'end' ? x - w : x;
      C.squiggle(sx, y - size * 0.3, w, { ink: o.ink, thick: o.thick });
      return w;
    }
    return C.text(x, y, s, o);
  }
  const lines = (s) => String(s ?? '').split('\n');
  // Shrink to minSize, then truncate with an ellipsis, until s fits maxW. Measured, so deterministic.
  function fitText(Cx, s, size, maxW, font, minSize = 10) {
    if (isSq(s) || !(maxW > 0)) return { s, size };
    while (size > minSize && Cx.measure(s, size, font) > maxW) size -= 1;
    if (Cx.measure(s, size, font) <= maxW) return { s, size };
    let t = s;
    while (t.length > 1 && Cx.measure(t + '…', size, font) > maxW) t = t.slice(0, -1);
    return { s: t.trimEnd() + '…', size };
  }

  const C = {};
  const REG = (name, def) => { C[name] = def; };

  // ---------- containers ----------
  function stackH(Cx, kids, w, gap) {
    if (!kids || !kids.length) return 0;
    return kids.reduce((a, k) => a + CSI.measureNode(Cx, k, w).h, 0) + gap * (kids.length - 1);
  }
  function drawStack(Cx, kids, x, y, w, gap) {
    let cy = y;
    for (const k of kids || []) cy += CSI.placeNode(Cx, k, x, cy, w).h + gap;
    return cy - y - (kids && kids.length ? gap : 0);
  }
  function rowWidths(Cx, kids, w, gap) {
    const fixed = kids.map((k) => {
      if (k.w != null) return CSI.resolveW(k.w, w);
      const d = C[k.type];
      if (d && d.iw && (k.fit ?? d.fit)) return d.iw(k, Cx);
      return null;
    });
    const used = fixed.reduce((a, v) => a + (v ?? 0), 0) + gap * (kids.length - 1);
    const flex = fixed.filter((v) => v == null).length;
    const each = flex ? Math.max(20, (w - used) / flex) : 0;
    return fixed.map((v) => v ?? each);
  }

  REG('stack', {
    h: (n, w, Cx) => stackH(Cx, n.children, w, n.gap ?? 10),
    draw: (Cx, n, x, y, w) => drawStack(Cx, n.children, x, y, w, n.gap ?? 10),
  });

  REG('row', {
    h: (n, w, Cx) => {
      const ws = rowWidths(Cx, n.children || [], w, n.gap ?? 10);
      return Math.max(0, ...(n.children || []).map((k, i) => CSI.measureNode(Cx, { ...k, w: ws[i] }, ws[i]).h));
    },
    draw: (Cx, n, x, y, w, h) => {
      const kids = n.children || [], gap = n.gap ?? 10;
      const ws = rowWidths(Cx, kids, w, gap);
      const total = ws.reduce((a, b) => a + b, 0) + gap * (kids.length - 1);
      if (total > w + 1) Cx.warnings.push(`row${n.id ? ` "${n.id}"` : ''} is ${Math.round(total - w)}px wider than its container — shrink children or widen the parent`);
      let cx = n.justify === 'center' ? x + (w - total) / 2 : n.justify === 'end' ? x + w - total : x;
      if (n.justify === 'between' && kids.length > 1) {
        const sp = (w - ws.reduce((a, b) => a + b, 0)) / (kids.length - 1);
        kids.forEach((k, i) => { const kh = CSI.measureNode(Cx, { ...k, w: ws[i] }, ws[i]).h; CSI.placeNode(Cx, { ...k, w: ws[i] }, cx, y + (h - kh) / 2, ws[i]); cx += ws[i] + sp; });
        return;
      }
      kids.forEach((k, i) => {
        const kh = CSI.measureNode(Cx, { ...k, w: ws[i] }, ws[i]).h;
        const ky = n.valign === 'top' ? y : y + (h - kh) / 2;
        CSI.placeNode(Cx, { ...k, w: ws[i] }, cx, ky, ws[i]);
        cx += ws[i] + gap;
      });
    },
  });

  const colsOf = (n) => { const c = n.cols ?? 3; if (!Number.isInteger(c) || c < 1) throw new Error(`grid.cols must be a positive integer (got ${JSON.stringify(n.cols)})`); return c; };
  REG('grid', {
    h: (n, w, Cx) => {
      const cols = colsOf(n), gap = n.gap ?? 10, cw = (w - gap * (cols - 1)) / cols;
      const kids = n.children || [];
      let h = 0;
      for (let i = 0; i < kids.length; i += cols)
        h += Math.max(...kids.slice(i, i + cols).map((k) => CSI.measureNode(Cx, { ...k, w: cw }, cw).h)) + gap;
      return Math.max(0, h - gap);
    },
    draw: (Cx, n, x, y, w) => {
      const cols = colsOf(n), gap = n.gap ?? 10, cw = (w - gap * (cols - 1)) / cols;
      const kids = n.children || [];
      let cy = y;
      for (let i = 0; i < kids.length; i += cols) {
        const row = kids.slice(i, i + cols);
        const rh = Math.max(...row.map((k) => CSI.measureNode(Cx, { ...k, w: cw }, cw).h));
        row.forEach((k, j) => CSI.placeNode(Cx, { ...k, w: cw }, x + j * (cw + gap), cy, cw));
        cy += rh + gap;
      }
    },
  });

  REG('card', {
    h: (n, w, Cx) => stackH(Cx, n.children, w - 2 * (n.pad ?? 10), n.gap ?? 8) + 2 * (n.pad ?? 10),
    draw: (Cx, n, x, y, w, h) => {
      Cx.rect(x, y, w, h, { sw: T.stroke.detail, dashed: n.dashed, r: n.r, ink: n.ink });
      const p = n.pad ?? 10;
      drawStack(Cx, n.children, x + p, y + p, w - 2 * p, n.gap ?? 8);
    },
  });

  // Screen / frame. chrome: plain | browser | phone | modal | panel
  const chromeTop = (n) => ({ browser: 24, phone: 26, modal: 10, panel: 10, plain: 0 }[n.chrome || 'plain'] ?? 0) + (n.title ? 30 : 0);
  REG('screen', {
    h: (n, w, Cx) => {
      const p = n.pad ?? 14;
      return chromeTop(n) + p * 2 + stackH(Cx, n.children, w - 2 * p, n.gap ?? 10) + (n.zigzag ? 8 : 0);
    },
    draw: (Cx, n, x, y, w, h) => {
      const p = n.pad ?? 14, chrome = n.chrome || 'plain';
      const r = chrome === 'phone' ? 18 : 0;
      if (n.zigzag) {
        // open bottom edge = panel continues / scrolls
        const zy = y + h - 6;
        Cx.line(x, y + h, x, y, { sw: T.stroke.frame });
        Cx.line(x, y, x + w, y, { sw: T.stroke.frame });
        Cx.line(x + w, y, x + w, y + h, { sw: T.stroke.frame });
        const pts = []; for (let i = 0, px = x; px <= x + w; px += 9, i++) pts.push([px, zy + (i % 2 ? 5 : -2)]);
        Cx.curve(pts, { sw: 1.3, roughness: 0.4, single: true });
      } else {
        Cx.rect(x, y, w, h, { sw: T.stroke.frame, r, ink: n.ink, dashed: n.dashed });
      }
      let top = y;
      if (chrome === 'browser') {
        Cx.line(x, y + 22, x + w, y + 22, { sw: 1.1 });
        for (let i = 0; i < 3; i++) Cx.circle(x + 12 + i * 11, y + 11, 6, { sw: 1, single: true });
        Cx.rect(x + 50, y + 5, Math.min(w - 70, 180), 12, { sw: 0.9, r: 5, single: true });
        top += 24;
      } else if (chrome === 'phone') {
        Cx.line(x + w / 2 - 14, y + 12, x + w / 2 + 14, y + 12, { sw: 2.2, single: true });
        top += 26;
      } else if (chrome === 'modal' || chrome === 'panel') top += 10;
      if (n.close ?? (chrome === 'modal' || chrome === 'panel')) {
        const cx = x + w - 16, cy = y + 13;
        Cx.line(cx - 5, cy - 5, cx + 5, cy + 5, { sw: 1.5, single: true });
        Cx.line(cx + 5, cy - 5, cx - 5, cy + 5, { sw: 1.5, single: true });
      }
      if (n.menu) {
        const mx = x + w - ((n.close ?? (chrome === 'modal' || chrome === 'panel')) ? 40 : 18), my = top + 6;
        for (let i = 0; i < 3; i++) Cx.line(mx - 7, my + i * 5, mx + 7, my + i * 5, { sw: 1.6, single: true });
      }
      if (n.title) {
        label(Cx, n.title, x + p, top + 22, { size: 19 });
        top += 30;
      }
      let used = 0;
      const drawKids = () => { used = drawStack(Cx, n.children, x + p, top + p, w - 2 * p, n.gap ?? 10); };
      if (n.clip) Cx.clip(x + 2, top + 2, w - 4, y + h - top - 4, drawKids, `${n.template ? `page "${n.template}"` : `screen "${n.id || '?'}"`}`);
      else drawKids();
      const limit = y + h - p - (n.zigzag ? 8 : 0); // keep visible bottom padding
      if (top + p + used > limit) Cx.warnings.push(`screen "${n.id || n.title || '?'}" content overflows its bottom padding by ${Math.round(top + p + used - limit)}px — raise h`);
    },
  });

  // A page thumbnail built from a named template in lib/pages.js (CSI.pages).
  // The template receives (node, {w, h}) — the inner content box — and returns { title, children }.
  REG('page', {
    h: (n, w) => n.h ?? Math.round(w * 1.3),
    draw: (Cx, n, x, y, w, h) => {
      const tpl = CSI.pages && CSI.pages[n.template];
      if (!tpl) throw new Error(`unknown page template "${n.template}" — known: ${Object.keys(CSI.pages || {}).join(', ')}`);
      const pad = n.pad ?? 8, labelH = n.label === false ? 0 : 20;
      const t = tpl(n, { w: w - 2 * pad, h: h - 2 * pad - labelH });
      C.screen.draw(Cx, { id: n.id, template: n.template, clip: true, chrome: 'plain', pad, gap: n.gap ?? 6, children: [{ type: 'spacer', h: labelH - 6 }, ...t.children] }, x, y, w, h);
      if (n.label !== false) label(Cx, n.label ?? t.title ?? n.template, x + w / 2, y + pad + 11, { size: 12, anchor: 'middle' });
    },
  });

  // ---------- text ----------
  REG('text', {
    fit: true,
    iw: (n, Cx) => Math.max(...lines(n.text).map((l) => labelW(Cx, l, n.size, n.font))) + 2,
    h: (n) => lines(n.text).length * (n.size ?? T.size.text) * 1.35,
    draw: (Cx, n, x, y, w) => {
      const size = n.size ?? T.size.text;
      lines(n.text).forEach((l, i) => {
        const bx = n.align === 'center' ? x + w / 2 : n.align === 'right' ? x + w : x;
        const anchor = n.align === 'center' ? 'middle' : n.align === 'right' ? 'end' : 'start';
        const f = n.overflow === 'fit' ? fitText(Cx, l, size, w, n.font) : { s: l, size };
        label(Cx, f.s, bx, y + size * (1.0 + i * 1.35), { size: f.size, font: n.font, ink: n.ink, anchor, w: isSq(l) ? w : undefined });
      });
    },
  });

  REG('heading', {
    fit: true,
    iw: (n, Cx) => labelW(Cx, n.text, n.size ?? T.size.heading, n.font) + 6,
    h: (n) => (n.size ?? T.size.heading) * 1.35 + (n.underline === false ? 0 : 6),
    draw: (Cx, n, x, y, w) => {
      const size = n.size ?? T.size.heading;
      const tw = labelW(Cx, n.text, size, n.font);
      const sx = n.align === 'center' ? x + (w - tw) / 2 : x;
      label(Cx, n.text, sx, y + size, { size, font: n.font, ink: n.ink, thick: true });
      if (n.underline !== false) Cx.underline(sx, y + size + 6, tw, { double: n.underline === 2, ink: n.ink });
    },
  });

  // Placeholder copy: lines of squiggles. lines, align (left|center), thick (headline)
  REG('squiggle', {
    h: (n) => (n.lines ?? 1) * (n.thick ? 14 : 11),
    draw: (Cx, n, x, y, w) => {
      const L = n.lines ?? 1, lh = n.thick ? 14 : 11;
      for (let i = 0; i < L; i++) {
        const frac = L > 1 && i === L - 1 ? 0.45 + Cx.rng() * 0.2 : 0.85 + Cx.rng() * 0.15;
        const lw = w * frac;
        const sx = n.align === 'center' ? x + (w - lw) / 2 : x;
        Cx.squiggle(sx, y + lh * i + lh / 2, lw, { thick: n.thick, ink: n.ink });
      }
    },
  });
  C.paragraph = { ...C.squiggle, h: (n) => (n.lines ?? 3) * 11, draw: (Cx, n, x, y, w, h) => C.squiggle.draw(Cx, { ...n, lines: n.lines ?? 3 }, x, y, w, h) };

  REG('bullets', {
    h: (n) => {
      let c = 0; const walk = (it) => it.forEach((i) => { c++; if (i && i.items) walk(i.items); }); walk(n.items || []);
      return c * (n.size ?? T.size.text) * 1.45;
    },
    draw: (Cx, n, x, y) => {
      const size = n.size ?? T.size.text, lh = size * 1.45;
      let cy = y;
      const walk = (items, depth) => items.forEach((it) => {
        const txt = typeof it === 'string' ? it : it.text;
        const bx = x + depth * 22;
        Cx.line(bx, cy + size * 0.62, bx + 8, cy + size * 0.62 + Cx.j(1), { sw: 1.3, single: true, ink: n.ink });
        label(Cx, txt, bx + 14, cy + size, { size, font: n.font, ink: n.ink });
        cy += lh;
        if (it && it.items) walk(it.items, depth + 1);
      });
      walk(n.items || [], 0);
    },
  });

  // ---------- controls ----------
  REG('button', {
    fit: true,
    iw: (n, Cx) => (n.label ? labelW(Cx, n.label, 15) + 32 : 70),
    h: (n) => n.h ?? (n.size === 'sm' ? 24 : 34),
    draw: (Cx, n, x, y, w, h) => {
      const v = n.variant || 'primary';
      if (v === 'link') { const tw = label(Cx, n.label || '~', x, y + h * 0.65, { size: 15 }); Cx.underline(x, y + h * 0.65 + 4, tw, { sw: 1.1 }); return; }
      const r = n.pill ? h / 2 : 5;
      if (v === 'primary') Cx.rect(x, y, w, h, { sw: T.stroke.frame, hatch: true, r, hatchGap: n.label ? 7 : 4.2, ink: n.ink });
      else Cx.rect(x, y, w, h, { sw: v === 'outline' ? 2.1 : 1.2, r, ink: n.ink });
      if (v === 'outline') Cx.rect(x + 1.5, y + 1.5, w - 3, h - 3, { sw: 0.9, r, single: true, ink: n.ink });
      if (n.label) {
        const f = fitText(Cx, n.label, Math.min(15, Math.max(10, h * 0.5)), w - 12, 'hand');
        label(Cx, f.s, x + w / 2, y + h / 2 + f.size * 0.36, { size: f.size, anchor: 'middle', halo: v === 'primary', w: w - 24 });
      }
    },
  });

  const fieldLabelH = (n) => (n.label ? 20 : 0);
  REG('input', {
    h: (n) => fieldLabelH(n) + (n.rows ? n.rows * 20 + 10 : 30),
    draw: (Cx, n, x, y, w, h) => {
      if (n.label) label(Cx, n.label, x, y + 14, { size: 14 });
      const by = y + fieldLabelH(n), bh = h - fieldLabelH(n);
      Cx.rect(x, by, w, bh, { sw: 1.4, r: 3 });
      const ts = Math.max(9, Math.min(14, bh * 0.55)), base = n.rows ? by + 20 : by + bh / 2 + ts * 0.35;
      if (n.filled) Cx.squiggle(x + 8, n.rows ? by + 15 : by + bh / 2, Math.min(w - 16, w * 0.55), { sw: 1.1 });
      else if (n.value || n.placeholder) { const f = fitText(Cx, n.value || n.placeholder, ts, w - 14, 'hand'); label(Cx, f.s, x + 7, base, { size: f.size, ink: n.value ? null : 'note', w: Math.min(w - 16, 90) }); }
    },
  });
  C.textarea = { ...C.input, h: (n) => fieldLabelH(n) + (n.rows ?? 3) * 20 + 10 };

  REG('dropdown', {
    h: (n) => fieldLabelH(n) + 30,
    draw: (Cx, n, x, y, w, h) => {
      if (n.label) label(Cx, n.label, x, y + 14, { size: 14 });
      const by = y + fieldLabelH(n);
      Cx.rect(x, by, w, 30, { sw: 1.4, r: 3 });
      Cx.line(x + w - 26, by + 2, x + w - 26, by + 28, { sw: 1.1, single: true });
      Cx.path(`M${x + w - 19},${by + 12} L${x + w - 13},${by + 19} L${x + w - 7},${by + 12}`, { sw: 1.5, single: true, roughness: 0.4 });
      if (n.value) label(Cx, n.value, x + 8, by + 20, { size: 14, w: Math.min(80, w - 44) });
    },
  });
  C.select = C.dropdown;

  REG('slider', {
    h: (n) => fieldLabelH(n) + 22,
    draw: (Cx, n, x, y, w, h) => {
      if (n.label) label(Cx, n.label, x, y + 14, { size: 14 });
      if (n.display != null) label(Cx, String(n.display), x + w, y + 14, { size: 13, anchor: 'end' });
      const ty = y + fieldLabelH(n) + 8, v = Math.min(1, Math.max(0, n.value ?? 0.5));
      Cx.rect(x, ty, w, 7, { sw: 1.2, r: 3 });
      const tx = x + 4 + v * (w - 14);
      Cx.rect(tx, ty - 6, 10, 19, { sw: 1.5, fillPaper: true });
    },
  });

  REG('toggle', {
    fit: true,
    iw: (n, Cx) => 40 + (n.label ? labelW(Cx, n.label, 14) + 10 : 0),
    h: () => 22,
    draw: (Cx, n, x, y) => {
      Cx.rect(x, y + 2, 36, 18, { sw: 1.4, r: 9, hatch: !!n.on });
      Cx.circle(n.on ? x + 27 : x + 9, y + 11, 13, { sw: 1.4, fillPaper: true });
      if (n.label) label(Cx, n.label, x + 46, y + 16, { size: 14 });
    },
  });

  REG('checkbox', {
    fit: true,
    iw: (n, Cx) => 24 + (n.label ? labelW(Cx, n.label, 14) : 0),
    h: () => 22,
    draw: (Cx, n, x, y) => {
      if (n.radio) { Cx.circle(x + 8, y + 11, 15, { sw: 1.3 }); if (n.checked) Cx.circle(x + 8, y + 11, 6, { solid: true, sw: 1 }); }
      else { Cx.rect(x, y + 3, 15, 15, { sw: 1.3 }); if (n.checked) Cx.path(`M${x + 2},${y + 10} L${x + 7},${y + 16} L${x + 17},${y}`, { sw: 1.8, single: true, roughness: 0.5 }); }
      if (n.label) label(Cx, n.label, x + 24, y + 16, { size: 14 });
    },
  });
  C.radio = { ...C.checkbox, draw: (Cx, n, x, y, w, h) => C.checkbox.draw(Cx, { ...n, radio: true }, x, y, w, h) };

  REG('tabs', {
    h: () => 32,
    draw: (Cx, n, x, y, w) => {
      const items = n.items || [];
      if (!items.length) return Cx.line(x, y + 30, x + w, y + 30, { sw: 0.9, single: true });
      const gap = Math.min(20, w / (items.length * 4));
      const nat = items.map((t) => labelW(Cx, t, 15));
      const avail = Math.max(items.length * 6, w - gap * (items.length - 1));
      const k = Math.min(1, avail / nat.reduce((a, b) => a + b, 0)); // ≥ 0 by construction
      let cx = x;
      items.forEach((t, i) => {
        const tw = Math.max(6, nat[i] * k);
        const f = fitText(Cx, t, Math.max(10, 15 * k), tw + 2, 'hand');
        label(Cx, f.s, cx, y + 20, { size: f.size, w: tw });
        if (i === (n.active ?? 0)) Cx.line(cx - 2, y + 27, cx + tw + 2, y + 27, { sw: 2.4, single: true });
        cx += tw + gap;
      });
      Cx.line(x, y + 30, x + w, y + 30, { sw: 0.9, single: true });
    },
  });


  // ---------- media & placeholders ----------
  REG('image', {
    h: (n, w) => n.h ?? Math.round(w * (n.ratio ?? 0.62)),
    draw: (Cx, n, x, y, w, h) => {
      Cx.rect(x, y, w, h, { sw: 1.5, ink: n.ink });
      Cx.line(x + 2, y + 2, x + w - 2, y + h - 2, { sw: 1, single: true, ink: n.ink });
      Cx.line(x + w - 2, y + 2, x + 2, y + h - 2, { sw: 1, single: true, ink: n.ink });
      if (n.play) { const cx = x + w / 2, cy = y + h / 2; Cx.circle(cx, cy, 34, { fillPaper: true, sw: 1.4 }); Cx.path(`M${cx - 5},${cy - 8} L${cx + 9},${cy} L${cx - 5},${cy + 8} Z`, { solid: true, sw: 1 }); }
      if (n.label) { const tw = Cx.measure(n.label, 14); Cx.rect(x + w / 2 - tw / 2 - 6, y + h / 2 - 11, tw + 12, 22, { fillPaper: true, sw: 1 }); label(Cx, n.label, x + w / 2, y + h / 2 + 5, { size: 14, anchor: 'middle' }); }
    },
  });
  C.video = { ...C.image, draw: (Cx, n, x, y, w, h) => C.image.draw(Cx, { ...n, play: true }, x, y, w, h) };

  REG('avatar', {
    fit: true,
    iw: (n) => n.d ?? 46,
    h: (n) => n.d ?? 46,
    draw: (Cx, n, x, y, w) => {
      const d = n.d ?? 46, cx = x + (w - d) / 2 + d / 2, cy = y + d / 2;
      Cx.circle(cx, cy, d, { sw: 1.5 });
      if (n.figure) {
        Cx.circle(cx, cy - d * 0.12, d * 0.3, { sw: 1.2, single: true });
        Cx.path(`M${cx - d * 0.3},${cy + d * 0.34} Q${cx},${cy + d * 0.02} ${cx + d * 0.3},${cy + d * 0.34}`, { sw: 1.2, single: true });
      } else {
        const k = d * 0.35;
        Cx.line(cx - k, cy - k, cx + k, cy + k, { sw: 1.1, single: true });
        Cx.line(cx + k, cy - k, cx - k, cy + k, { sw: 1.1, single: true });
      }
    },
  });
  C.logo = { ...C.avatar, iw: (n) => n.d ?? 24, h: (n) => n.d ?? 24, draw: (Cx, n, x, y, w, h) => C.avatar.draw(Cx, { ...n, d: n.d ?? 24 }, x, y, w, h) };

  REG('add', {
    h: (n) => n.h ?? 80,
    draw: (Cx, n, x, y, w, h) => {
      Cx.rect(x, y, w, h, { dashed: true, sw: 1.3 });
      const cx = x + w / 2, cy = y + h / 2 - (n.label ? 7 : 0);
      Cx.line(cx - 8, cy, cx + 8, cy, { sw: 1.8, single: true });
      Cx.line(cx, cy - 8, cx, cy + 8, { sw: 1.8, single: true });
      if (n.label) label(Cx, n.label, cx, cy + 26, { size: 13, anchor: 'middle' });
    },
  });

  REG('plus', {
    fit: true, iw: () => 26, h: () => 26,
    draw: (Cx, n, x, y) => { Cx.circle(x + 13, y + 13, 24, { sw: 1.4 }); Cx.line(x + 7, y + 13, x + 19, y + 13, { sw: 1.6, single: true }); Cx.line(x + 13, y + 7, x + 13, y + 19, { sw: 1.6, single: true }); },
  });

  REG('icons', {
    fit: true,
    iw: (n) => { const k = Array.isArray(n.items) ? n.items.length : (n.n ?? 4); return k * (n.d ?? 13) + (k - 1) * 9; },
    h: (n) => (n.d ?? 13) + 4,
    draw: (Cx, n, x, y) => {
      const items = Array.isArray(n.items) ? n.items : Array(n.n ?? 4).fill('');
      const d = n.d ?? 13;
      items.forEach((it, i) => {
        const cx = x + d / 2 + i * (d + 9);
        Cx.circle(cx, y + d / 2 + 2, d, { sw: 1.2, single: true });
        if (it) label(Cx, it, cx, y + d / 2 + 6, { size: Math.max(9, d * 0.7), anchor: 'middle' });
      });
    },
  });

  REG('nav', {
    h: () => 28,
    draw: (Cx, n, x, y, w) => {
      let lx = x;
      if (n.logo !== false) { C.logo.draw(Cx, {}, x, y + 2, 24); lx += 34; }
      const items = Array.isArray(n.items) ? n.items : Array(n.n ?? 3).fill('~');
      let rx = x + w;
      if (n.menu) { for (let i = 0; i < 3; i++) Cx.line(rx - 16, y + 8 + i * 5, rx, y + 8 + i * 5, { sw: 1.6, single: true }); rx -= 26; }
      if (n.cta) { const bw = n.cta === true ? 56 : Cx.measure(n.cta, 15) + 26; C.button.draw(Cx, { label: n.cta === true ? null : n.cta }, rx - bw, y + 3, bw, 22); rx -= bw + 14; }
      if (!n.menu || n.items) {
        const ws = items.map((s) => labelW(Cx, s, 14) * (isSq(s) ? 0.6 : 1));
        let cx = n.align === 'left' ? lx : rx - ws.reduce((a, b) => a + b + 16, -16);
        items.forEach((s, i) => { label(Cx, s, cx, y + 19, { size: 14, w: ws[i] }); cx += ws[i] + 16; });
      }
    },
  });

  REG('divider', {
    h: (n) => (n.label ? 22 : 10),
    draw: (Cx, n, x, y, w, h) => {
      const my = y + h / 2;
      if (!n.label) return Cx.line(x, my, x + w, my + Cx.j(1), { sw: n.sw ?? 1.2, dashed: n.dashed, ink: n.ink });
      const tw = Cx.measure(n.label, 13) + 16;
      Cx.line(x, my, x + (w - tw) / 2, my, { sw: 1.1, single: true });
      Cx.line(x + (w + tw) / 2, my, x + w, my, { sw: 1.1, single: true });
      label(Cx, n.label, x + w / 2, my + 5, { size: 13, anchor: 'middle' });
    },
  });

  REG('more', { // row of tick marks: "more content continues"
    h: () => 14,
    draw: (Cx, n, x, y, w) => { for (let px = x + 4; px < x + w - 4; px += 7) Cx.line(px, y + 3, px + Cx.j(1), y + 12, { sw: 1, single: true }); },
  });

  REG('table', {
    h: (n) => (n.rows ?? (n.cells ? n.cells.length : 4)) * 26,
    draw: (Cx, n, x, y, w, h) => {
      const cells = n.cells;
      const R = n.rows ?? (cells ? cells.length : 4), K = n.cols ?? (cells ? cells[0].length : 3), rh = h / R, cw = w / K;
      Cx.rect(x, y, w, h, { sw: 1.4 });
      for (let i = 1; i < R; i++) Cx.line(x, y + i * rh, x + w, y + i * rh, { sw: i === 1 && n.header !== false ? 1.6 : 0.9, single: true });
      for (let j = 1; j < K; j++) Cx.line(x + j * cw, y, x + j * cw, y + h, { sw: 0.9, single: true });
      for (let i = 0; i < R; i++) for (let j = 0; j < K; j++) {
        const s = cells ? cells[i]?.[j] : '~';
        if (s) label(Cx, s, x + j * cw + 7, y + i * rh + rh / 2 + 5, { size: 13, w: cw * 0.6 });
      }
    },
  });

  REG('list', { // mark: check | dash | dot | num | circle
    h: (n) => (Array.isArray(n.items) ? n.items.length : (n.n ?? 3)) * 22,
    draw: (Cx, n, x, y, w) => {
      const items = Array.isArray(n.items) ? n.items : Array(n.n ?? 3).fill('~~');
      items.forEach((s, i) => {
        const cy = y + i * 22 + 11, m = n.mark || 'check';
        if (m === 'check') Cx.path(`M${x},${cy - 1} L${x + 4},${cy + 5} L${x + 11},${cy - 7}`, { sw: 1.6, single: true, roughness: 0.5 });
        else if (m === 'dot') Cx.circle(x + 4, cy, 5, { solid: true, sw: 1 });
        else if (m === 'circle') Cx.circle(x + 5, cy, 11, { sw: 1.2 });
        else if (m === 'num') label(Cx, `${i + 1}.`, x, cy + 5, { size: 14 });
        else Cx.line(x, cy, x + 8, cy, { sw: 1.3, single: true });
        label(Cx, s, x + 20, cy + 5, { size: 14, w: isSq(s) ? Math.min(w - 24, sqW(s)) : undefined });
      });
    },
  });

  // Dropdown / popover menu. caret: top | none. dividers: [index after which to rule]
  REG('menu', {
    h: (n) => (n.items || []).length * 26 + 12 + (n.caret === 'none' ? 0 : 8),
    draw: (Cx, n, x, y, w, h) => {
      const top = n.caret === 'none' ? y : y + 8;
      Cx.rect(x, top, w, h - (top - y), { sw: 1.5, r: 6, fillPaper: true });
      if (n.caret !== 'none') { const cx = x + (n.caretX ?? w / 2); Cx.path(`M${cx - 8},${top + 1} L${cx},${y} L${cx + 8},${top + 1}`, { sw: 1.4, single: true, roughness: 0.4 }); }
      (n.items || []).forEach((s, i) => {
        label(Cx, s, x + 14, top + 6 + i * 26 + 18, { size: 15 });
        if ((n.dividers || []).includes(i)) Cx.line(x + 4, top + 6 + (i + 1) * 26 + 1, x + w - 4, top + 6 + (i + 1) * 26 + 1, { sw: 1.1, single: true });
      });
    },
  });
  C.popover = C.menu;

  REG('badge', {
    fit: true, iw: (n, Cx) => labelW(Cx, n.label || 'new', 12) + 14, h: () => 20,
    draw: (Cx, n, x, y, w, h) => { Cx.rect(x, y, w, h, { r: 9, sw: 1.2, ink: n.ink }); label(Cx, n.label || 'new', x + w / 2, y + 14, { size: 12, anchor: 'middle', ink: n.ink }); },
  });

  REG('placeholder', { // labelled box: "map", "chart", "embed"
    h: (n) => n.h ?? 80,
    draw: (Cx, n, x, y, w, h) => { Cx.rect(x, y, w, h, { sw: 1.4, dashed: n.dashed }); label(Cx, n.label || '~', x + w / 2, y + h / 2 + 6, { size: 15, anchor: 'middle' }); },
  });

  REG('chart', {
    h: (n) => n.h ?? 90,
    draw: (Cx, n, x, y, w, h) => {
      Cx.line(x, y, x, y + h, { sw: 1.3, single: true }); Cx.line(x, y + h, x + w, y + h, { sw: 1.3, single: true });
      const bars = n.bars || [0.4, 0.7, 0.5, 0.9, 0.6], bw = (w - 10) / bars.length;
      if (n.kind === 'line') Cx.curve(bars.map((v, i) => [x + 8 + i * bw + bw / 2, y + h - v * (h - 6)]), { sw: 1.6 });
      else bars.forEach((v, i) => Cx.rect(x + 8 + i * bw, y + h - v * (h - 6), bw * 0.6, v * (h - 6), { sw: 1.2, hatch: i === n.highlight }));
    },
  });

  REG('cursor', {
    fit: true, iw: () => 16, h: () => 22,
    draw: (Cx, n, x, y) => Cx.path(`M${x},${y} L${x},${y + 17} L${x + 4.5},${y + 13} L${x + 8},${y + 21} L${x + 11},${y + 19.5} L${x + 7.5},${y + 12} L${x + 13},${y + 12} Z`, { sw: 1.3, fillPaper: true, roughness: 0.5 }),
  });

  REG('burger', { // hamburger menu icon
    fit: true, iw: (n) => n.d ?? 18, h: (n) => Math.round((n.d ?? 18) * 0.8),
    draw: (Cx, n, x, y, w, h) => { for (let i = 0; i < 3; i++) Cx.line(x, y + (h * i) / 2, x + w, y + (h * i) / 2, { sw: 1.6, single: true }); },
  });

  REG('spacer', { h: (n) => n.h ?? 10, draw: () => {} });

  CSI.components = C;
  CSI.label = label;
  CSI.isSq = isSq;
})();
