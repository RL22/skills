# Product Hunt Launch Anatomy: Conversion & Positioning Guide

A Product Hunt launch requires immediate conversion mechanics. Visitors arriving from Product Hunt are impatient: they give a repository 3–5 seconds before either upvoting/starring or closing the tab.

---

## 1. Product Hunt Badges & Embed Widgets

Place the Product Hunt embed immediately above or below the badge ribbon.

### Live Featured Widget (Light & Dark Theme)
The official Product Hunt embed dynamically updates with upvote counts:

```html
<a href="https://www.producthunt.com/posts/{slug}?embed=true&utm_source=badge-featured&utm_medium=badge&utm_campaign=badge-{slug}" target="_blank">
  <img src="https://api.producthunt.com/widgets/embed-image/v1/featured.svg?post_id={post_id}&theme=neutral" alt="{Product Name} - {Tagline} | Product Hunt" style="width: 250px; height: 54px;" width="250" height="54" />
</a>
```

> [!TIP]
> Use `&theme=neutral` for seamless background blending across both dark and light modes on GitHub.

### Top Product of the Day / Week Badge
If you achieve Top 5 or #1 Product of the Day, update the badge to display your award:

```html
<a href="https://www.producthunt.com/posts/{slug}?embed=true" target="_blank">
  <img src="https://api.producthunt.com/widgets/embed-image/v1/top-post-badge.svg?post_id={post_id}&theme=neutral&period=daily" alt="{Product Name} - #1 Product of the Day | Product Hunt" style="width: 250px; height: 54px;" width="250" height="54" />
</a>
```

---

## 2. The 1-Liner Hook Formula

Your title and tagline must be understandable to a general tech audience within 3 seconds. Avoid internal jargon.

| Formula | Structure | Example |
| :--- | :--- | :--- |
| **Pain Relief** | `[Do Desirable Action] without [Hated Chore]` | *"Automate full-stack E2E tests without writing flaky selectors"* |
| **Category King** | `The [Superlative] [Category] for [Target Group]` | *"The ultra-fast terminal file manager for Neovim lovers"* |
| **X for Y** | `[Familiar High-Status Product] for [New Niche]` | *"Linear for personal project planning"* |
| **Zero-State** | `Zero-[Friction Point] [Outcome]` | *"Zero-configuration Postgres replication in 60 seconds"* |

---

## 3. The 3-Column Problem / Solution Framework

Hunters want to know: **"Why does this exist?"**
Structure the problem as 3 distinct friction points, followed by how your project changes the game.

```html
<table width="100%">
  <tr>
    <td width="33%" valign="top" align="center">
      <h4>❌ The Status Quo</h4>
      <p>Existing tools require complex YAML configs and 10+ cloud dependencies just to run locally.</p>
    </td>
    <td width="33%" valign="top" align="center">
      <h4>⚠️ The Hidden Cost</h4>
      <p>Teams spend 20 hours per sprint debugging fragile integration scripts and broken mocks.</p>
    </td>
    <td width="33%" valign="top" align="center">
      <h4>✨ The Solution</h4>
      <p>One self-contained binary with automated zero-config environment virtualization.</p>
    </td>
  </tr>
</table>
```

---

## 4. Hero Visual Assets: Specifications & Best Practices

Showing the tool in action builds immediate conviction, but bloated assets destroy mobile conversions:

- **Format**: Static WebP/PNG poster (recommended, <250KB) or animated WebP/GIF (<2MB).
  *(Note: GitHub does not support externally hosted looping video in markdown; user-uploaded video embeds require manual play click).*
- **Target Size**: Under **2 MB** (strictly enforce to prevent mobile browser tab crashes).
- **Dimensions**: 800px width with integer `width="800"` and `height="450"` attributes to eliminate Cumulative Layout Shift (CLS).
- **Duration**: 6 to 8 seconds per loop. Deliver the core visual "aha!" within the first 3 seconds.
- **Terminal Recordings**: Use [`vhs`](https://github.com/charmbracelet/vhs) to render pixel-perfect, typography-styled terminal recordings.

---

## 5. Launch Day Special Offer & Founder Note

Convert casual visitors into active stars and contributors by including a warm, personal callout:

```markdown
> [!TIP]
> **🚀 Product Hunt Launch Day Special**
> Thank you to everyone from the Product Hunt community checking us out today!
> - Star the repo to unlock our premium starter templates in `/examples`.
> - Have feedback or a feature request? Drop a comment on our [Product Hunt launch page](https://www.producthunt.com/posts/{slug}) or join our [Discord](https://discord.gg/yourinvite)!
```

---

## 6. Social Proof Ribbon

Stack social proof elements in a clean ribbon:

```html
<div align="center">

[![GitHub Stars](https://img.shields.io/github/stars/{owner}/{repo}?style=for-the-badge&color=FF6154&logo=github&labelColor=1A1A1A)](https://github.com/{owner}/{repo}/stargazers)
[![Product Hunt](https://img.shields.io/badge/Product_Hunt-Upvote-DA552F?style=for-the-badge&logo=producthunt&logoColor=white&labelColor=1A1A1A)](https://www.producthunt.com/posts/{slug})
[![Discord Community](https://img.shields.io/badge/Community-Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white&labelColor=1A1A1A)](https://discord.gg/yourinvite)
[![License](https://img.shields.io/badge/License-MIT-00B4D8?style=for-the-badge&labelColor=1A1A1A)](LICENSE)

</div>
```

---

## 7. Benchmark & Claims Credibility (The Anti-Hype Standard)

Technical developers and skeptics immediately discount claims like "10x faster" or "zero overhead" if unsupported. When publishing performance claims on Product Hunt or GitHub:

### Required Benchmark Reproducibility Checklist
Never publish raw numbers without linking to a committed reproduction script. Every benchmark table must specify:
1. **Commit Hash**: Target repository commit and harness commit.
2. **Environment & Hardware**: Exact CPU architecture (e.g. Apple M3 Max, AMD EPYC 7763), RAM, OS version, and compiler/runtime version (e.g. Node v22.4.1, Go 1.23).
3. **Methodology**: Number of warmups, trials, median score, and standard deviation (dispersion).
4. **Competitor Baseline Versions**: Exact version and flags used for comparison targets (avoid benchmarking against unoptimized defaults).
5. **Raw Data**: Link to machine-readable JSON/CSV output in `/benchmarks/results/`.
