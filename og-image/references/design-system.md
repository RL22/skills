# Open Graph Image Layout Reference & Deconstruction
> **Source Data**: Analyzed 768+ unique Open Graph social card image examples across 17+ categories from [opengraphexamples.com](https://opengraphexamples.com/).  
> **Purpose**: Serves as an authoritative design reference to directly inform building a brand-agnostic, code-generated Open Graph image tool using an Atomic Design System architecture (Atoms, Molecules, Templates).

---

## 1. Canvas Geometry, Standard Proportions, & Safe Zones

### Standard Canvas Dimensions
* **Primary Open Graph Standard**: `1200px × 630px` (Aspect Ratio `1.904:1` ~ `1.91:1`).
  * Used by: Facebook, Twitter/X (Summary Card with Large Image), LinkedIn, Slack, Discord, iMessage, WhatsApp.
* **High-DPI / Retina Standard**: `2400px × 1260px` (2x scaling for ultra-crisp mobile & desktop displays).
* **Alternative Aspect Ratios & Deviations**:
  * `1200px × 600px` (`2.0:1` aspect ratio) — Legacy Twitter landscape format.
  * `1920px × 1080px` (`16:9` aspect ratio) — HD video thumbnail cross-over standard.
  * `1200px × 675px` (`16:9` aspect ratio) — Standard YouTube / social video thumbnail format.

### Safe Zone & Edge Margin Rules
Social platforms apply rounded corners, overlay badges (play icons, domain tags, timestamp overlays), or slight edge cropping depending on the client viewport.

* **Canvas Edge Padding (Safe Margin)**:
  * Minimum: `48px` (4% inset).
  * Standard / Recommended: `64px` (5.33% inset).
  * Generous / Minimalist: `80px` (6.67% inset).
* **Max Active Content Boundary (`1200 × 630`)**:
  * Width: `1072px` (`1200px - 128px horizontal margins`).
  * Height: `502px` (`630px - 128px vertical margins`).
* **Visual Hierarchy Spacing Grid**:
  * Outer canvas padding: `64px`.
  * Section gap (e.g., between Title block and Screenshot/Graphic): `32px` – `48px`.
  * Element gap (e.g., between Eyebrow and Main Heading): `12px` – `16px`.

---

## 2. Core Layout Archetypes

Deconstruction of the 8 predominant layout archetypes identified across the 768 scraped OG card examples.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              LAYOUT ARCHETYPES                          │
├───────────────────┬───────────────────┬───────────────────┬─────────────┤
│ 1. Dual Column    │ 2. Centered Hero  │ 3. Stat Callout   │ 4. App UI   │
│ ┌──────┬────────┐ │ ┌───────────────┐ │ ┌──────┬────────┐ │ ┌─────────┐ │
│ │ Text │ Mockup │ │ │   Eyebrow     │ │ │ Text │ 99.9%  │ │ │ [o o o] │ │
│ │ Block│ Graphic│ │ │   TITLE       │ │ │ Block│  STAT  │ │ │         │ │
│ └──────┴────────┘ │ └───────────────┘ │ └──────┴────────┘ │ └─────────┘ │
├───────────────────┼───────────────────┼───────────────────┼─────────────┤
│ 5. Code Terminal  │ 6. Full Photo     │ 7. Quote Card     │ 8. Badge    │
│ ┌──────┬────────┐ │ ┌───────────────┐ │ ┌───────────────┐ │ ┌─────────┐ │
│ │ Text │ $ code │ │ │ [Photo Image] │ │ │ “ Quote Text” │ │ │ [TAG]   │ │
│ │ Block│  snippet││ │ [Scrim Overlay│ │ │  - Author     │ │ │ Title   │ │
│ └──────┴────────┘ │ └───────────────┘ │ └───────────────┘ │ └─────────┘ │
└───────────────────┴───────────────────┴───────────────────┴─────────────┘
```

---

### Archetype 1: Title-Left / Visual-Right Split (Dual Column)
* **Description**: A asynchronous two-column layout. The left column contains the brand eyebrow, title, description, and footer logo. The right column displays a tilted 3D product screenshot, floating browser mockup, or feature visual.
* **Column Ratios**: `50/50`, `50/45` (with right visual overflow), or `60/40` left-dominant split.
* **Proportions & Bounds**:
  * Left Content Width: `520px - 600px`.
  * Right Visual Container: `480px - 580px`.
* **Recurring Visual Motifs**: Drop shadow under screenshot (`0 20px 40px rgba(0,0,0,0.3)`), subtle 3D perspective angle (`rotateY(-6deg) rotateX(4deg)`), background radial glow behind visual.
* **Typography**: Title `44px - 52px` bold, Subtitle `20px - 22px` regular, Eyebrow `14px` uppercase tracking `1.5px`.
* **Representative Examples & Categories**:
  * [Simple Analytics](https://opengraphexamples.com/examples/simple-analytics/) (`Website Analytics`) — Live privacy-first dashboard preview on right.
  * [Shipixen](https://opengraphexamples.com/examples/shipixen/) (`SaaS Starters`) — Left title block with right Next.js code/boilerplate mockup.
  * [Tailscan](https://opengraphexamples.com/examples/tailscan/) (`Website Development`) — Left text with right Tailwind inspector visual.
  * [Cartpops](https://opengraphexamples.com/examples/cartpops/) (`Ecommerce`) — Left headline with right floating toast/cart popup preview.

---

### Archetype 2: Centered Hero / Wordmark Card
* **Description**: Symmetrical, high-impact centered layout. Ideal for major product launches, brand taglines, or single focus tools. Features a central title banner flanked by an top eyebrow/logo badge and bottom domain tag.
* **Proportions & Bounds**:
  * Max Content Width: `900px` centered horizontally.
  * Vertical Alignment: Flex center with `gap: 20px - 32px`.
* **Recurring Visual Motifs**: Dark void background (`#0b0f17`), central radial gradient spotlight (`bg-radial`), noise texture overlay, thin glowing 1px border (`rgba(255,255,255,0.1)`).
* **Typography**: Title XL `56px - 72px` font-weight 800, line-height 1.1. Subtitle `22px - 24px` muted opacity 0.8.
* **Representative Examples & Categories**:
  * [Branding 5](https://opengraphexamples.com/examples/branding-5/) (`Marketing`) — Centered bold title with glowing gradient sphere background.
  * [SEO Stuff](https://opengraphexamples.com/examples/seo-stuff/) (`Marketing`) — Minimalist centered title with high contrast yellow accent text.
  * [Gasby](https://opengraphexamples.com/examples/gasby/) (`AI`) — Centered AI assistant card with glowing neon aura.
  * [Trailer Wave](https://opengraphexamples.com/examples/trailer-wave/) (`Website Development`) — Punchy centered wordmark with dark ambient background.

---

### Archetype 3: Stat / Metric Callout Card (Data-Driven)
* **Description**: Highlights quantitative social proof or report metrics (e.g. "115 SaaS Directories", "103 SEO Audit Score", "99.9% Uptime", "10M+ Queries").
* **Proportions & Bounds**:
  * Left side title block (`450px`), right side stat grid containing 1 to 4 large metric boxes (`550px`).
* **Recurring Visual Motifs**: Glassmorphism stat cards (`background: rgba(255,255,255,0.04)`), trend indicator pills (`+24%`), accent colored numbers (emerald `#10b981`, violet `#8b5cf6`, gold `#f59e0b`).
* **Typography**: Metric Number `64px - 96px` ExtraBold tabular figures, Metric Label `14px - 16px` uppercase bold. Title `36px - 44px`.
* **Representative Examples & Categories**:
  * [Hunted.Space Launch Analytics](https://opengraphexamples.com/examples/hunted.space-launch-analytics/) (`Website Analytics`) — Large numeric launch analytics grid.
  * [103SEO](https://opengraphexamples.com/examples/103seo/) (`Marketing`) — Highlighted SEO score stat callout card.
  * [listmysaas.com](https://opengraphexamples.com/examples/listmysaas.com/) (`Productivity`) — "115 Directories" massive numerical badge.
  * [Clobbr Test Results](https://opengraphexamples.com/examples/clobbr-test-results/) (`Website Development`) — Benchmark performance metric cards.

---

### Archetype 4: App UI / Floating Browser Window Frame
* **Description**: Encloses the core product visual or content inside a stylized browser chrome frame or macOS window wrapper inserted directly on the OG canvas.
* **Proportions & Bounds**:
  * Canvas padding: `48px - 64px`.
  * Window Frame: Outer dimensions `1072px × 502px`, Header bar height `36px - 42px`.
* **Recurring Visual Motifs**: Three macOS window dots (red `#ff5f56`, yellow `#ffbd2e`, green `#27c93f` at 12px diameter), search/URL address bar (`https://...`), soft drop shadow (`box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5)`).
* **Typography**: Address bar font `14px` monospace/sans, inner UI text matching app scale.
* **Representative Examples & Categories**:
  * [Shots](https://opengraphexamples.com/examples/shots/) (`Marketing`) — Clean canvas with inset browser mockup wrapper.
  * [Stagetimer Documentation](https://opengraphexamples.com/examples/stagetimer-documentation/) (`SaaS Starters`) — Inset documentation window chrome.
  * [One Tab Group](https://opengraphexamples.com/examples/one-tab-group/) (`Collaboration`) — Chrome extension UI inside window frame.
  * [Eesel](https://opengraphexamples.com/examples/eesel/) (`SaaS Starters`) — Search widget overlay inside app window frame.

---

### Archetype 5: Code Snippet / Terminal Developer Card
* **Description**: Specifically targeted at developers, API tools, and technical SaaS products. Features a dark IDE code block or terminal CLI prompt with syntax highlighting.
* **Proportions & Bounds**:
  * Left Title Column (`480px`), Right Code Terminal Block (`560px × 420px`).
* **Recurring Visual Motifs**: Dark charcoal container (`#0d1117` or `#090d16`), language badge tab (`index.ts`), terminal prompt symbol (`$`), colorful syntax tokens (cyan, pink, yellow, green).
* **Typography**: Monospace font (JetBrains Mono / Fira Code / Geist Mono) `18px - 24px`, line-height `1.5`.
* **Representative Examples & Categories**:
  * [Clobbr](https://opengraphexamples.com/examples/clobbr/) (`Marketing` / `Dev Tools`) — Terminal command execution card.
  * [DevTerms](https://opengraphexamples.com/examples/devterms/) (`Marketing`) — Code definition block layout.
  * [Code Snippets AI](https://opengraphexamples.com/examples/code-snippets-ai/) (`Productivity` / `AI`) — Syntax-highlighted AI code block preview.
  * [SearchAPI](https://opengraphexamples.com/examples/searchapi/) (`Collaboration` / `Dev Tools`) — JSON API payload terminal view.

---

### Archetype 6: Full-Bleed Photo / Gradient Overlay Scrim
* **Description**: Uses a high-resolution background image, 3D abstract render, or photography across 100% of the canvas, layered under a dark gradient scrim overlay for text legibility.
* **Proportions & Bounds**:
  * `100% × 100%` full-bleed background container.
* **Recurring Visual Motifs**: Dark scrim gradient (`linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0.85) 100%)` or `linear-gradient(90deg, rgba(0,0,0,0.9) 30%, transparent 100%)`), glass text card container (`backdrop-filter: blur(12px)`).
* **Typography**: Clean white text (`#ffffff`), `text-shadow: 0 2px 10px rgba(0,0,0,0.5)`.
* **Representative Examples & Categories**:
  * [Klu](https://opengraphexamples.com/examples/klu/) (`Productivity`) — Ambient photo background with dark frosted overlay.
  * [Gift Ideas AI](https://opengraphexamples.com/examples/gift-ideas-ai/) (`AI`) — Full-bleed AI imagery with bottom gradient title box.
  * [Hyperbolic](https://opengraphexamples.com/examples/hyperbolic/) (`Productivity`) — 3D abstract artwork background with crisp white overlay text.
  * [Himingle](https://opengraphexamples.com/examples/himingle/) (`Productivity`) — Rich hero visual with dark gradient left block.

---

### Archetype 7: Quote / Author & Testimonial Card
* **Description**: Designed for blog posts, opinion pieces, press quotes, or podcast episodes. Features a prominent quote mark, quote copy, author headshot avatar, name, and role.
* **Proportions & Bounds**:
  * Centered or left-aligned single-column stack.
* **Recurring Visual Motifs**: Decorative quote mark graphic (`“` in 120px light opacity serif), circular avatar headshot with border glow (`w-16 h-16 rounded-full`), star rating icons.
* **Typography**: Quote text `28px - 36px` serif/italic or clean sans, Author name `20px` bold, Role/Company `16px` muted opacity 0.7.
* **Representative Examples & Categories**:
  * [Curbn](https://opengraphexamples.com/examples/curbn/) (`Business Services`) — Quote card with founder callout.
  * [OpenAlternative](https://opengraphexamples.com/examples/openalternative/) (`Marketing`) — Community spotlight quote card.
  * [FounderPal](https://opengraphexamples.com/examples/founderpal/) (`Collaboration`) — Strategic quote/insight card.

---

### Archetype 8: Badge / Pill-Header Minimalist Card
* **Description**: Vercel/Linear style minimalist card layout. Features a top pill badge (e.g. `NEW FEATURE`, `CHANGELOG`, `DOCUMENTATION`), clean headline, short description, and bottom tech stack icon row.
* **Proportions & Bounds**:
  * Vertical stack with `gap: 20px - 28px`.
* **Recurring Visual Motifs**: Rounded pill tags (`border-radius: 9999px`, `border: 1px solid rgba(255,255,255,0.15)`), tech stack icon pills (React, Next.js, TypeScript), subtle dot matrix background.
* **Typography**: Pill tag `12px - 14px` font-weight 600 letter-spacing `1px`, Headline `48px` font-weight 700.
* **Representative Examples & Categories**:
  * [Typeframes](https://opengraphexamples.com/examples/typeframes/) (`Productivity`) — Pill tag header with dark clean typography.
  * [APIcrud](https://opengraphexamples.com/examples/apicrud/) (`Dev Tools`) — Minimalist badge header and code highlight tag.
  * [Open for Ads](https://opengraphexamples.com/examples/open-for-ads/) (`Marketing`) — Clean category pill tag header.
  * [Unicorn Platform](https://opengraphexamples.com/examples/unicorn-platform/) (`Collaboration`) — Minimalist page card with tech pills.

---

## 3. Recurring Visual Motifs & Aesthetic Primitives

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           VISUAL MOTIFS MATRIX                          │
├──────────────────────┬──────────────────────┬───────────────────────────┤
│ Background Gradients │ Textures & Patterns  │ Frames & Glassmorphism    │
│ • Mesh Gradient Glow │ • SVG Grain / Noise  │ • 1px Border Stroke       │
│ • Radial Spotlight   │ • Dot Matrix Grid    │ • Frosted GlassBlur       │
│ • Dark Void (#090d16)│ • Line Grid Grid     │ • macOS Window Dots       │
└──────────────────────┴──────────────────────┴───────────────────────────┘
```

1. **Gradients & Ambient Mesh Glows**:
   * **Radial Spotlight**: `radial-gradient(circle at 50% 0%, rgba(99, 102, 241, 0.25) 0%, transparent 70%)`. Adds depth behind central text.
   * **Dual Corner Glows**: Top-left indigo spotlight + bottom-right violet spotlight.
   * **Gradient Borders**: `border: 1px solid transparent; background-image: linear-gradient(135deg, rgba(255,255,255,0.2), rgba(255,255,255,0.02))`.

2. **Textures & Background Patterns**:
   * **SVG Grain / Noise**: SVG `<filter id="noise">` with `feTurbulence` overlay at `opacity: 0.03 - 0.05` to break gradient color banding.
   * **Dot Matrix Grid**: `background-image: radial-gradient(rgba(255, 255, 255, 0.12) 1px, transparent 1px); background-size: 24px 24px;`.
   * **Line Grid**: `background-image: linear-gradient(to right, rgba(255,255,255,0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.05) 1px, transparent 1px); background-size: 40px 40px;`.

3. **Borders, Frames, & Glassmorphism**:
   * **Subtle 1px Borders**: Dark theme: `border: 1px solid rgba(255, 255, 255, 0.1)`; Light theme: `border: 1px solid rgba(0, 0, 0, 0.08)`.
   * **Frosted Glass Containers**: `background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(16px); border-radius: 16px;`.
   * **macOS Window Dots**: Three 12px circles (`#ff5f56`, `#ffbd2e`, `#27c93f`) spaced 8px apart.

4. **Iconography & Badges**:
   * **Category Badges**: Pill shape (`px-3 py-1 rounded-full text-xs font-semibold`).
   * **Tech Stack Rows**: Inline flex row of brand SVG icons (Next.js, Tailwind, TypeScript, React) at `24px × 24px`.
   * **Avatar Stacks**: Overlapping circular headshots (`flex -space-x-3`) with `2px` border matching background.

---

## 4. Typography Scale & Hierarchy

Rules for type scale on a standard `1200px × 630px` canvas.

| Role | Font Size (px) | Line Height | Weight | Max Character / Line Count | Tracking / Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Title XL** (Short Title < 35 chars) | `56px – 72px` | `1.10` | 800 (ExtraBold) | Max 2 lines (~35 chars) | `-0.02em` (Tight) |
| **Title LG** (Standard Title 35-70 chars) | `40px – 52px` | `1.15` | 700 (Bold) | Max 3 lines (~70 chars) | `-0.01em` (Slightly tight) |
| **Title MD** (Long Title > 70 chars) | `32px – 38px` | `1.25` | 700 (Bold) | Max 3 lines (~100 chars) | `0` (Normal) |
| **Subtitle / Description** | `20px – 24px` | `1.40` | 400 - 500 (Regular/Medium) | Max 2 lines (~110 chars) | `0` (Normal) |
| **Eyebrow / Kicker** | `14px – 16px` | `1.00` | 600 (SemiBold) | Single line (~30 chars) | `+0.05em` (UPPERCASE) |
| **Stat Metric Number** | `64px – 96px` | `1.00` | 800 - 900 (Black) | Single line (3-6 chars) | `-0.03em` (Tabular) |
| **Domain / Brand Footer** | `16px – 18px` | `1.00` | 500 (Medium) | Single line (~30 chars) | `0` (Normal) |

### Recommended Fonts
* **Modern Sans (Primary)**: Inter, Plus Jakarta Sans, Geist Sans, Outfit, SF Pro Display, Space Grotesk.
* **Monospace (Code/Dev)**: JetBrains Mono, Fira Code, Geist Mono.
* **Serif (Editorial/Quote)**: Playfair Display, Newsreader, Lora.

---

## 5. Color & Contrast Strategies for Text Legibility

To guarantee readability when text overlays complex graphics or photo backgrounds:

1. **Linear Dark Scrim Overlay**:
   ```css
   /* Place behind text over full-bleed images */
   background: linear-gradient(180deg, rgba(0, 0, 0, 0.1) 0%, rgba(0, 0, 0, 0.85) 100%);
   ```
2. **Horizontal Gradient Mask**:
   ```css
   /* For left-aligned text over right-aligned visual graphics */
   background: linear-gradient(90deg, #090d16 0%, #090d16 55%, transparent 100%);
   ```
3. **Glassmorphic Card Backplates**:
   ```css
   /* Enclose text elements inside a semi-transparent blur container */
   background: rgba(15, 23, 42, 0.75);
   backdrop-filter: blur(16px);
   border: 1px solid rgba(255, 255, 255, 0.1);
   border-radius: 16px;
   padding: 32px;
   ```
4. **Text Shadow Enforcement**:
   ```css
   /* Ensures legibility on variable brightness backgrounds */
   text-shadow: 0 2px 10px rgba(0, 0, 0, 0.6);
   ```

---

## 6. Atomic Design System Architecture

This specification maps the research findings directly into a code-implementable **Atomic Design System** structure for an automated OG image generator tool (Satori / HTML Canvas / Svelte / SVG / Tailwind).

```
ATOMIC OG SYSTEM ARCHITECTURE
│
├── 1. ATOMS (Tokens & Visual Primitives)
│   ├── TypeScaleTokens (XL: 64px, LG: 48px, MD: 36px, Subtitle: 22px, Eyebrow: 14px)
│   ├── ColorTokens (DarkBg: #090d16, LightBg: #fafafa, AccentPrimary: #6366f1, TextMuted: #94a3b8)
│   ├── SpacingTokens (PaddingCanvas: 64px, GapSection: 32px, GapItem: 16px, RadiusCard: 16px)
│   └── MotifAtoms (NoiseOverlay, DotGridPattern, RadialGlow, WindowDots, SubtleBorder)
│
├── 2. MOLECULES (Composite Layout Blocks)
│   ├── EyebrowHeader (Pill Badge + Category Tag)
│   ├── TitleBlock (Eyebrow + Main Title + Subtitle Description)
│   ├── BrandFooter (Logo Icon + Brand Name + Domain URL)
│   ├── StatMetricBox (Hero Metric Number + Label + Trend Pill)
│   ├── CodeWindow (macOS Header Bar + Syntax Highlighted Code Container)
│   ├── ScreenshotFrame (Browser Window Mockup + Drop Shadow)
│   └── AuthorByline (Headshot Avatar + Name + Role)
│
└── 3. TEMPLATES (Full Card Layout Presets)
    ├── Template_SplitScreen (TitleBlock + ScreenshotFrame)
    ├── Template_CenteredHero (EyebrowHeader + Center TitleBlock + RadialGlow)
    ├── Template_StatGrid (TitleBlock + StatMetricBox Grid)
    ├── Template_CodeTerminal (TitleBlock + CodeWindow)
    ├── Template_AppWindow (Full Inset ScreenshotFrame Window)
    ├── Template_FullPhoto (Photo Background + Scrim Overlay + TitleBlock)
    ├── Template_QuoteCard (Quote Mark + Quote Text + AuthorByline)
    └── Template_BadgeMinimal (EyebrowHeader Pill + Headline + BrandFooter)
```

---

### Component Implementation Mapping

#### Atoms (Primitives)
* `TypeScale`: Pre-calculated CSS variables or Satori inline style objects mapping `TitleXL` (`64px`), `TitleLG` (`48px`), `Eyebrow` (`14px uppercase`).
* `ColorTokens`: Theme maps (`dark`, `light`, `gradient-indigo`, `gradient-emerald`).
* `MotifAtoms.NoiseOverlay`: SVG noise overlay data URI.
* `MotifAtoms.DotGridPattern`: Background dot-matrix SVG string.

#### Molecules (Composite Components)
* `TitleBlock`: Takes `{ eyebrow, title, subtitle, maxTitleLines: 3 }` and computes optimal font size based on string length.
* `BrandFooter`: Renders `{ logoUrl, brandName, domain }` at bottom left or bottom right of canvas.
* `StatMetricBox`: Formats numeric callout `{ value: "99.9%", label: "Uptime SLA", trend: "+2.4%" }`.
* `CodeWindow`: Formats code snippet with syntax colors and macOS red/yellow/green window controls.

#### Templates (Card Presets)
* `Template_SplitScreen`: Flex layout (`row`), Left `w-1/2` `TitleBlock`, Right `w-1/2` `ScreenshotFrame`.
* `Template_CenteredHero`: Flex layout (`col`), `items-center justify-center`, background `RadialGlow`.
* `Template_StatGrid`: Flex layout (`row`), Left `TitleBlock`, Right 2x2 grid of `StatMetricBox` components.
