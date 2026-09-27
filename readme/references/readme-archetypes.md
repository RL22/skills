# README Architectural Archetypes

Different categories of software require distinct storytelling structures. This guide breaks down the four core archetypes distilled from top-ranking repositories in [`matiassingers/awesome-readme`](https://github.com/matiassingers/awesome-readme).

---

## Archetype 1: The Developer CLI / System Tool

**Key Exemplars**: `shallow-backup`, `colorls`, `vhs`, `create-go-app`

### Primary Goal
Convince a terminal power user that the tool is fast, lightweight, respects system hygiene, and can be installed via their package manager of choice in 10 seconds.

### Required Anatomy
1. **Header**: Centered tool name, 1-line capability summary, terminal-themed badges (Version, License, OS Support).
2. **Hero Terminal GIF**: A high-speed, aesthetically styled terminal recording showing real CLI interaction and immediate output.
3. **The "Why?"**: Bulleted checklist explaining what pain made the author build this instead of using shell aliases or bash scripts.
4. **Zero-Friction Install Matrix**: Multi-platform install commands:
   - macOS: `brew install tool`
   - Linux: `curl -fsSL https://... | sh` or package manager
   - Python/Node/Go/Rust: `pipx`, `npm install -g`, `go install`, or `cargo install`
5. **Quickstart & Common Commands**: 3 core commands demonstrated with copy-paste snippets.
6. **Command Recipes & Examples**: Practical real-world flags and workflows.
7. **Security & Configuration**: Config file location (`~/.config/tool/config.toml`), permissions model, and environment variables.

---

## Archetype 2: Full-Stack SaaS & Web Application

**Key Exemplars**: `reach`, `Bridge`, `amplication`, `supabase-plus`

### Primary Goal
Communicate a consumer- or enterprise-grade product experience. Bridge the gap between non-technical evaluators, product managers, and developers looking to self-host or inspect architecture.

### Required Anatomy
1. **Header Banner**: Designer-grade 1200px wide branding visual.
2. **Title & Mission Statement**: Symmetrical centered title, bold subtitle, and Product Hunt upvote widget.
3. **Problem Grid**: 3-column HTML card table highlighting current market failures (fragmentation, latency, high cost).
4. **Architecture Diagram**: Visual schematic explaining the end-to-end data flow (ingestion, processing, database, UI).
5. **Interactive Screenshot Gallery**: 2x2 or 3x1 visual table showcasing UI views (Dashboard, Analytics, Settings, Mobile).
6. **Tech Stack Grid**: Detailed component table displaying frontend, backend, database, and infrastructure choices with official icons.
7. **Self-Hosting / Deployment**: 1-click deploy buttons (Vercel, Railway, Docker Compose) alongside manual setup steps.

---

## Archetype 3: Open Source Library / SDK / Framework

**Key Exemplars**: `dbt-core`, `notecharts`, `choo`, `implot3d`

### Primary Goal
Establish developer ergonomics, API elegance, type safety, performance benchmarks, and minimal bundle impact.

### Required Anatomy
1. **Minimalist Header**: Clean project logo, package manager badges (npm downloads, PyPI version, Bundlephobia size, coverage).
2. **10-Line "Aha!" Code Snippet**: The cleanest possible syntax highlighting snippet showing the library solving a complex problem in seconds.
3. **Key Differentiators & Philosophy**: Why choose this over existing incumbent libraries?
4. **Benchmark & Comparison Table**: A matrix comparing performance (ops/sec, bundle size, dependency count) against alternatives.
5. **API Quick Reference**: Concise method signatures and return types, with links to full typed API documentation.
6. **Browser / Environment Matrix**: Supported runtimes (Node 18+, Bun, Deno, modern browsers).

---

## Archetype 4: AI Agent / Workflow Pipeline

**Key Exemplars**: Modern autonomous agent and LLM orchestration repos.

### Primary Goal
Prove architectural determinism, model flexibility, low hallucination/failure rates, cost efficiency, and ease of custom tool integration.

### Required Anatomy
1. **Header**: Name, AI domain tags, supported model provider logos (Anthropic, OpenAI, Google Gemini, Ollama, HuggingFace).
2. **Hero Flow Diagram**: Mermaid.js sequence or flowchart demonstrating the agent DAG (Planner → Tools → Evaluator → Synthesis).
3. **Model Support & Token Efficiency**: Table detailing supported providers, prompt token budgets, and streaming support.
4. **One-Command Agent Run**: Instant launch CLI command (`npx agent start` or `python -m agent`).
5. **Tool Registry & Extensibility**: Code example showing how developers register custom tools or MCP (Model Context Protocol) servers.
6. **Evaluation Benchmarks**: Eval accuracy scores, error recovery rates, and latency profiles.
