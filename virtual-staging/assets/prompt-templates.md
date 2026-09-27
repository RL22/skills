# Prompt Templates

Execution rules for every staging template below: pass the source photo as an image input (edit mode), match the source aspect ratio, request the largest supported output, and use camera-relative placement language only. The 2x2 and 1x1 grid templates are style-exploration artifacts, never listing deliverables — final and consistency work is always one photo per call.

Determinism rules (see the five-block skeleton below):
- Enforce by API parameter what a parameter can enforce: set `imageConfig.aspectRatio` instead of describing the ratio in prose, and fix `generationConfig.seed` so identical input + identical prompt reproduces closely (not guaranteed bitwise).
- Every added object gets count + material + color + form + camera-relative position. No "or", no "such as", no open nouns ("minimal decor", "a small plant") — each one is a fork the model resolves differently per run.
- Close the set: end every ADD manifest with "Nothing else. No objects beyond this list."
- Phrase constraints positively ("keep the sconces fully visible"), keep one generic architectural ban; long specific "do not add X" lists prime the model with X.
- Identity across views comes from the chained reference image, not adjectives. Adjectives get a similar sofa; a reference image gets the same sofa.

## Floor Plan Schematic

```text
Create a clean 2D schematic floor plan from the approved structured plan only.
Follow the approved topology exactly. Use simple black walls on a white background.
Keep proportions approximate but preserve room relationships, wall openings, windows, doorways, labels, and photo viewpoint markers.
Do not add rooms, remove rooms, change orientation, create a 3D rendering, or make it decorative.
If furniture is requested, add only simple furniture blocks that support later staging decisions.
```

## 2x2 Style Tile Grid

Before using this template, ask the user which four styles they want to compare. If they want the recommended defaults, use:

- Top Left: Boho Warm Minimal
- Top Right: Mid-Century Modern
- Bottom Left: Scandinavian Neutral
- Bottom Right: Organic Modern Luxury

```text
Create a 2x2 virtual staging concept tile from this property photo.
Preserve the exact property architecture and physical features: room layout, wall placement, windows, doors, trim, flooring, ceiling height, built-ins, cabinets, countertops, appliances, permanent fixtures, and natural light direction. Do not renovate, remodel, repaint, change finishes, or alter the property itself.
Add realistic furniture and decor as if an Architectural Digest staging team designed the property for a premium real estate listing. Keep furniture naturally scaled, realistic, and aligned with the original camera perspective.
Use the four user-selected staging presets:
Top Left: [STYLE 1]
Top Right: [STYLE 2]
Bottom Left: [STYLE 3]
Bottom Right: [STYLE 4]
Each quadrant should feel polished, editorial, move-in ready, and suitable for helping market the space faster. The final image should be a clean 2x2 comparison grid.
```

## 1x1 Side-by-Side Comparison

Before using this template, ask the user which two styles they want to compare (or if they want to compare a single style to the original photo). Offer a default set like Boho Warm Minimal and Mid-Century Modern if they want a shortcut.

```text
Create a 1x1 side-by-side comparison image from this property photo.
Preserve the exact property architecture and physical features: room layout, wall placement, windows, doors, trim, flooring, ceiling height, built-ins, cabinets, countertops, appliances, permanent fixtures, and natural light direction. Do not renovate, remodel, repaint, change finishes, or alter the property itself.
Add realistic furniture and decor as if an Architectural Digest staging team designed the property for a premium real estate listing. Keep furniture naturally scaled, realistic, and aligned with the original camera perspective.
Show two variations side-by-side:
Left: [STYLE 1 or Original Photo]
Right: [STYLE 2]
The final image should be a clean side-by-side comparison of the two options.
```

## Multi-Photo Consistency (Sequential Chaining)

Do not ask the model to generate a consistency grid — stage each view individually and compose the contact sheet locally (see workflows.md). For every view after the approved hero, pass two image inputs: this view's source photo and the approved hero render.

Chained views use the same five-block skeleton, with the ADD manifest reduced to placement-only lines pointing at the reference:

```text
TASK: Edit the first image — not a new render. The second image is an approved staged view of the same apartment and is the furniture reference. Stage the first image in the same [STYLE] direction, reusing the exact furniture pieces from the reference — same shapes, materials, wood tones, and fabrics. Keep the exact framing, camera perspective, and existing lighting of the first image.

PRESERVE exactly as photographed in the first image: [NAMED FEATURE INVENTORY]. No renovation, repainting, or new architectural features of any kind.

ADD (placement of reference furniture only):
1. [e.g. "The cream boucle sofa from the reference — now seen from behind, lower-left of frame."]
2. [...]
Nothing else. No furniture or decor that is not in the reference image.

CONSTRAINTS: Keep the [key features, doorways, and walking paths] fully visible. Natural scale, correct perspective, real floor contact and shadows.

FINISH: Bright, airy, professional real-estate photograph, matching the reference image's staging exactly.
```

## Per-View Staging — Five-Block Skeleton (canonical)

The canonical template for every hero and final render. Fixed block order; between views of the same set, only the ADD block changes. Fill [NAMED FEATURE INVENTORY] with the actual visible permanent features of this photo (e.g. "the two windows with white horizontal blinds, the white radiator cover between them, the wall sconce on the left wall, the ornate crown molding, the pale blue wall color, the oak floor and its plank direction, the outlets and their positions").

```text
TASK: Edit this photo — not a new render. Virtually stage it in a [STYLE PRESET] direction as if a premium staging team designed it for a real estate listing. Keep the exact framing, camera perspective, and existing lighting of the source photo.

PRESERVE exactly as photographed: [NAMED FEATURE INVENTORY]. No renovation, repainting, or new architectural features of any kind.

ADD (exact manifest):
1. [One object per line: count + material + color + form — camera-relative position, e.g. "One queen platform bed, low pale-oak frame, warm white linen bedding — headboard centered on the far wall between the two sconces, both sconces fully visible."]
2. [...]
Nothing else. No objects beyond this list.

CONSTRAINTS: Keep the [key features, doorways, and walking paths] fully visible. Natural scale, correct perspective, real floor contact and shadows.

FINISH: Bright, airy, professional real-estate photograph, accurate to the property.
```

## Corrective Retry (After Failed Self-QC)

Use when a render violated the fidelity contract. Resend the original five-block prompt VERBATIM — do not rewrite or reshuffle it, or you cannot tell whether the fix or the reshuffle changed the result — and prepend one corrective block naming the violation:

```text
CORRECTION: The previous attempt had these errors: [SPECIFIC VIOLATIONS, e.g. "the white radiator cover between the two windows was removed", "a ceiling light was added that does not exist"]. Fix these while keeping everything else identical.

[ORIGINAL FIVE-BLOCK PROMPT, VERBATIM]
```

## AD-Style Master Prompt

Style-exploration shortcut only — its open nouns are non-deterministic by design. Never use for finals or consistency sets; use the five-block skeleton instead.

```text
Virtually stage this property photo as if an Architectural Digest interior design team styled the space for a premium real estate listing. Preserve the exact architecture, room layout, floor plan, windows, doors, trim, flooring, wall color, ceiling height, built-ins, cabinets, countertops, appliances, fixtures, and natural light direction. Do not renovate or alter the property itself.
Add tasteful, realistic furniture and decor that fits the room's scale, perspective, and lighting. Make the space feel aspirational, livable, premium, warm, and move-in ready. Use high-end editorial styling, natural materials, layered textures, beautiful proportions, and realistic real estate photography polish.
The final image should look like a professionally staged property listing photo, not a fantasy render or AI redesign.
```

## Cross-Photo Verification

```text
Perform cross-photo verification across all provided property staging photos.
1. Map each photo to an estimated standing position and view direction (cardinal or relative direction).
2. Reconcile shared boundaries: identify doors, windows, structural columns, and wall partitions that appear in multiple photos.
3. Verify entry/exit points: confirm which door represents the main front entry, and ensure it is not mislabeled as a closet, pantry, or utility door when seen from different rooms.
4. Construct a consistent, single-floorplan topology that resolves all overlaps and perspective variations.
5. List any remaining spatial conflicts or ambiguities as uncertainties.
```

