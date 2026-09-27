---
name: create-visuals
description: >
  Design rules and motion patterns for building polished Remotion videos and
  animated graphics: color system, typography, scene architecture, sound
  design, render settings, a pre-delivery checklist, and a library of 17
  reusable motion components (entrances, staggers, word reveals, mesh
  backgrounds, grain, vignette, Ken Burns, counters, transitions, captions).
  Use when composing a Remotion scene, animated title, explainer, or video
  graphic, or when a video looks flat and needs a quality pass. Trigger:
  /create-visuals. Pairs with the create-thumbnail and video-edit skills.
---

# Create Visuals

Quality rules and copy-paste motion patterns for Remotion work. This skill
holds the design judgment; it does not scaffold a project.

## Inputs

- The scene or graphic to build (topic, duration, aspect ratio)
- Brand colors and fonts, if the user has them. Otherwise use the proven palettes in `references/design-rules.md`.
- An existing Remotion project. If none exists, create one with `npx create-video@latest --blank`.

## Workflow

1. Read `references/design-rules.md`. Pick a palette (one base, one hero color, one accent), a type scale, and a scene structure.
2. Put every color, easing, and spring config in one `theme.ts`. Start from `references/upstream-theme-example.ts`. Never inline them in components.
3. Build each scene from the patterns in `references/motion-patterns.md`. Layer order, bottom to top: background mesh, content, color grade, grain, vignette.
4. Add sound design unless the user asks for silence.
5. Render at the settings in `references/design-rules.md`.
6. Run the pre-delivery checklist at the end of `references/design-rules.md` against the render before presenting it.

## Rules

- The hero color appears on at most one element per frame.
- Every still image gets Ken Burns motion.
- Exits are faster than entrances.
- Anything on screen longer than 2 seconds gets idle breathing motion.
- Fix checklist failures before presenting the result. Do not present a render that fails the checklist.

## References

| File | Use for |
| --- | --- |
| `references/design-rules.md` | Color, typography, scene architecture, sound, asset guidance, render settings, checklist |
| `references/motion-patterns.md` | 17 motion components with code |
| `references/upstream-theme-example.ts` | Starter `theme.ts` with colors, easings, spring configs |
