---
name: create-thumbnail
description: >
  Generate YouTube thumbnail candidates by cutting the subject out of a
  source frame or photo with rembg's BiRefNet engine, then compositing it
  onto a branded background via a Remotion Still (title text, gradient,
  brand tokens). Replaces the manual Photoshop thumbnail step in the
  video-edit pipeline. Trigger: /create-thumbnail <slug> [source-image].
  Auto-activates when the user says "make a thumbnail", "generate
  thumbnail candidates", or asks to cut out/remove background from a video
  frame for a thumbnail.
---

# Thumbnail Generator

## Purpose

Produce several composited thumbnail candidates per video: subject
cut out cleanly from the background (via `rembg` + BiRefNet, run locally,
no cloud), placed onto a branded Remotion `<Still>` composition with title
text. Human picks the winner — this skill never auto-selects or
auto-publishes.

---

## Invocation

```
/create-thumbnail <slug> [source-image]
```

- `slug` — matches `content-outlines/<slug>/` (same convention as `video-edit`).
- `source-image` — optional path to a photo/frame to cut the subject from.
  If omitted, grab 3 candidate frames from the finished video instead (see
  Step 1b).

---

## Step 0 — Resolve paths

```bash
CONTENT_DIR="${SPRINTZ_CONTENT_DIR:-$HOME/Sprintz/brands/sprintz/content}"
SLUG_DIR="$CONTENT_DIR/content-outlines/$SLUG"
THUMB_DIR="$SLUG_DIR/thumbnail-candidates"
mkdir -p "$THUMB_DIR/cutouts" "$THUMB_DIR/renders"
```

---

## Step 1 — Get candidate source frames

### 1a. Explicit source image provided
Copy it into `$THUMB_DIR/source-1.png` (convert to PNG if needed via
`ffmpeg -i <source> $THUMB_DIR/source-1.png`).

### 1b. No source given — pull frames from the video
Use whichever of these exists in the slug folder, in order of preference:
`final.mp4` (post-finalize) → `edit-composited.mp4` (post-edit) →
the raw footage in `raw/`.

```bash
VIDEO="$SLUG_DIR/final.mp4"  # fall back per the order above if missing
DURATION=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO")
# Grab 3 candidate frames spread across the video, biased toward moments
# with an expressive face if known cue timestamps exist (e.g. a KEY MOMENT
# cue) — otherwise evenly spaced.
for i in 1 2 3; do
  T=$(python3 -c "print(float('$DURATION') * $i / 4)")
  ffmpeg -y -ss "$T" -i "$VIDEO" -frames:v 1 "$THUMB_DIR/source-$i.png"
done
```

---

## Step 2 — Cut out the subject with rembg (BiRefNet)

```bash
which rembg > /dev/null || uv tool install rembg
for src in "$THUMB_DIR"/source-*.png; do
  name=$(basename "$src" .png)
  rembg i -m birefnet-general -vm "$src" "$THUMB_DIR/cutouts/$name-cutout.png"
done
```

- `-m birefnet-general` — best general-purpose matting quality of the
  cached BiRefNet variants; use `birefnet-portrait` instead if all
  candidates are tight head-and-shoulders shots (sharper hair/edge detail
  on portraits specifically).
- `-vm` (ViTMatte edge refinement) — worth the extra render time for
  thumbnails since edge quality is the difference between "cut out" and
  "obviously cut out."
- First run downloads BiRefNet weights (~1GB+); cached after that.

Run this as a loop, not one call per invocation — batch all candidate
frames through rembg in a single script pass so the model loads once
rather than once per image.

---

## Step 3 — Composite via Remotion Still

### 3a. Ensure a Remotion project exists
Check for `$CONTENT_DIR/../video-pipeline/remotion-project/`. If missing,
scaffold one (per the `remo-remotion` skill's setup instructions) and add
`remocn` for component primitives:

```bash
REMOTION_PROJECT="$CONTENT_DIR/../video-pipeline/remotion-project"
if [ ! -d "$REMOTION_PROJECT" ]; then
  npx create-video@latest --yes --blank --no-tailwind "$REMOTION_PROJECT"
  cd "$REMOTION_PROJECT" && npx skills use Remocn/remocn@remocn 2>&1 || true
fi
```

This is a single shared Remotion project reused across thumbnails **and**
`create-visuals` graphics — not a new project per video.

### 3b. Thumbnail composition
If `$REMOTION_PROJECT/src/Thumbnail.tsx` doesn't exist yet, create it
following the `remotion-dev/template-still` pattern (a `<Still>`
composition with a zod-typed props schema, not a video `<Composition>`):

```tsx
// src/Thumbnail.tsx
import { zColor } from "@remotion/zod-types";
import { AbsoluteFill, Img, staticFile } from "remotion";
import { z } from "zod";

export const thumbnailSchema = z.object({
  cutoutPath: z.string(),       // absolute path to the rembg cutout PNG
  title: z.string(),             // short punchy overlay text
  bgColor: zColor(),             // from visual-identity.md brand tokens
  accentColor: zColor(),
});

export const Thumbnail: React.FC<z.infer<typeof thumbnailSchema>> = ({
  cutoutPath, title, bgColor, accentColor,
}) => (
  <AbsoluteFill style={{ backgroundColor: bgColor }}>
    {/* background gradient/mesh — keep simple, subject + text carry the thumbnail */}
    <AbsoluteFill style={{
      background: `radial-gradient(circle at 70% 50%, ${accentColor}33, transparent 60%)`,
    }} />
    <Img
      src={cutoutPath}
      style={{ position: "absolute", right: 0, bottom: 0, height: "100%", objectFit: "contain" }}
    />
    <div style={{
      position: "absolute", left: 60, top: 80, maxWidth: "55%",
      fontFamily: "Space Grotesk", fontWeight: 700, fontSize: 96,
      lineHeight: 1.05, color: "#fff",
    }}>
      {title}
    </div>
  </AbsoluteFill>
);
```

Register it as a `<Still>` in `Root.tsx` (1280×720, YouTube thumbnail
aspect) if not already present, mirroring `template-still`'s `Root.tsx`.
Pull `bgColor`/`accentColor` defaults from
`assets/brand-kit/visual-identity.md` (Sprintz Orange etc.) rather than
hardcoding.

### 3c. Render one candidate per cutout

```bash
cd "$REMOTION_PROJECT"
for cutout in "$THUMB_DIR"/cutouts/*-cutout.png; do
  name=$(basename "$cutout" -cutout.png)
  npx remotion render Thumbnail "$THUMB_DIR/renders/$name.png" \
    --props="{\"cutoutPath\":\"$cutout\",\"title\":\"<TITLE>\",\"bgColor\":\"#1A120B\",\"accentColor\":\"#ED5724\"}"
done
```

Replace `<TITLE>` with the video's hook/title text (from the outline's
title, if available). `bgColor`/`accentColor` here default to Sprintz
Orange on the warm-dark brand palette — adjust per the actual video.

---

## Step 4 — Hand off to the human

List the rendered candidates in `$THUMB_DIR/renders/` and tell the user:

> N thumbnail candidates ready in `thumbnail-candidates/renders/`. Pick one
> (or ask for a re-render with a different title/frame/model) — nothing
> auto-publishes.

This is a manual pick, same as the review gates elsewhere in the
pipeline — it doesn't wire into `video-edit`'s state machine or its two
gates; it's an independent, on-demand skill you run whenever you want
thumbnail options, before or after finalize.

---

## Notes

- **Supersedes the "Photoshop-built thumbnail" line** in
  `video-edit/SKILL.md` Step 5 and in
  `optimal-config-architecture.md`'s Finalize & Publish node — update
  those references to point here once this is confirmed working, rather
  than running both a manual Photoshop pass and this skill.
- **Model choice**: `birefnet-general` vs `birefnet-portrait` — try both if
  a candidate frame's cutout looks rough on hair/edges; portrait mode
  trades general-subject robustness for sharper human-edge matting.
- **Not automated end-to-end on purpose**: title text and color props are
  passed explicitly per render rather than inferred, so you're never
  surprised by what text lands on a thumbnail — cheap to iterate, nothing
  guesses on your behalf.
