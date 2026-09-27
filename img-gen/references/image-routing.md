# Image routing — which model for which job

## The principle

**Symbols and structure → GPT Image (`image-text`). Light, matter and continuity → Nano Banana Pro (`image`).**

Every task below resolves through that one split:

- **GPT Image** is right when the image must contain *discrete things that have to be correct* — legible copy, exact prices, geometric lines, grid alignment, numbered callouts. Getting a price wrong or a column misaligned is a defect, not a style choice.
- **Nano Banana Pro** is right when the image must be *continuously rendered* — how light bounces, how fabric falls, how skin reads, how a character stays the same person across frames. There is no "correct" pixel, only a plausible one.

When a prompt wants both (a photoreal storefront *with* a legible sign), pick by which failure is worse. A beautiful sign with garbled text usually fails harder than a correct sign in flatter light — so lean `image-text`.

## Taxonomy Slug Mapping

Hard-map taxonomy slugs directly to models:
- **Codex/GPT (`image-text`)**: `ui-mockup`, `infographic-diagram`, `logo-brand`
- **Gemini/Nano Banana (`image`)**: `photorealistic-natural`, `identity-preserve`

## Matrix

| Vertical | Task | Micro-requirement | Route |
|---|---|---|---|
| Interior Design | Commercial space walkthroughs | Accurate ambient light bounce from glass/steel | `image` |
| | Residential virtual staging | Realistic fabric draping and wood grain textures | `image` |
| | Floorplan & blueprint layout | Clean geometric lines and technical text labels | `image-text` |
| UI/UX & Web | High-fidelity dashboard mockups | Multi-column layouts, data grids, icon alignment | `image-text` |
| | App onboarding screen | Crisp, legible text headers and body copy | `image-text` |
| | Hero section illustrations | Stylized, organic brand artwork with complex lighting | `image` |
| Advertising | Product-focused social ads | Exact promotional text, price points, slogans | `image-text` |
| | Lifestyle brand photography | Photorealistic humans, natural skin and hair texture | `image` |
| | Multi-product retail composition | Merging several reference images into one scene | `image` |
| Entertainment | Cinematic storyboards | Two or more characters interacting in one frame | `image` |
| | Graphic novel panels | Sequential background consistency across frames | `image` |
| | Title sequence cards | Stylized 3D text logos and fantasy typography | `image-text` |
| Technical Media | Infographics | Flowchart arrows, nested data blocks, chart keys | `image-text` |
| | Patent-style diagrams | Exploded-view technical sketches with numbers | `image-text` |

Eight `image-text`, six `image`. GPT Image is not a fallback — it is the primary choice for more than half these jobs, which is why the route is named `image-text` rather than `image-alt`.

## Model tiers on the agy side

agy's `generate_image` **inherits the session model tier**. This is the whole reason the route pins a model:

| Invocation | Serves |
|---|---|
| `agy -p "…generate_image…"` (no `--model`) | NB2-lite default |
| `agy --model gemini-3.1-pro-high -p "…"` | Nano Banana Pro |

The `image` route pins `gemini-3.1-pro-high` for exactly this reason. Omitting it silently downgrades every job in the left column to the lite model — a quiet quality regression with no error.

Observed: ~725KB output at Pro vs ~118KB on the lite default for comparable prompts. Slug and display name (`"Gemini 3.1 Pro (High)"`) both resolve.

The installed `nanobanana` MCP extension at `~/.gemini/antigravity-cli/plugins/nanobanana` pins Nano Banana 2 and needs `NANOBANANA_API_KEY` — it is **not** what serves this route. agy's `mcpServers` is empty and the tool name is unprefixed.

## Artifacts

| Route | Where the file lands | What the router reports |
|---|---|---|
| `image` | under `--dir` | the `--dir` copy |
| `image-text` / `image-alt` | under `--dir`, either directly or promoted from the private runtime cache | **the `--dir` copy** |

The router always reports a durable `--dir` artifact. If Codex writes only to its
ephemeral cache, the router promotes that image into `--dir` before cleanup.

The located path is printed as an `IMAGE:` line on stdout and a note on stderr. The router
exits `3` (`EX_EMPTY`) if the executor claims success but no file appears anywhere — an
image task that produces no image is a failure, not a terse success.

## Gotchas

- **An image prompt needs a tool instruction, not just a subject.** Handed a bare subject line, agy answers in prose and writes nothing. The router wraps image-mode prompts with an explicit "use the generate_image tool… do not reply with a description" instruction. A `--dry-run` will not catch a regression here — it only proves the command was built.
- **`--dir` matters on the codex routes.** They pass `--cd "$WORKDIR"`; without it codex runs in the caller's cwd and writes somewhere the caller never looks, while still exiting 0.
- **Neither codex route takes an image model.** codex owns that internally; naming one fails.
