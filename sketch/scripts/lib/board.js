// Board = paper + placed items + annotations (arrows, notes, strikes, vs, steps).
(function () {
  const T = CSI.tokens;
  const comps = CSI.components;
  const ANNOT = new Set(['arrow', 'note', 'strike', 'vs', 'step', 'badge']);
  const FULLROW = new Set(['heading', 'bullets', 'text', 'legend', 'journey', 'tree']);

  CSI.resolveW = (w, avail) => (typeof w === 'string' && w.endsWith('%') ? (avail * parseFloat(w)) / 100 : Number(w));

  CSI.measureNode = function (C, node, availW) {
    const d = comps[node.type];
    if (!d) throw new Error(`unknown component type "${node.type}"`);
    const w = node.w != null ? CSI.resolveW(node.w, availW)
      : d.iw && (node.fit ?? d.fit) ? Math.min(d.iw(node, C), availW) : availW;
    return { w, h: node.h ?? d.h(node, w, C) };
  };

  CSI.placeNode = function (C, node, x, y, availW) {
    const m = CSI.measureNode(C, node, availW);
    const px = node.align === 'center' ? x + (availW - m.w) / 2 : node.align === 'right' ? x + availW - m.w : x;
    comps[node.type].draw(C, node, px, y, m.w, m.h);
    if (node.selected) C.rect(px - 5, y - 5, m.w + 10, m.h + 10, { dashed: true, sw: 1.1 });
    if (node.cursor) comps.cursor.draw(C, {}, px + m.w * 0.7, y + m.h * 0.6);
    C.register(node.id, { x: px, y, w: m.w, h: m.h });
    return m;
  };

  // "id", "id.right", "id@0.3,0.8" or [x, y]
  function resolvePoint(C, ref) {
    if (Array.isArray(ref)) return { pt: ref, box: null };
    const [idPart, rel] = String(ref).split('@');
    const [id, side] = idPart.split('.');
    const box = C.boxes[id];
    if (!box) throw new Error(`annotation references unknown id "${id}"`);
    if (rel) { const [fx, fy] = rel.split(',').map(Number); return { pt: [box.x + box.w * fx, box.y + box.h * fy], box: null }; }
    return { box, side };
  }
  const center = (b) => [b.x + b.w / 2, b.y + b.h / 2];
  function edge(b, side, pad = 7) {
    return { right: [b.x + b.w + pad, b.y + b.h / 2], left: [b.x - pad, b.y + b.h / 2], top: [b.x + b.w / 2, b.y - pad], bottom: [b.x + b.w / 2, b.y + b.h + pad] }[side];
  }
  function autoSide(a, bc) {
    const ac = center(a), dx = bc[0] - ac[0], dy = bc[1] - ac[1];
    // prefer horizontal unless clearly vertical (flows read left→right)
    if (Math.abs(dx) >= Math.abs(dy) * 0.6) return dx > 0 ? 'right' : 'left';
    return dy > 0 ? 'bottom' : 'top';
  }
  function endpoints(C, from, to) {
    const A = resolvePoint(C, from), B = resolvePoint(C, to);
    const bc = B.box ? center(B.box) : B.pt, ac = A.box ? center(A.box) : A.pt;
    const p0 = A.box ? edge(A.box, A.side || autoSide(A.box, bc)) : A.pt;
    const p1 = B.box ? edge(B.box, B.side || autoSide(B.box, p0)) : B.pt;
    return [p0, p1];
  }
  function bezier(p0, p1, bend) {
    const mx = (p0[0] + p1[0]) / 2, my = (p0[1] + p1[1]) / 2;
    const dx = p1[0] - p0[0], dy = p1[1] - p0[1], len = Math.hypot(dx, dy) || 1;
    const c = [mx - (dy / len) * bend * len, my + (dx / len) * bend * len];
    const pts = [];
    for (let i = 0; i <= 14; i++) { const t = i / 14, u = 1 - t; pts.push([u * u * p0[0] + 2 * u * t * c[0] + t * t * p1[0], u * u * p0[1] + 2 * u * t * c[1] + t * t * p1[1]]); }
    return pts;
  }

  function drawArrow(C, a) {
    const [p0, p1] = endpoints(C, a.from, a.to);
    if (a.route === 'elbow') { // orthogonal: bend at the midpoint of the dominant axis
      const horiz = Math.abs(p1[0] - p0[0]) >= Math.abs(p1[1] - p0[1]);
      const m = horiz ? (p0[0] + p1[0]) / 2 : (p0[1] + p1[1]) / 2;
      const pts = horiz ? [p0, [m, p0[1]], [m, p1[1]], p1] : [p0, [p0[0], m], [p1[0], m], p1];
      CSI.elbow(C, pts, { ink: a.ink, dashed: a.dashed, dot: a.dot ?? true });
      if (a.label) CSI.label(C, a.label, (p0[0] + p1[0]) / 2, (horiz ? Math.min(p0[1], p1[1]) : m) - 8, { font: 'note', size: T.size.note - 2, ink: a.ink || 'note', anchor: 'middle' });
      return;
    }
    const pts = bezier(p0, p1, a.bend ?? -0.18);
    C.curve(pts, { sw: a.sw ?? 1.5, ink: a.ink, dashed: a.dashed, roughness: 0.7, single: true });
    const n = pts.length;
    C.arrowhead(p1[0], p1[1], Math.atan2(pts[n - 1][1] - pts[n - 3][1], pts[n - 1][0] - pts[n - 3][0]), { ink: a.ink });
    if (a.label) {
      const m = pts[7];
      CSI.label(C, a.label, m[0], m[1] - 14, { font: 'note', size: T.size.note - 2, ink: a.ink || 'note', anchor: 'middle' });
    }
  }

  function drawNote(C, n) {
    const size = n.size ?? T.size.note, font = n.font || 'note', ink = n.ink || 'note';
    const ls = String(n.text).split('\n'), lh = size * 1.05;
    const tw = Math.max(...ls.map((l) => C.measure(l, size, font)));
    const th = ls.length * lh;
    let x = n.x, y = n.y;
    if (x == null) {
      const b = C.boxes[n.near || String(n.to).split(/[.@]/)[0]];
      if (!b) throw new Error(`note "${n.text}" needs x/y or a valid near/to id`);
      const off = n.offset ?? 36, side = n.side || 'right';
      if (side === 'right') { x = b.x + b.w + off; y = b.y + (n.fy ?? 0.3) * b.h - th / 2; }
      else if (side === 'left') { x = b.x - off - tw; y = b.y + (n.fy ?? 0.3) * b.h - th / 2; }
      else if (side === 'top') { x = b.x + (n.fx ?? 0.5) * b.w - tw / 2; y = b.y - off - th; }
      else { x = b.x + (n.fx ?? 0.5) * b.w - tw / 2; y = b.y + b.h + off; }
    }
    ls.forEach((l, i) => C.text(x, y + size * 0.85 + i * lh, l, { size, font, ink, tilt: 1.5 }));
    if (n.underline) C.underline(x, y + th + 3, tw, { ink });
    const box = { x, y, w: tw, h: th };
    C.register(n.id, box);
    if (n.to) {
      const T2 = resolvePoint(C, n.to);
      const nc = center(box);
      const tp = T2.box ? (T2.side ? edge(T2.box, T2.side, 3) : clampTo(T2.box, nc)) : T2.pt;
      const sp = clampTo({ x: x - 5, y: y - 3, w: tw + 10, h: th + 6 }, tp);
      const pts = bezier(sp, tp, n.bend ?? 0.12);
      C.curve(pts, { sw: 1.3, ink, roughness: 0.5, single: true });
      if (n.arrow !== false) C.arrowhead(tp[0], tp[1], Math.atan2(pts[14][1] - pts[12][1], pts[14][0] - pts[12][0]), { ink, len: 8, sw: 1.1 });
    }
  }
  function clampTo(b, p) { // nearest point on box edge toward p
    const c = center(b), dx = p[0] - c[0], dy = p[1] - c[1];
    const sx = dx ? (b.w / 2) / Math.abs(dx) : Infinity, sy = dy ? (b.h / 2) / Math.abs(dy) : Infinity;
    const s = Math.min(sx, sy, 1);
    return [c[0] + dx * s, c[1] + dy * s];
  }

  function drawStrike(C, s) {
    const b = C.boxes[s.target];
    if (!b) throw new Error(`strike references unknown id "${s.target}"`);
    const o = 10;
    C.line(b.x - o, b.y - o, b.x + b.w + o, b.y + b.h + o, { sw: 2.2, single: true, roughness: 0.8, ink: s.ink });
    C.line(b.x + b.w + o, b.y - o, b.x - o, b.y + b.h + o, { sw: 2.2, single: true, roughness: 0.8, ink: s.ink });
    if (s.verdict) {
      const tw = C.measure(s.verdict, 19);
      const x = b.x + b.w / 2 - tw / 2, y = b.y + b.h + o + 28;
      C.text(x, y, s.verdict, { size: 19, ink: s.ink });
      C.underline(x, y + 6, tw, { ink: s.ink });
    }
  }

  function drawVs(C, v) {
    let x = v.x, y = v.y;
    if (v.between) {
      const [a, b] = v.between.map((id) => C.boxes[id]);
      if (!a || !b) throw new Error(`vs references unknown id in ${v.between}`);
      x = (a.x + a.w + b.x) / 2; y = Math.min(a.y + a.h / 2, b.y + b.h / 2);
    }
    C.text(x, y + 6, v.text || 'vs.', { size: 22, anchor: 'middle' });
  }

  function drawBadge(C, s) {
    const b = C.boxes[s.target];
    if (!b) throw new Error(`badge references unknown id "${s.target}"`);
    const corner = s.corner || 'tr';
    CSI.badge(C, corner.includes('r') ? b.x + b.w - 2 : b.x + 2, corner.includes('t') ? b.y + 2 : b.y + b.h - 2, s.n, s.ink ?? 'red');
  }

  function drawStep(C, s) {
    let x = s.x, y = s.y;
    if (s.target) { const b = C.boxes[s.target]; if (!b) throw new Error(`step references unknown id "${s.target}"`); x = b.x + b.w / 2; y = b.y - 24; }
    C.circle(x, y, 28, { sw: 1.5, ink: s.ink });
    C.text(x, y + 6, String(s.n), { size: 17, anchor: 'middle', ink: s.ink });
  }

  CSI.render = function (spec, svg) {
    const C = new CSI.Ctx(svg, spec);
    const margin = spec.margin ?? 44, gap = spec.gap ?? 90;
    const cur = { x: margin, y: margin, rowBottom: margin, rowHas: false };
    const items = spec.items || [];
    if (spec.title) {
      const size = 26;
      const tw = C.text(margin, margin + size, spec.title, { size });
      C.underline(margin, margin + size + 7, tw, { double: true });
      cur.y = cur.rowBottom = margin + size + (items.some((i) => i.type === 'step') ? 74 : 44);
    }
    for (const it of items) {
      if (ANNOT.has(it.type) && !(it.type === 'badge' && !it.target)) continue;
      if (!comps[it.type]) throw new Error(`unknown item type "${it.type}"`);
      const defW = it.type === 'screen' ? 260 : it.type === 'page' ? 150 : it.type === 'tree' ? 4000 : FULLROW.has(it.type) ? 700 : 240;
      const boardInner = (spec.width || 1200) - 2 * margin;
      const node = it.w != null ? { ...it, w: CSI.resolveW(it.w, boardInner) } : it; // resolve % once
      const m = CSI.measureNode(C, node, node.w ?? defW);
      let x, y, auto = false;
      if (it.x != null && it.y != null) { x = it.x; y = it.y; }
      else if (it.at) {
        const a = it.at, ref = C.boxes[a.rightOf || a.leftOf || a.below || a.above];
        if (!ref) throw new Error(`item "${it.id || it.type}" has 'at' pointing to an unknown/later id`);
        const g = a.gap ?? gap;
        if (a.rightOf) { x = ref.x + ref.w + g; y = ref.y; }
        else if (a.leftOf) { x = ref.x - g - m.w; y = ref.y; }
        else if (a.below) { x = ref.x; y = ref.y + ref.h + (a.gap ?? 60); }
        else { x = ref.x; y = ref.y - (a.gap ?? 60) - m.h; }
        x += a.dx ?? 0; y += a.dy ?? 0;
      } else if (FULLROW.has(it.type)) {
        y = cur.rowHas ? cur.rowBottom + gap * 0.6 : cur.y;
        x = margin;
        cur.y = cur.rowBottom = y + m.h + 26; cur.rowHas = false; cur.x = margin;
      } else {
        auto = true;
        if (it.newRow && cur.rowHas) { cur.y = cur.rowBottom + gap * 0.6; cur.rowHas = false; }
        x = cur.rowHas ? cur.x : margin; y = cur.y;
        if (spec.width && cur.rowHas && x + m.w > spec.width - margin) { x = margin; y = cur.y = cur.rowBottom + gap * 0.6; }
      }
      if (auto) { cur.x = x + m.w + gap; cur.rowBottom = Math.max(cur.rowBottom, y + m.h); cur.rowHas = true; }
      CSI.placeNode(C, node, x, y, m.w);
    }
    for (const it of items) {
      if (it.type === 'arrow') drawArrow(C, it);
      else if (it.type === 'note') drawNote(C, it);
      else if (it.type === 'strike') drawStrike(C, it);
      else if (it.type === 'vs') drawVs(C, it);
      else if (it.type === 'step') drawStep(C, it);
      else if (it.type === 'badge' && it.target) drawBadge(C, it);
    }
    const bs = C.bounds(C.gShapes), bt = C.bounds(C.gText);
    if (Math.min(bs.x, bt.x) < -2 || Math.min(bs.y, bt.y) < -2) C.warnings.push('content extends past the left/top edge (negative coordinates) and will be clipped — move it right/down');
    const contentW = Math.max(bs.x + bs.width, bt.x + bt.width) + margin;
    const contentH = Math.max(bs.y + bs.height, bt.y + bt.height) + margin;
    const W = Math.ceil(spec.width || contentW), H = Math.ceil(spec.height || contentH);
    if (spec.width && contentW > W + 4) C.warnings.push(`content (${Math.round(contentW)}px) wider than board width ${W}`);
    if (spec.height && contentH > H + 4) C.warnings.push(`content (${Math.round(contentH)}px) taller than board height ${H}`);
    C.drawPaper(W, H);
    svg.setAttribute('width', W); svg.setAttribute('height', H);
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    return { width: W, height: H, warnings: C.warnings, boxes: C.boxes };
  };
})();
