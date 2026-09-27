// Drawing context: seeded rough.js wrapper + handwritten text + paper.
// Determinism rule: only draw() paths consume the RNG; measure paths never do.
(function () {
  const T = CSI.tokens;
  const NS = 'http://www.w3.org/2000/svg';

  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  function el(tag, attrs, parent) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) if (attrs[k] != null) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  }

  function roundRectPath(x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    return `M${x + r},${y} H${x + w - r} Q${x + w},${y} ${x + w},${y + r} V${y + h - r} ` +
      `Q${x + w},${y + h} ${x + w - r},${y + h} H${x + r} Q${x},${y + h} ${x},${y + h - r} ` +
      `V${y + r} Q${x},${y} ${x + r},${y} Z`;
  }

  const measureCanvas = document.createElement('canvas').getContext('2d');

  class Ctx {
    constructor(svg, spec) {
      this.svg = svg;
      this.spec = spec;
      this.rc = rough.svg(svg);
      this.rng = mulberry32(spec.seed ?? 7);
      this.boxes = {};
      this.warnings = [];
      this.clipN = 0;
      this.paper = T.paper[spec.paper || 'grid'] || T.paper.grid;
      this.defs = el('defs', {}, svg);
      this.gPaper = el('g', {}, svg);
      const wobble = spec.wobble ?? 1;
      if (wobble > 0) {
        const f = el('filter', { id: 'wobble', x: '-2%', y: '-2%', width: '104%', height: '104%' }, this.defs);
        el('feTurbulence', { type: 'fractalNoise', baseFrequency: 0.03, numOctaves: 2, seed: (spec.seed ?? 7) % 1000 }, f);
        el('feDisplacementMap', { in: 'SourceGraphic', scale: wobble }, f);
      }
      this.gShapes = el('g', { filter: wobble > 0 ? 'url(#wobble)' : null }, svg);
      this.gText = el('g', {}, svg); // text never filtered — legibility
    }

    seed() { return 1 + Math.floor(this.rng() * 2 ** 30); }
    j(a) { return (this.rng() * 2 - 1) * a; }
    inkOf(n) { return n ? (T.ink[n] || n) : T.ink.primary; }

    opts(o = {}) {
      const ink = this.inkOf(o.ink);
      const r = {
        seed: this.seed(), stroke: ink, strokeWidth: o.sw ?? T.stroke.detail,
        roughness: o.roughness ?? T.rough.roughness, bowing: o.bowing ?? T.rough.bowing,
        disableMultiStroke: o.single ?? false,
      };
      if (o.dashed) { r.strokeLineDash = [7, 6]; r.disableMultiStroke = true; }
      if (o.hatch) Object.assign(r, {
        fill: ink, fillStyle: 'hachure', hachureGap: (o.hatchGap ?? T.hachure.gap) + this.j(0.8),
        hachureAngle: T.hachure.angle + this.j(7), fillWeight: T.hachure.weight + this.j(0.35),
        fillShapeRoughnessGain: 1.4,
      });
      if (o.solid) Object.assign(r, { fill: ink, fillStyle: 'solid' });
      if (o.fillPaper) Object.assign(r, { fill: this.paper.bg, fillStyle: 'solid' });
      return r;
    }

    add(n) { this.gShapes.appendChild(n); return n; }
    rect(x, y, w, h, o = {}) {
      if (o.r) return this.add(this.rc.path(roundRectPath(x, y, w, h, o.r), this.opts(o)));
      return this.add(this.rc.rectangle(x, y, w, h, this.opts(o)));
    }
    line(x1, y1, x2, y2, o = {}) { return this.add(this.rc.line(x1, y1, x2, y2, this.opts(o))); }
    circle(cx, cy, d, o = {}) { return this.add(this.rc.circle(cx, cy, d, this.opts(o))); }
    curve(pts, o = {}) { return this.add(this.rc.curve(pts, this.opts(o))); }
    path(d, o = {}) { return this.add(this.rc.path(d, this.opts(o))); }

    // Handwritten squiggle standing in for a line of copy. y = vertical centre.
    squiggle(x, y, w, o = {}) {
      if (w < 6) return;
      const amp = o.amp ?? 2.4, step = o.step ?? 6;
      const pts = [];
      let i = 0;
      for (let px = x; px < x + w; px += step * (0.55 + this.rng() * 0.9), i++)
        pts.push([px, y + (i % 2 ? amp : -amp) * (0.35 + this.rng() * 0.95) + Math.sin(i * 0.7) * 0.6]);
      pts.push([x + w, y + this.j(1)]);
      this.curve(pts, { sw: o.sw ?? (o.thick ? 2.1 : 1.3), roughness: 0.35, bowing: 0.5, single: true, ink: o.ink });
    }

    measure(str, size, font) {
      measureCanvas.font = `${size}px ${T.font[font || 'hand']}`;
      return measureCanvas.measureText(String(str)).width;
    }

    // y = baseline. Returns rendered width.
    text(x, y, str, o = {}) {
      const size = o.size ?? T.size.text;
      const font = o.font || 'hand';
      const dy = this.j(0.7), rot = this.j(o.tilt ?? 0.8);
      const t = el('text', {
        x, y: y + dy, 'font-family': T.font[font], 'font-size': size,
        fill: this.inkOf(o.ink), 'text-anchor': o.anchor || 'start',
        transform: `rotate(${rot.toFixed(2)} ${x} ${y})`,
      }, this.gText);
      const chars = [...String(str)];
      if (chars.length > 1 && o.jitter !== false) {
        const k = o.halo ? 0.5 : 1;
        t.setAttribute('rotate', chars.map(() => this.j(4 * k).toFixed(1)).join(' '));
        const dys = []; let acc = 0;
        for (let i = 0; i < chars.length; i++) { const d = this.j(0.9 * k) - acc * 0.5; acc += d; dys.push(d.toFixed(2)); }
        t.setAttribute('dy', dys.join(' '));
      }
      t.textContent = String(str);
      if (o.halo) { // separate underlay: per-glyph halos on one element would erase neighbouring glyphs
        const h = t.cloneNode(true);
        h.setAttribute('fill', 'none');
        h.setAttribute('stroke', this.paper.bg);
        h.setAttribute('stroke-width', o.haloW ?? 7);
        h.setAttribute('stroke-linejoin', 'round');
        t.parentNode.insertBefore(h, t);
      }
      return this.measure(str, size, font);
    }

    underline(x, y, w, o = {}) {
      this.line(x - 2, y, x + w + 4, y + this.j(1.5), { sw: o.sw ?? 1.6, ink: o.ink, roughness: 0.9 });
      if (o.double) this.line(x, y + 4, x + w + 2, y + 4 + this.j(1.5), { sw: 1.3, ink: o.ink, roughness: 0.9 });
    }

    arrowhead(x, y, angle, o = {}) {
      const len = o.len ?? 11, spread = 0.45;
      for (const s of [-1, 1]) {
        const a = angle + Math.PI - s * spread;
        this.line(x, y, x + Math.cos(a) * len, y + Math.sin(a) * len, { sw: o.sw ?? 1.5, ink: o.ink, roughness: 0.6, single: true });
      }
    }

    // Draw fn() with shapes and text clipped to the rect; warn when anything spilled past it.
    clip(x, y, w, h, fn, what = 'content') {
      const id = `clip${++this.clipN}`;
      const cp = el('clipPath', { id }, this.defs);
      el('rect', { x: x - 1, y: y - 1, width: w + 2, height: h + 2 }, cp);
      const [gs, gt] = [this.gShapes, this.gText];
      const rect = `${x},${y},${w},${h}`;
      this.gShapes = el('g', { 'clip-path': `url(#${id})`, 'data-clip': rect }, gs);
      this.gText = el('g', { 'clip-path': `url(#${id})`, 'data-clip': rect }, gt);
      try { fn(); } finally {
        const spill = [this.gShapes, this.gText].map((g) => g.getBBox()).some((b) => b.width && (b.x < x - 4 || b.y < y - 4 || b.x + b.width > x + w + 4 || b.y + b.height > y + h + 4));
        if (spill) this.warnings.push(`${what} spills outside its frame (clipped)`);
        this.gShapes = gs; this.gText = gt;
      }
    }

    // Visible bounds of a group: clipped subgroups count as their clip rect, not their raw geometry.
    bounds(g) {
      let x1 = Infinity, y1 = Infinity, x2 = -Infinity, y2 = -Infinity;
      const walk = (node) => {
        for (const c of node.children) {
          const clip = c.getAttribute && c.getAttribute('data-clip');
          let b;
          if (clip) { const [x, y, w, h] = clip.split(',').map(Number); b = { x, y, width: w, height: h }; }
          else if (c.tagName === 'g' && !c.getAttribute('filter')) { walk(c); continue; }
          else b = c.getBBox();
          if (!b.width && !b.height) continue;
          x1 = Math.min(x1, b.x); y1 = Math.min(y1, b.y); x2 = Math.max(x2, b.x + b.width); y2 = Math.max(y2, b.y + b.height);
        }
      };
      walk(g);
      return x1 === Infinity ? { x: 0, y: 0, width: 0, height: 0 } : { x: x1, y: y1, width: x2 - x1, height: y2 - y1 };
    }

    register(id, box) {
      if (!id) return;
      if (this.boxes[id]) this.warnings.push(`duplicate id "${id}"`);
      this.boxes[id] = box;
    }

    drawPaper(W, H) {
      const p = this.paper, g = this.gPaper;
      el('rect', { x: 0, y: 0, width: W, height: H, fill: p.bg }, g);
      if (p.grid) {
        const cell = p.cell, gl = el('g', { stroke: p.grid, 'stroke-width': 0.7 }, g);
        const off = this.j(cell / 2) + cell / 2;
        for (let x = off; x < W; x += cell) el('line', { x1: x, y1: 0, x2: x, y2: H, 'stroke-opacity': (0.3 + this.rng() * 0.25).toFixed(2) }, gl);
        for (let y = off; y < H; y += cell) el('line', { x1: 0, y1: y, x2: W, y2: y, 'stroke-opacity': (0.3 + this.rng() * 0.25).toFixed(2) }, gl);
      }
      // grain
      const f = el('filter', { id: 'grain', x: 0, y: 0, width: '100%', height: '100%' }, this.defs);
      el('feTurbulence', { type: 'fractalNoise', baseFrequency: 0.85, numOctaves: 2, seed: 3 }, f);
      el('feColorMatrix', { values: '0 0 0 0 0.35  0 0 0 0 0.3  0 0 0 0 0.2  0 0 0 0.09 0' }, f);
      el('rect', { x: 0, y: 0, width: W, height: H, filter: 'url(#grain)' }, g);
      const m = el('filter', { id: 'mottle', x: 0, y: 0, width: '100%', height: '100%' }, this.defs);
      el('feTurbulence', { type: 'fractalNoise', baseFrequency: 0.006, numOctaves: 3, seed: 11 }, m);
      el('feColorMatrix', { values: '0 0 0 0 0.45  0 0 0 0 0.38  0 0 0 0 0.2  0 0 0 0.16 -0.03' }, m);
      el('rect', { x: 0, y: 0, width: W, height: H, filter: 'url(#mottle)' }, g);
      // scan vignette
      const rg = el('radialGradient', { id: 'vig', cx: '50%', cy: '48%', r: '75%' }, this.defs);
      el('stop', { offset: '60%', 'stop-color': '#000', 'stop-opacity': 0 }, rg);
      el('stop', { offset: '100%', 'stop-color': '#5a4a20', 'stop-opacity': 0.08 }, rg);
      el('rect', { x: 0, y: 0, width: W, height: H, fill: 'url(#vig)' }, g);
    }
  }

  CSI.Ctx = Ctx;
  CSI.el = el;
})();
