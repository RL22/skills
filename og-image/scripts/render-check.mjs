#!/usr/bin/env node
// Renders every template in assets/templates.tsx through the real Satori
// engine (not just tsc --noEmit, which passes even when Satori throws at
// render time - that's how the inset/viewBox/undefined-maxWidth bugs shipped
// past the first review). Run after any change to templates.tsx.
//
// Usage: node scripts/render-check.mjs
// Requires: npm install --no-save satori @resvg/resvg-js typescript @types/react
//           (run once in this directory; not part of the shipped skill deps)

import { readFileSync, writeFileSync, mkdirSync, rmSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";
import satori from "satori";
import { Resvg } from "@resvg/resvg-js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const SKILL_ROOT = join(__dirname, "..");

// Transpile templates.tsx to plain JS (jsx: react-jsx) into a subdirectory of
// the skill root (NOT os.tmpdir()) so Node's ESM resolver walks up into the
// skill's own node_modules for "react" and "satori" - a tmpdir output has no
// node_modules ancestry and fails to resolve them.
const tmp = join(SKILL_ROOT, "scripts/.render-check-tmp");
rmSync(tmp, { recursive: true, force: true });
mkdirSync(tmp, { recursive: true });
execSync(
  `npx tsc "${join(SKILL_ROOT, "assets/templates.tsx")}" --jsx react-jsx --module esnext --target es2020 --moduleResolution bundler --outDir "${tmp}" --skipLibCheck`,
  { stdio: "inherit" }
);
const mod = await import(join(tmp, "templates.js"));
const {
  TemplateCenteredHero,
  TemplateSplitScreen,
  TemplateStatGrid,
  TemplateAppWindow,
  TemplateCodeTerminal,
  TemplateFullPhoto,
  TemplateQuoteCard,
  TemplateBadgeMinimal,
  exampleTokens,
} = mod;

const fontDir = join(SKILL_ROOT, "assets/fonts");
const fonts = [
  { name: "Space Grotesk", data: readFileSync(join(fontDir, "SpaceGrotesk-600.ttf")), weight: 600, style: "normal" },
  { name: "Space Grotesk", data: readFileSync(join(fontDir, "SpaceGrotesk-700.ttf")), weight: 700, style: "normal" },
  { name: "JetBrains Mono", data: readFileSync(join(fontDir, "JetBrainsMono-500.ttf")), weight: 500, style: "normal" },
];

// Self-contained stand-in "photo" for TemplateFullPhoto - a gradient SVG data
// URI, so the smoke test needs no network fetch and no real photo asset.
const FAKE_PHOTO =
  "data:image/svg+xml," +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#312e81"/><stop offset="1" stop-color="#0f172a"/></linearGradient></defs><rect width="1200" height="630" fill="url(#g)"/></svg>'
  );

const cases = [
  ["centered-hero", TemplateCenteredHero({ tokens: exampleTokens, eyebrow: "SPRINTZ", title: "Ship faster with less overhead." })],
  ["split-screen", TemplateSplitScreen({ tokens: exampleTokens, eyebrow: "LAUNCH", title: "A split-screen card with a longer left-aligned title to check truncation." })],
  [
    "stat-grid",
    TemplateStatGrid({
      tokens: exampleTokens,
      eyebrow: "Q3 REPORT",
      title: "Growth metrics",
      stats: [
        { value: "99.9%", label: "Uptime", trend: "+0.4%" },
        { value: "10M+", label: "Queries" },
        { value: "42", label: "Regions" },
      ],
    }),
  ],
  ["app-window", TemplateAppWindow({ tokens: exampleTokens, url: "https://app.example.com/dashboard" })],
  [
    "code-terminal",
    TemplateCodeTerminal({
      tokens: exampleTokens,
      eyebrow: "API",
      title: "One request, typed responses.",
      filename: "index.ts",
      lines: [
        [{ text: "import", color: "#ff7b72" }, { text: " { client } " }, { text: "from", color: "#ff7b72" }, { text: ' "sdk"', color: "#a5d6ff" }],
        [{ text: "" }],
        [{ text: "const", color: "#ff7b72" }, { text: " res = " }, { text: "await", color: "#ff7b72" }, { text: " client.query()" }],
      ],
    }),
  ],
  [
    "full-photo",
    TemplateFullPhoto({
      tokens: exampleTokens,
      eyebrow: "CASE STUDY",
      title: "How Acme cut onboarding time by 60%.",
      backgroundImage: FAKE_PHOTO,
    }),
  ],
  [
    "quote-card",
    TemplateQuoteCard({
      tokens: exampleTokens,
      quote: "The fastest team we've worked with, by a wide margin.",
      author: "Jordan Rivera",
      role: "VP Engineering, Acme",
    }),
  ],
  [
    "badge-minimal",
    TemplateBadgeMinimal({
      tokens: exampleTokens,
      badge: "NEW FEATURE",
      title: "Realtime collaboration",
      subtitle: "See every cursor, every edit, live.",
      techStack: ["React", "Next.js", "TypeScript"],
    }),
  ],
];

let failed = 0;
for (const [name, element] of cases) {
  try {
    const svg = await satori(element, { width: 1200, height: 630, fonts });
    const png = new Resvg(svg).render().asPng();
    const outPath = join(SKILL_ROOT, `scripts/.render-check-${name}.png`);
    writeFileSync(outPath, png);
    console.log(`OK   ${name}  -> ${outPath}  (${png.length} bytes)`);
  } catch (err) {
    failed++;
    console.error(`FAIL ${name}: ${err.message}`);
  }
}

if (failed > 0) {
  console.error(`\n${failed}/${cases.length} template(s) failed to render.`);
  process.exit(1);
}
console.log(`\nAll ${cases.length} templates rendered successfully.`);
