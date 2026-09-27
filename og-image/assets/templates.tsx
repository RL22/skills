/**
 * Satori-safe OG image templates. Brand-agnostic: every color/type/spacing
 * value comes from `BrandTokens`, not a hardcoded default. See
 * references/design-system.md for the archetype catalog these implement,
 * and references/satori-constraints.md for the Satori constraints
 * that shaped this code (flex-only layout, no CSS grid, inline styles only,
 * `top/right/bottom/left` instead of the shorthand `inset`).
 *
 * Verified by actually rendering all three templates through `satori` +
 * `@resvg/resvg-js` at 1200x630 (not just `tsc --noEmit` — that passes even
 * when Satori throws at render time). See scripts/render-check.mjs.
 *
 * Usage (Next.js App Router):
 *   import { readFile } from "node:fs/promises";
 *   import { ImageResponse } from "next/og";
 *   import { TemplateCenteredHero, exampleTokens } from ".../templates";
 *
 *   export const size = { width: 1200, height: 630 };
 *   export const contentType = "image/png";
 *
 *   export default async function Image() {
 *     const [sg600, sg700] = await Promise.all([
 *       readFile("assets/fonts/SpaceGrotesk-600.ttf"),
 *       readFile("assets/fonts/SpaceGrotesk-700.ttf"),
 *     ]);
 *     return new ImageResponse(
 *       TemplateCenteredHero({ tokens: exampleTokens, eyebrow: "SPRINTZ", title: "Ship faster." }),
 *       {
 *         ...size,
 *         fonts: [
 *           // `name` is UNQUOTED here; BrandTokens.fontTitle is quoted for use
 *           // inside a CSS fontFamily string - the two are not interchangeable.
 *           { name: "Space Grotesk", data: sg600, weight: 600, style: "normal" },
 *           { name: "Space Grotesk", data: sg700, weight: 700, style: "normal" },
 *         ],
 *       }
 *     );
 *   }
 */

// ---------- determinism: fixed-seed PRNG, per programmatic-brand-assets skill ----------
// Never use Math.random() for motif placement/jitter - re-rendering the same
// props (including seed) must produce the same pixels.
export function mulberry32(seed: number) {
  return function next() {
    let t = (seed += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------- atoms: brand-agnostic token shape ----------
// A template receives tokens as a required prop, never a hardcoded default.
// `exampleTokens` below is a *working example* for this skill's own docs,
// not the templates' identity - swap it for the calling project's brand.
export type BrandTokens = {
  /** Six-digit hex only (e.g. "#090d16"). Motifs append an alpha suffix
   *  (e.g. `${color}40`) - rgb()/hsl()/named colors/3- or 8-digit hex will
   *  produce malformed CSS. Use `withAlpha()` below if a token needs a
   *  non-hex-friendly value. */
  bg: string;
  bgLight?: string;
  accentPrimary: string;
  textPrimary: string;
  textMuted: string;
  fontTitle: string;       // quoted family name for CSS, e.g. '"Space Grotesk"'
  fontMono?: string;       // for code/terminal archetypes, e.g. '"JetBrains Mono"'
  radiusCard: number;      // px, e.g. 16
  paddingCanvas: number;   // px, e.g. 64
  seed: number;            // determinism: same seed -> same motif placement, on every template
};

export const exampleTokens: BrandTokens = {
  bg: "#090d16",
  accentPrimary: "#6366f1",
  textPrimary: "#f8fafc",
  textMuted: "#94a3b8",
  fontTitle: '"Space Grotesk"',
  fontMono: '"JetBrains Mono"',
  radiusCard: 16,
  paddingCanvas: 64,
  seed: 42,
};

// Appends an alpha byte to a six-digit hex color. Throws on anything else,
// so a bad token fails loudly at call time instead of producing silently
// malformed CSS that Satori just ignores.
export function withAlpha(hex: string, alphaHex: string): string {
  if (!/^#[0-9a-fA-F]{6}$/.test(hex)) {
    throw new Error(`withAlpha expects a six-digit hex color, got "${hex}"`);
  }
  return `${hex}${alphaHex}`;
}

// ---------- motif atoms ----------
// Satori does not support the `inset` shorthand (confirmed by render-check.mjs:
// with `inset: 0` these motifs silently fail to cover the canvas). Use the
// four longhand edge properties instead.
const FULL_BLEED = { top: 0, right: 0, bottom: 0, left: 0 } as const;

// Radial spotlight glow, deterministic position offset from the seeded PRNG
// so a template can vary slightly between renders without going random.
function radialGlow(tokens: BrandTokens) {
  const rand = mulberry32(tokens.seed);
  const xOffset = 45 + rand() * 10; // 45-55%, stays near-centered
  return {
    position: "absolute" as const,
    ...FULL_BLEED,
    background: `radial-gradient(circle at ${xOffset}% 0%, ${withAlpha(tokens.accentPrimary, "40")} 0%, transparent 70%)`,
  };
}

// SVG grain data URI - breaks gradient banding at very low opacity, per
// design-system.md §3. Must declare viewBox or Satori throws
// `missing "viewBox"` at render time (confirmed by render-check.mjs).
const NOISE_OVERLAY_STYLE = {
  position: "absolute" as const,
  ...FULL_BLEED,
  opacity: 0.04,
  backgroundImage:
    "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100' height='100' filter='url(%23n)'/%3E%3C/svg%3E\")",
};

// Line grid (not the dot-grid from design-system.md §3 - verified by
// isolated render that Satori sizes an unqualified `radial-gradient(color
// 1px, transparent 1px)` to its farthest-corner default rather than the
// browser's closest-side default, so the "1px dot" trick collapses to a
// sub-pixel point and renders as nothing. Two crossed linear-gradients with
// hard 1px stops render correctly and are the line-grid variant
// design-system.md §3 already documents as an alternative motif).
// Seeded sub-pixel offset so every template that uses this actually
// consumes tokens.seed - previously only the radial glow did, despite all
// three templates claiming determinism.
function dotGridStyle(tokens: BrandTokens) {
  const rand = mulberry32(tokens.seed + 1); // +1: independent stream from radialGlow's
  const offsetPx = Math.floor(rand() * 40); // 0-39px, keeps the 40px grid pitch
  const line = `${withAlpha(tokens.textMuted, "33")} 1px, transparent 1px`;
  return {
    position: "absolute" as const,
    ...FULL_BLEED,
    backgroundImage: `linear-gradient(to right, ${line}), linear-gradient(to bottom, ${line})`,
    backgroundSize: "40px 40px",
    backgroundPosition: `${offsetPx}px ${offsetPx}px`,
  };
}

// ---------- molecules ----------
// Exported: advertised in SKILL.md as shared molecules, so callers can reuse
// them directly rather than only through the three full templates.
export type TitleBlockProps = {
  tokens: BrandTokens;
  eyebrow?: string;
  title: string;
  subtitle?: string;
  align?: "left" | "center";
  /** Truncates (with an ellipsis) rather than overflow - Satori does not
   *  support -webkit-line-clamp, so this is done by character budget instead
   *  of a real CSS line clamp. Matches design-system.md's documented
   *  maxTitleLines contract via an approximate chars-per-line conversion. */
  maxTitleLines?: number;
};

const CHARS_PER_LINE_AT: Record<number, number> = { 64: 18, 48: 24, 36: 32 };

export function TitleBlock({ tokens, eyebrow, title, subtitle, align = "left", maxTitleLines }: TitleBlockProps) {
  // Type-scale rule from design-system.md §4: short titles get the XL size,
  // longer ones step down so a template never has to hand-tune font size.
  // 64 (not 68/72) and 48/36 chosen so the family's actual max static weight
  // (700 - Space Grotesk ships no 800) still reads clearly at this size.
  const titleSize = title.length < 35 ? 64 : title.length < 70 ? 48 : 36;
  let displayTitle = title;
  if (maxTitleLines) {
    const budget = (CHARS_PER_LINE_AT[titleSize] ?? 24) * maxTitleLines;
    if (title.length > budget) displayTitle = title.slice(0, budget - 1).trimEnd() + "…";
  }
  const titleStyle: Record<string, string | number> = {
    fontSize: titleSize,
    fontWeight: 700,
    lineHeight: 1.1,
    letterSpacing: -1,
    color: tokens.textPrimary,
    fontFamily: tokens.fontTitle,
  };
  // Assign maxWidth only when centered - a bare `maxWidth: undefined` key
  // reaches Satori's layout engine and throws `Cannot read properties of
  // undefined (reading 'trim')` (confirmed by render-check.mjs). Omit the
  // key entirely rather than assign undefined to it.
  if (align === "center") titleStyle.maxWidth = 900;

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: align === "center" ? "center" : "flex-start",
        textAlign: align,
        gap: 16,
      }}
    >
      {eyebrow && (
        <div
          style={{
            fontSize: 15,
            fontWeight: 600,
            letterSpacing: 2,
            textTransform: "uppercase",
            color: tokens.accentPrimary,
          }}
        >
          {eyebrow}
        </div>
      )}
      <div style={titleStyle}>{displayTitle}</div>
      {subtitle && (
        <div style={{ fontSize: 22, lineHeight: 1.4, color: tokens.textMuted, maxWidth: 560 }}>
          {subtitle}
        </div>
      )}
    </div>
  );
}

export type StatMetricBoxProps = {
  tokens: BrandTokens;
  value: string;
  label: string;
  /** e.g. "+24%" - rendered as a small pill next to the value when present. */
  trend?: string;
};

export function StatMetricBox({ tokens, value, label, trend }: StatMetricBoxProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        width: 260,
        padding: 24,
        borderRadius: tokens.radiusCard,
        background: withAlpha(tokens.textPrimary, "0a"),
        border: `1px solid ${withAlpha(tokens.textPrimary, "1a")}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <div style={{ fontSize: 64, fontWeight: 700, letterSpacing: -2, color: tokens.textPrimary }}>
          {value}
        </div>
        {trend && (
          <div
            style={{
              fontSize: 14,
              fontWeight: 600,
              color: tokens.accentPrimary,
              padding: "2px 8px",
              borderRadius: 999,
              background: withAlpha(tokens.accentPrimary, "1f"),
            }}
          >
            {trend}
          </div>
        )}
      </div>
      <div style={{ fontSize: 15, fontWeight: 600, textTransform: "uppercase", color: tokens.textMuted }}>
        {label}
      </div>
    </div>
  );
}

// ---------- templates (full 1200x630 card presets) ----------
// design-system.md Archetype 2
export function TemplateCenteredHero(props: {
  tokens: BrandTokens;
  eyebrow?: string;
  title: string;
  subtitle?: string;
}) {
  const { tokens } = props;
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        position: "relative",
        background: tokens.bg,
        padding: tokens.paddingCanvas,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div style={radialGlow(tokens)} />
      <div style={NOISE_OVERLAY_STYLE} />
      <TitleBlock {...props} tokens={tokens} align="center" maxTitleLines={2} />
    </div>
  );
}

// design-system.md Archetype 1
export function TemplateSplitScreen(props: {
  tokens: BrandTokens;
  eyebrow?: string;
  title: string;
  subtitle?: string;
  visual?: React.ReactNode; // caller supplies the right-column mockup/graphic
}) {
  const { tokens, visual } = props;
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        position: "relative",
        background: tokens.bg,
        padding: tokens.paddingCanvas,
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <div style={dotGridStyle(tokens)} />
      <div style={{ display: "flex", width: "50%", position: "relative" }}>
        <TitleBlock {...props} tokens={tokens} align="left" maxTitleLines={3} />
      </div>
      <div
        style={{
          display: "flex",
          width: "45%",
          position: "relative",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {visual}
      </div>
    </div>
  );
}

// design-system.md Archetype 3. `stats` is documented (design-system.md §2,
// Archetype 3) as 1-4 entries in a 2x2-ish grid; each StatMetricBox is a
// fixed 260px so up to 2 sit per row inside the 560px container - this was
// previously left to flex-wrap auto-sizing, which doesn't reliably grid.
export function TemplateStatGrid(props: {
  tokens: BrandTokens;
  eyebrow?: string;
  title: string;
  subtitle?: string;
  stats: [
    { value: string; label: string; trend?: string },
    ...Array<{ value: string; label: string; trend?: string }>,
  ]; // enforced non-empty at the type level; runtime check below covers the 4-max
}) {
  const { tokens, stats } = props;
  if (stats.length > 4) {
    throw new Error(`TemplateStatGrid accepts 1-4 stats (design-system.md Archetype 3), got ${stats.length}`);
  }
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        position: "relative",
        background: tokens.bg,
        padding: tokens.paddingCanvas,
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <div style={dotGridStyle(tokens)} />
      <div style={{ display: "flex", width: 420, position: "relative" }}>
        <TitleBlock
          tokens={tokens}
          eyebrow={props.eyebrow}
          title={props.title}
          subtitle={props.subtitle}
          align="left"
          maxTitleLines={3}
        />
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 20, width: 560, position: "relative" }}>
        {stats.map((s) => (
          <StatMetricBox key={s.label} tokens={tokens} value={s.value} label={s.label} trend={s.trend} />
        ))}
      </div>
    </div>
  );
}

// ---------- additional molecules (archetypes 4-8) ----------

// design-system.md §2 Archetype 4. Three fixed macOS traffic-light colors are
// a real-world OS convention, not a brand token - they read as "browser
// chrome" specifically because they're NOT customized.
const MACOS_DOT_COLORS = ["#ff5f56", "#ffbd2e", "#27c93f"];

function WindowChrome({ tokens, url, children }: { tokens: BrandTokens; url?: string; children?: React.ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: 1072,
        height: 502,
        borderRadius: tokens.radiusCard,
        overflow: "hidden",
        background: withAlpha(tokens.textPrimary, "08"),
        border: `1px solid ${withAlpha(tokens.textPrimary, "1a")}`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          height: 40,
          padding: "0 16px",
          background: withAlpha(tokens.textPrimary, "0d"),
          borderBottom: `1px solid ${withAlpha(tokens.textPrimary, "14")}`,
        }}
      >
        <div style={{ display: "flex", gap: 8 }}>
          {MACOS_DOT_COLORS.map((c) => (
            <div key={c} style={{ display: "flex", width: 12, height: 12, borderRadius: 999, background: c }} />
          ))}
        </div>
        {url && (
          <div
            style={{
              display: "flex",
              fontSize: 14,
              fontFamily: tokens.fontMono ?? tokens.fontTitle,
              color: tokens.textMuted,
              padding: "4px 12px",
              borderRadius: 999,
              background: withAlpha(tokens.textPrimary, "0a"),
            }}
          >
            {url}
          </div>
        )}
      </div>
      <div style={{ display: "flex", flex: 1, position: "relative" }}>{children}</div>
    </div>
  );
}

/** One colored span of a code line. `color` defaults to `tokens.textMuted`
 *  if omitted - callers supply their own syntax-color mapping rather than
 *  the template hardcoding a specific IDE theme's palette. */
export type CodeToken = { text: string; color?: string };

function CodeWindow({ tokens, filename, lines }: { tokens: BrandTokens; filename?: string; lines: CodeToken[][] }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: 560,
        height: 420,
        borderRadius: tokens.radiusCard,
        overflow: "hidden",
        background: "#0d1117",
        border: `1px solid ${withAlpha(tokens.textPrimary, "14")}`,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 16,
          height: 38,
          padding: "0 16px",
          borderBottom: "1px solid #ffffff14",
        }}
      >
        <div style={{ display: "flex", gap: 8 }}>
          {MACOS_DOT_COLORS.map((c) => (
            <div key={c} style={{ display: "flex", width: 10, height: 10, borderRadius: 999, background: c }} />
          ))}
        </div>
        {filename && (
          <div style={{ display: "flex", fontSize: 13, fontFamily: tokens.fontMono ?? tokens.fontTitle, color: "#8b949e" }}>
            {filename}
          </div>
        )}
      </div>
      <div style={{ display: "flex", flexDirection: "column", padding: 24, gap: 6 }}>
        {lines.map((line, i) => (
          <div key={i} style={{ display: "flex", fontFamily: tokens.fontMono ?? tokens.fontTitle, fontSize: 18, lineHeight: 1.5 }}>
            <span style={{ color: "#484f58", width: 24 }}>{i + 1}</span>
            {line.map((tok, j) => (
              // whiteSpace: "pre" - without it, leading/trailing spaces inside
              // each token's text are collapsed at render time (confirmed by
              // render-check.mjs: "import { client } from" rendered as
              // "import{ client }from" with every token-boundary space
              // silently eaten). Standard fix for code/preformatted text.
              <span key={j} style={{ color: tok.color ?? tokens.textMuted, whiteSpace: "pre" }}>
                {tok.text}
              </span>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// design-system.md §2 Archetype 8. Distinct from TitleBlock's plain eyebrow
// text: this is a bordered pill, not inline uppercase text.
export function PillBadge({ tokens, children }: { tokens: BrandTokens; children: React.ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        fontSize: 13,
        fontWeight: 600,
        letterSpacing: 1,
        textTransform: "uppercase",
        color: tokens.textPrimary,
        padding: "6px 16px",
        borderRadius: 999,
        border: `1px solid ${withAlpha(tokens.textPrimary, "26")}`,
        background: withAlpha(tokens.textPrimary, "0a"),
      }}
    >
      {children}
    </div>
  );
}

// design-system.md §2 Archetype 7. No avatar image is fetched by default -
// remote image fetches inside ImageResponse risk the timeout/size failures
// documented in satori-constraints.md, so the safe default is a
// deterministic initial-letter avatar; pass `avatarDataUri` to override.
export type AuthorBylineProps = {
  tokens: BrandTokens;
  name: string;
  role?: string;
  avatarDataUri?: string;
};

export function AuthorByline({ tokens, name, role, avatarDataUri }: AuthorBylineProps) {
  const initial = name.trim().charAt(0).toUpperCase() || "?";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
      {avatarDataUri ? (
        <img
          src={avatarDataUri}
          width={64}
          height={64}
          style={{ borderRadius: 999, border: `2px solid ${withAlpha(tokens.accentPrimary, "66")}` }}
        />
      ) : (
        <div
          style={{
            display: "flex",
            width: 64,
            height: 64,
            borderRadius: 999,
            alignItems: "center",
            justifyContent: "center",
            fontSize: 26,
            fontWeight: 700,
            color: tokens.textPrimary,
            background: withAlpha(tokens.accentPrimary, "33"),
            border: `2px solid ${withAlpha(tokens.accentPrimary, "66")}`,
          }}
        >
          {initial}
        </div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <div style={{ fontSize: 20, fontWeight: 700, color: tokens.textPrimary }}>{name}</div>
        {role && <div style={{ fontSize: 16, color: tokens.textMuted }}>{role}</div>}
      </div>
    </div>
  );
}

// ---------- templates 4-8 ----------

// design-system.md Archetype 4
export function TemplateAppWindow(props: {
  tokens: BrandTokens;
  url?: string;
  visual?: React.ReactNode; // caller supplies the framed screenshot/UI content
}) {
  const { tokens, url, visual } = props;
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        position: "relative",
        background: tokens.bg,
        padding: tokens.paddingCanvas,
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <WindowChrome tokens={tokens} url={url}>
        {visual}
      </WindowChrome>
    </div>
  );
}

// design-system.md Archetype 5
export function TemplateCodeTerminal(props: {
  tokens: BrandTokens;
  eyebrow?: string;
  title: string;
  subtitle?: string;
  filename?: string;
  lines: CodeToken[][];
}) {
  const { tokens, filename, lines } = props;
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        position: "relative",
        background: tokens.bg,
        padding: tokens.paddingCanvas,
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <div style={{ display: "flex", width: 480, position: "relative" }}>
        <TitleBlock {...props} tokens={tokens} align="left" maxTitleLines={3} />
      </div>
      <CodeWindow tokens={tokens} filename={filename} lines={lines} />
    </div>
  );
}

// design-system.md Archetype 6. `backgroundImage` must be a data URI or an
// already-resized remote URL - see satori-constraints.md's asset-size
// warning; a full-resolution remote photo risks a render timeout.
export function TemplateFullPhoto(props: {
  tokens: BrandTokens;
  eyebrow?: string;
  title: string;
  subtitle?: string;
  backgroundImage: string;
  /** "vertical" = bottom-heavy scrim (title anchored low); "horizontal" =
   *  left-heavy scrim (title anchored left, image visible on the right). */
  scrimDirection?: "vertical" | "horizontal";
}) {
  const { tokens, backgroundImage, scrimDirection = "vertical" } = props;
  const scrim =
    scrimDirection === "vertical"
      ? "linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0.85) 100%)"
      : `linear-gradient(90deg, ${tokens.bg} 0%, ${tokens.bg} 40%, transparent 100%)`;
  return (
    <div style={{ width: "100%", height: "100%", display: "flex", position: "relative" }}>
      <img src={backgroundImage} width={1200} height={630} style={{ position: "absolute", ...FULL_BLEED, objectFit: "cover" }} />
      <div style={{ position: "absolute", ...FULL_BLEED, background: scrim }} />
      <div
        style={{
          display: "flex",
          position: "relative",
          width: "100%",
          height: "100%",
          padding: tokens.paddingCanvas,
          alignItems: scrimDirection === "vertical" ? "flex-end" : "center",
        }}
      >
        <TitleBlock
          {...props}
          tokens={{ ...tokens, textPrimary: "#ffffff", textMuted: "#e2e8f0" }}
          align="left"
          maxTitleLines={2}
        />
      </div>
    </div>
  );
}

// design-system.md Archetype 7
export function TemplateQuoteCard(props: {
  tokens: BrandTokens;
  quote: string;
  author: string;
  role?: string;
  avatarDataUri?: string;
}) {
  const { tokens, quote, author, role, avatarDataUri } = props;
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        position: "relative",
        background: tokens.bg,
        padding: tokens.paddingCanvas,
        justifyContent: "center",
        gap: 32,
      }}
    >
      <div style={{ display: "flex", fontSize: 100, lineHeight: 1, color: withAlpha(tokens.textPrimary, "26"), fontFamily: tokens.fontTitle }}>
        &ldquo;
      </div>
      <div style={{ display: "flex", fontSize: 32, lineHeight: 1.35, color: tokens.textPrimary, maxWidth: 980, marginTop: -60 }}>
        {quote}
      </div>
      <AuthorByline tokens={tokens} name={author} role={role} avatarDataUri={avatarDataUri} />
    </div>
  );
}

// design-system.md Archetype 8
export function TemplateBadgeMinimal(props: {
  tokens: BrandTokens;
  badge: string;
  title: string;
  subtitle?: string;
  techStack?: string[]; // rendered as plain-text pills; no external icon set is bundled
}) {
  const { tokens, badge, title, subtitle, techStack } = props;
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        position: "relative",
        background: tokens.bg,
        padding: tokens.paddingCanvas,
        justifyContent: "center",
        gap: 24,
      }}
    >
      <div style={dotGridStyle(tokens)} />
      <div style={{ display: "flex", position: "relative" }}>
        <PillBadge tokens={tokens}>{badge}</PillBadge>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 16, position: "relative", maxWidth: 760 }}>
        <TitleBlock tokens={tokens} title={title} subtitle={subtitle} align="left" maxTitleLines={2} />
      </div>
      {techStack && techStack.length > 0 && (
        <div style={{ display: "flex", gap: 12, position: "relative" }}>
          {techStack.map((t) => (
            <PillBadge key={t} tokens={tokens}>
              {t}
            </PillBadge>
          ))}
        </div>
      )}
    </div>
  );
}
