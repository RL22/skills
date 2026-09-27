// Diagram components: tree (sitemap), legend (numbered footnotes), journey (customer journey map).
// Like every component: h()/iw() are pure (measurement only), draw() consumes the RNG.
(function () {
  const T = CSI.tokens;
  const C = CSI.components;
  const label = CSI.label;

  function wrap(Cx, s, size, maxW, font) {
    const out = [];
    for (const para of String(s ?? '').split('\n')) {
      let line = '';
      for (const w of para.split(/\s+/).filter(Boolean)) {
        const t = line ? `${line} ${w}` : w;
        if (line && Cx.measure(t, size, font) > maxW) { out.push(line); line = w; } else line = t;
      }
      out.push(line);
    }
    return out;
  }

  // Filled numbered disc — the badge that ties a thumbnail to a legend entry.
  CSI.badge = function (Cx, cx, cy, n, ink = 'red', d = 22) {
    Cx.circle(cx, cy, d, { solid: true, ink, sw: 1 });
    Cx.text(cx, cy + d * 0.26, String(n), { size: d * 0.62, anchor: 'middle', ink: Cx.paper.bg, tilt: 0, jitter: false });
  };

  // Orthogonal connector through pts, arrowhead on the last segment, optional origin dot.
  CSI.elbow = function (Cx, pts, o = {}) {
    for (let i = 0; i < pts.length - 1; i++) {
      const [a, b] = [pts[i], pts[i + 1]];
      if (Math.hypot(b[0] - a[0], b[1] - a[1]) < 1) continue;
      Cx.line(a[0], a[1], b[0], b[1], { sw: o.sw ?? 1.3, ink: o.ink, dashed: o.dashed, roughness: 0.6, single: true });
    }
    if (o.dot) Cx.circle(pts[0][0], pts[0][1], 5, { solid: true, ink: o.ink, sw: 1 });
    if (o.head !== false) {
      const [a, b] = pts.slice(-2);
      Cx.arrowhead(b[0], b[1], Math.atan2(b[1] - a[1], b[0] - a[0]), { ink: o.ink, len: 8, sw: 1.3 });
    }
  };

  // ---------- tree (sitemap) ----------
  // { type:'tree', root:{ id, label, template?, badge?, dashed?, children:[…] }, nodeW:120, nodeH:156, gapX:40, gapY:50 }
  // Level 1 fans out in a row under the root; each level-1 column stacks its children on a rail;
  // deeper nodes sit to the right of their parent on the same row.
  function layoutTree(n) {
    const W = n.nodeW ?? 120, H = n.nodeH ?? Math.round(W * 1.3), gx = n.gapX ?? 40, gy = n.gapY ?? 50, ind = 22, rowGap = gy * 0.7;
    if (!n.root) throw new Error('tree needs a root node');
    const boxes = [], links = [];
    let maxX = W, maxY = H;
    // deeper levels: first child continues right on the parent's row, later siblings drop to new rows
    const place = (node, x, y) => {
      boxes.push({ node, x, y });
      maxX = Math.max(maxX, x + W); maxY = Math.max(maxY, y + H);
      let bottom = y + H;
      (node.children || []).forEach((ch, i) => {
        const cy = i === 0 ? y : bottom + rowGap;
        links.push({ kind: i === 0 ? 'side' : 'drop', from: node, to: ch });
        bottom = Math.max(bottom, place(ch, x + W + gx * 0.8, cy));
      });
      return bottom;
    };
    boxes.push({ node: n.root, x: 0, y: 0 });
    const y1 = H + gy;
    let colX = 0;
    for (const c of n.root.children || []) {
      boxes.push({ node: c, x: colX, y: y1 });
      links.push({ kind: 'bus', from: n.root, to: c });
      let rowY = y1 + H + rowGap;
      const colStart = maxX;
      maxX = Math.max(maxX, colX + W);
      for (const g of c.children || []) {
        links.push({ kind: 'rail', from: c, to: g });
        rowY = place(g, colX + ind, rowY) + rowGap;
      }
      maxY = Math.max(maxY, rowY - rowGap);
      colX = Math.max(colX + W, maxX) + gx;
      void colStart;
    }
    return { W, H, boxes, links, w: maxX, h: maxY };
  }

  C.tree = {
    fit: true,
    iw: (n) => layoutTree(n).w,
    h: (n) => layoutTree(n).h,
    draw: (Cx, n, x, y) => {
      const L = layoutTree(n);
      const pos = new Map();
      for (const b of L.boxes) {
        const nd = b.node, bx = x + b.x, by = y + b.y;
        pos.set(nd, { x: bx, y: by });
        if (nd.template) C.page.draw(Cx, { id: nd.id, template: nd.template, label: nd.label, pad: 7 }, bx, by, L.W, L.H);
        else C.screen.draw(Cx, { id: nd.id, dashed: nd.dashed, pad: 8, gap: 7, children: [{ type: 'spacer', h: 14 }, { type: 'squiggle', lines: 3 }] }, bx, by, L.W, L.H);
        if (!nd.template) label(Cx, nd.label ?? '', bx + L.W / 2, by + 20, { size: 13, anchor: 'middle' });
        if (nd.badge != null) CSI.badge(Cx, bx + L.W - 2, by + 2, nd.badge, n.badgeInk ?? 'red');
        Cx.register(nd.id, { x: bx, y: by, w: L.W, h: L.H });
      }
      const busY = y + L.H + (n.gapY ?? 50) / 2;
      for (const k of L.links) {
        const a = pos.get(k.from), b = pos.get(k.to), o = { dashed: k.to.dashed, ink: n.ink };
        if (k.kind === 'bus') CSI.elbow(Cx, [[a.x + L.W / 2, a.y + L.H], [a.x + L.W / 2, busY], [b.x + L.W / 2, busY], [b.x + L.W / 2, b.y - 2]], { ...o, head: true });
        else if (k.kind === 'rail') CSI.elbow(Cx, [[a.x + 8, a.y + L.H], [a.x + 8, b.y + L.H / 2], [b.x - 2, b.y + L.H / 2]], { ...o, dot: true });
        else if (k.kind === 'side') CSI.elbow(Cx, [[a.x + L.W, a.y + L.H / 2], [b.x - 2, b.y + L.H / 2]], { ...o, dot: true });
        else { const mx = a.x + L.W + (b.x - a.x - L.W) / 2; CSI.elbow(Cx, [[a.x + L.W, a.y + L.H / 2], [mx, a.y + L.H / 2], [mx, b.y + L.H / 2], [b.x - 2, b.y + L.H / 2]], { ...o, dot: true }); }
      }
    },
  };

  // ---------- legend (numbered footnotes) ----------
  // { type:'legend', items:['text', {n:4, text:'…'}], cols:4, ink:'red' }
  function legendRows(Cx, n, w) {
    const cols = n.cols ?? 4, gap = 24;
    if (!Number.isInteger(cols) || cols < 1) throw new Error(`legend.cols must be a positive integer (got ${JSON.stringify(n.cols)})`);
    const cw = (w - gap * (cols - 1)) / cols, size = n.size ?? 17;
    const items = (n.items || []).map((it, i) => (typeof it === 'string' ? { n: i + 1, text: it } : { n: it.n ?? i + 1, ...it }));
    const cells = items.map((it) => ({ ...it, lines: wrap(Cx, it.text, size, cw - 34, 'note') }));
    const rows = [];
    for (let i = 0; i < cells.length; i += cols) rows.push(cells.slice(i, i + cols));
    const lh = size * 1.05;
    return { cols, gap, cw, size, lh, rows, h: rows.reduce((a, r) => a + Math.max(...r.map((c) => Math.max(26, c.lines.length * lh))) + 14, -14) };
  }
  C.legend = {
    h: (n, w, Cx) => Math.max(0, legendRows(Cx, n, w).h),
    draw: (Cx, n, x, y, w) => {
      const L = legendRows(Cx, n, w);
      let cy = y;
      for (const row of L.rows) {
        row.forEach((c, j) => {
          const cx = x + j * (L.cw + L.gap);
          CSI.badge(Cx, cx + 11, cy + 11, c.n, n.ink ?? 'red');
          c.lines.forEach((l, k) => Cx.text(cx + 32, cy + L.size * 0.9 + k * L.lh, l, { size: L.size, font: 'note', ink: 'note' }));
        });
        cy += Math.max(...row.map((c) => Math.max(26, c.lines.length * L.lh))) + 14;
      }
    },
  };

  // ---------- journey (customer journey map) ----------
  // { type:'journey', w:1100, phases:[{ title, actions:[…], points:[{ score:-2..2, touch:'email', note }], opportunities:[…] }],
  //   touchpoints:['Web','Email',…] (legend chips), rows: ['phases','actions','experience','opportunities'] }
  function journeyLayout(Cx, n, w) {
    if (!Array.isArray(n.phases) || !n.phases.length) throw new Error('journey needs at least one phase');
    const labW = n.labelW ?? 110, ph = n.phases, pw = (w - labW) / ph.length;
    const lh = 20;
    const aRows = Math.max(1, ...ph.map((p) => (p.actions || []).length));
    const oRows = Math.max(0, ...ph.map((p) => (p.opportunities || []).length));
    const rows = n.rows || [...(n.meta ? ['overview'] : []), 'phases', 'actions', 'experience', 'opportunities'];
    const hOf = { overview: n.meta ? 58 : 0, phases: 36, actions: aRows * lh + 18, experience: n.experienceH ?? 230, opportunities: oRows ? oRows * 22 + 16 : 0 };
    let yy = 0;
    const band = {};
    for (const r of rows) { band[r] = { y: yy, h: hOf[r] }; yy += hOf[r]; }
    return { labW, pw, band, rows, h: yy, lh };
  }
  function face(Cx, cx, cy, mood) {
    Cx.circle(cx, cy, 18, { sw: 1.2, single: true });
    Cx.circle(cx - 3.5, cy - 2.5, 2, { solid: true, sw: 0.6 });
    Cx.circle(cx + 3.5, cy - 2.5, 2, { solid: true, sw: 0.6 });
    const m = mood > 0 ? `M${cx - 5},${cy + 2} Q${cx},${cy + 7} ${cx + 5},${cy + 2}` : mood < 0 ? `M${cx - 5},${cy + 6} Q${cx},${cy + 1} ${cx + 5},${cy + 6}` : `M${cx - 5},${cy + 4} L${cx + 5},${cy + 4}`;
    Cx.path(m, { sw: 1.2, single: true, roughness: 0.3 });
  }
  C.journey = {
    h: (n, w, Cx) => journeyLayout(Cx, n, w).h,
    draw: (Cx, n, x, y, w, h) => {
      const L = journeyLayout(Cx, n, w), ph = n.phases || [];
      const X0 = x + L.labW;
      // row labels + row rules
      L.rows.forEach((r) => {
        const b = L.band[r];
        if (!b.h) return;
        Cx.text(x, y + b.y + Math.min(r === 'experience' ? 22 : 24, b.h / 2 + 6), n.labels?.[r] ?? r[0].toUpperCase() + r.slice(1), { size: 15 });
        Cx.line(X0, y + b.y + b.h, x + w, y + b.y + b.h, { sw: 0.9, single: true, ink: 'note' });
      });
      // overview: persona / scenario / timeline …
      if (L.band.overview && n.meta) {
        const entries = Object.entries(n.meta), cw = (w - L.labW) / entries.length;
        entries.forEach(([k, v], i) => {
          Cx.text(X0 + i * cw, y + L.band.overview.y + 16, k.toUpperCase(), { size: 11, ink: 'note' });
          label(Cx, String(v), X0 + i * cw, y + L.band.overview.y + 38, { size: 15, w: cw - 16 });
        });
      }
      // phase columns
      ph.forEach((p, i) => {
        const px = X0 + i * L.pw;
        if (i) Cx.line(px, y + (L.band.overview?.h ?? 0), px, y + h, { sw: 0.9, dashed: true, ink: 'note' });
        const B = L.band;
        if (B.phases) {
          Cx.rect(px + 3, y + B.phases.y + 3, L.pw - 6, B.phases.h - 6, { hatch: i === (n.highlight ?? -1), sw: 1.4, r: 4 });
          const f = { size: 15 };
          label(Cx, p.title ?? `Phase ${i + 1}`, px + L.pw / 2, y + B.phases.y + B.phases.h / 2 + 5, { ...f, anchor: 'middle', halo: i === n.highlight });
        }
        if (B.actions) (p.actions || []).forEach((a, k) => {
          const ay = y + B.actions.y + 9 + k * L.lh;
          Cx.text(px + 10, ay + 13, `${k + 1 + ph.slice(0, i).reduce((s, q) => s + (q.actions || []).length, 0)}`, { size: 12, ink: 'note' });
          label(Cx, a, px + 30, ay + 13, { size: 13, w: Math.min(L.pw - 44, 120) });
        });
        if (B.opportunities) (p.opportunities || []).forEach((o, k) => {
          const oy = y + B.opportunities.y + 10 + k * 22;
          Cx.path(`M${px + 10},${oy + 6} L${px + 14},${oy + 11} L${px + 21},${oy + 2}`, { sw: 1.4, single: true, roughness: 0.4 });
          label(Cx, o, px + 30, oy + 11, { size: 13, w: Math.min(L.pw - 44, 160) });
        });
      });
      // experience curve
      const E = L.band.experience;
      if (E) {
        const top = y + E.y + 46, bot = y + E.y + E.h - 26, mid = (top + bot) / 2, fx = X0 - 18;
        face(Cx, fx, top, 1); face(Cx, fx, mid, 0); face(Cx, fx, bot, -1);
        Cx.line(X0, mid, x + w, mid, { sw: 0.8, dashed: true, ink: 'note' });
        const pts = [];
        ph.forEach((p, i) => {
          const list = p.points || [];
          list.forEach((pt, k) => pts.push({ ...pt, x: X0 + i * L.pw + L.pw * (k + 1) / (list.length + 1), y: mid - (Math.max(-2, Math.min(2, pt.score ?? 0)) / 2) * (mid - top) }));
        });
        if (pts.length) Cx.curve([[X0 + 4, pts[0].y], ...pts.map((p) => [p.x, p.y]), [x + w - 4, pts[pts.length - 1].y]], { sw: 1.8, roughness: 0.5, single: true });
        const cardW = Math.min(150, L.pw * 0.8);
        pts.forEach((p, k) => {
          if (p.note) {
            const ls = wrap(Cx, p.note, 13, cardW - 12, 'hand');
            const ch = ls.length * 16 + 10, above = (p.side ?? (k % 2 ? 'below' : 'above')) === 'above';
            const cy = above ? Math.max(y + E.y + 6, p.y - 26 - ch) : Math.min(y + E.y + E.h - ch - 4, p.y + 26);
            const cx = Math.max(X0 + 4, Math.min(p.x - cardW / 2, x + w - cardW - 4));
            Cx.line(p.x, above ? cy + ch : cy, p.x, p.y, { sw: 0.9, dashed: true, ink: 'note', single: true });
            Cx.rect(cx, cy, cardW, ch, { sw: 1.1, r: 4, fillPaper: true });
            ls.forEach((l, j) => Cx.text(cx + 6, cy + 18 + j * 16, l, { size: 13 }));
          }
          Cx.circle(p.x, p.y, 16, { sw: 1.3, fillPaper: true });
          if (p.touch) Cx.text(p.x, p.y + 4, String(p.touch)[0].toUpperCase(), { size: 11, anchor: 'middle', jitter: false });
        });
        // touchpoint key: one chip per distinct channel, top-left of the band
        const touches = [...new Set(pts.map((p) => p.touch).filter(Boolean))];
        let kx = X0 + 8;
        touches.forEach((t) => {
          Cx.circle(kx + 7, y + E.y + 14, 14, { sw: 1.1, fillPaper: true });
          Cx.text(kx + 7, y + E.y + 18, String(t)[0].toUpperCase(), { size: 10, anchor: 'middle', jitter: false });
          kx += 20 + Cx.text(kx + 18, y + E.y + 19, String(t), { size: 12, ink: 'note' }) + 8;
        });
      }
    },
  };
})();
