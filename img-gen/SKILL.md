---
name: img-gen
description: "Image generation and editing. Triggers on requests to create, edit, or modify visual assets (img, photo, logo, banner, /img-gen)."
argument-hint: "<prompt or path>"
metadata:
  version: "0.1.0"
author: "Rodney Lewis"
date_added: "2026-08-12"
---

# /img-gen

## Invocation

`/img-gen {model?} {prompt?}` — model is `gemini` | `gpt` (omit = auto).

| You give | Action |
|---|---|
| model + prompt | optimize prompt in that model's dialect, then generate |
| prompt only | recommend the best-fit model + one-line reason, confirm, generate |
| model only | ask the user for the goal (use case, style, key elements), then generate |
| neither | ask the goal first, recommend a model, then generate |

## Model routing (auto)

This skill owns the model routing policy (combining Nano Banana vs GPT logic). Use the matrix in `references/image-routing.md` to recommend the best-fit model. Always announce the chosen model and why.

For model-specific params load `references/nano-banana.md` or `references/gpt-image.md` — only the one you're using.

## Execution Rules

- **Prompt Schema:** Model-specific prompt formatting is strictly required:
  - If routing to **Codex/GPT Image**, rigorously enforce the structured 14-part schema (Use case, Asset type, Primary request, etc.).
  - If routing to **Gemini/Nano Banana**, use the 5-component natural language formula (`Subject -> Action -> Location -> Composition -> Style`). Write as flowing descriptive paragraphs.
    - **Spatial Anchoring:** Explicitly define UI layouts and bounding boxes using spatial anchors (e.g., 'header', 'left third', 'foreground') in the 'Composition' section.
- **Latency & Prototyping Modes:** When doing drafts or multi-turn edits with GPT Image, explicitly pass `--effort low` and prioritize square resolutions. Only use high quality for final exports.
- **Edit Invariant Carry-over:** Explicitly instruct the agent to copy the `Constraints:` block (or invariant text) from the previous turn for multi-turn edits to prevent model drift.
- **Preflight Checks:** Instruct the agent to run `scripts/preflight.sh <image_path>` on any input images or masks before delegating to `delegate.sh`.
- **Transparent Backgrounds:** Since neither model supports native transparency, if the user requests a cutout or transparent background, explicitly prompt the model to generate the subject on a "solid white or neutral gray background" (to ensure clean edge extraction). Then run `scripts/remove_bg.sh <input_file> <output_file>` to strip the background.
- **Completion:** Do not stop until the final image file is written to the workspace and verified.
