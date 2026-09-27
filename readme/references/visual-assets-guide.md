# Visual Assets & Media Guide for READMEs

Visual polish separates amateur repositories from top-trending projects. This guide covers recommended tools and techniques for generating production-quality assets.

---

## 1. Terminal Recordings: `vhs` (Recommended)

[`vhs`](https://github.com/charmbracelet/vhs) is the gold standard for terminal recording because it is **declarative and scripted**. You write a `.tape` file, and `vhs` outputs a pixel-perfect, typography-styled GIF or MP4.

### Example `demo.tape` File
```tape
# Output settings
Output assets/demo.gif
Set FontSize 18
Set Width 1200
Set Height 600
Set Theme "Catppuccin Mocha"
Set WindowBar Colorful

# Scripted execution
Type "readme --init my-project"
Sleep 500ms
Enter
Sleep 1s
Type "Creating high-converting README structure..."
Sleep 500ms
Enter
Sleep 2s
```

Run in terminal:
```bash
vhs demo.tape
```

---

## 2. Media Performance Budgets & CLS Prevention

A heavy hero GIF is the fastest way to ruin repository performance. At 1200×600, a 10-second 15 fps GIF consumes roughly **432 MB of decoded RGBA memory** in browser RAM, causing mobile Safari / Chrome memory pressure and sluggish scrolling.

### Strict Media Budgets
- **Static Hero Poster**: Under **250 KB** (WebP or optimized PNG).
- **Animated Hero (if motion is essential)**:
  - **Transfer Size**: Under **2.0 MB** (never allow 8MB+ blobs).
  - **Dimensions**: Max **800px** width (GitHub content container is 888px; 800px scales crisply without wasting pixel data).
  - **Frame Rate**: Max **10–12 fps** (sufficient for UI/terminal; halves frame count).
  - **Duration**: Max **6–8 seconds** per loop.
- **Intrinsic Numeric Dimensions (Zero-CLS)**:
  Always specify explicit integer `width` and `height` attributes to prevent Cumulative Layout Shift (CLS):
  ```html
  <img src="assets/hero.webp" alt="UI Demo" width="800" height="450">
  ```
  *(Avoid `width="100%"` as an HTML attribute; it is non-standard for raster media and causes layout reflows).*

### Third-Party CDN Origin Budget
- **Origin Ceiling**: Limit external image origins to **<= 2** per README.
- **Why**: While GitHub proxies images via Camo (`camo.githubusercontent.com`), Camo must still fetch the origin on cache misses. If `api.iconify.design`, `skillicons.dev`, or `api.star-history.com` suffers rate limiting, latency spikes, or downtime, your README displays broken image placeholders.
- **Best Practice**: Vendor critical SVG icons locally in an `assets/icons/` folder, or commit generated Star History SVGs in CI rather than fetching them dynamically per pageview.

---

## 3. Cohesive Badge Systems (Shields.io)

Badges provide credibility, but an uncontrolled mix of styles looks disorganized. Follow these design rules:

### Uniform Style
Choose one badge style and stick to it throughout the README:
- `style=for-the-badge` (Bold, modern, great for top-level headers)
- `style=flat-square` (Compact, technical, great for libraries and CLI tools)

### Unified Color Palette
Avoid random rainbow badges. Pick an accent color matching your brand and set a consistent dark background label (`labelColor=0D1117` or `labelColor=1A1A1A`):

```markdown
<!-- Stars Badge -->
[![Stars](https://img.shields.io/github/stars/owner/repo?style=for-the-badge&color=4F9CF9&labelColor=0D1117)](https://github.com/owner/repo/stargazers)

<!-- License Badge -->
[![License](https://img.shields.io/badge/License-MIT-4F9CF9?style=for-the-badge&labelColor=0D1117)](LICENSE)

<!-- Version Badge -->
[![Version](https://img.shields.io/github/v/release/owner/repo?style=for-the-badge&color=4F9CF9&labelColor=0D1117)](https://github.com/owner/repo/releases)
```

---

## 4. Dynamic GitHub Widgets

### Interactive Star History Chart
Shows project momentum over time. Embed dynamically using the Star History API:

```markdown
<div align="center">
  <a href="https://star-history.com/#owner/repo&Date">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=owner/repo&type=Date&theme=dark" />
      <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=owner/repo&type=Date" />
      <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=owner/repo&type=Date" width="80%" />
    </picture>
  </a>
</div>
```

### Contributor Avatar Grid
Recognize community contributors automatically using [`contrib.rocks`](https://contrib.rocks):

```html
<a href="https://github.com/owner/repo/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=owner/repo" alt="Contributors" />
</a>
```

### Skill Icons
Display clean, high-resolution technology badges via [`skillicons.dev`](https://skillicons.dev):

```html
<p align="center">
  <a href="https://skillicons.dev">
    <img src="https://skillicons.dev/icons?i=ts,react,nextjs,tailwind,postgres,docker" />
  </a>
</p>
```
