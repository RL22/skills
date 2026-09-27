# SVG Floor Plan Template

Use this template after the user approves the structured floor-plan interpretation. Create a clean inline SVG staging floor plan from the approved plan, using the original sketch (if provided) only as visual reference.

## Visual Direction

- Black background
- Light gray or off-white walls
- Thin architectural linework
- Minimal modern property floor plan aesthetic
- Simple room labels
- Clean map-style symbols
- White or light-gray outlines
- Subtle gray fills for fixtures or furniture zones
- Professional leasing or staging presentation quality

## Fidelity Rules

- If the user says the sketch or approved layout is correct, authoritative, exact, or that markers/windows are placed exactly, copy those details from the approved spec. Do not reinterpret them from photos.
- Preserve the approved topology from the structured plan.
- Preserve approximate proportions from the sketch (if provided) or cross-photo verification when measurements are missing.
- Do not claim exact dimensions unless the user provided them.
- Do not invent rooms, resize spaces arbitrarily, or change orientation.
- Do not add room types unless they are visible in the sketch (if provided), source photos, or approved by the user.
- If a detail remains ambiguous, omit it or label it as uncertain instead of guessing.
- Preserve user-corrected window count, marker placement, and marker direction exactly.

## Elements to Convert (from Sketch or Cross-Photo Verification)

The source materials may include:

- Room outlines
- Doorways
- Windows
- Kitchen or bathroom fixtures
- Photo reference numbers
- Standing-position markers
- Direction-facing arrows for each photo

## Required SVG Elements

1. Property walls and room boundaries
2. Door openings and doorway swings where indicated
3. Windows labeled clearly
4. Room labels only where known or approved
5. Photo-position markers using numbered circles
6. Direction arrows showing where the camera was facing for each photo
7. A map-style legend explaining all symbols
8. Optional staging-zone labels if useful and approved

## Photo Marker Style

- Use a numbered circle for each photo reference: 1, 2, 3, etc.
- Place the circle where the user was standing.
- Add a directional arrow from the circle showing where the camera was facing.
- Keep markers visible but not distracting.
- Use one consistent warm accent color for all photo markers and camera arrows.

## Legend

Include entries for:

- Photo position marker
- Camera direction arrow
- Window
- Doorway or door swing
- Main entry
- Room label
- Optional staging zone

## Output Requirements

- Return valid inline SVG only.
- Use a scalable `viewBox`.
- Use semantic SVG groups with IDs such as `walls`, `windows`, `doors`, `photo-markers`, `labels`, and `legend`.
- Use clean vector paths, rects, lines, polygons, and text.
- Do not rasterize sketches.
- Do not include external fonts, images, or dependencies.
- Keep the design readable at thumbnail and full size.
- Use comments in the SVG to separate major sections.

## Default Visual Style

- Background: black
- Walls: off-white thick strokes
- Interior lines: medium gray
- Fixtures/furniture zones: dark gray fill with light gray stroke
- Labels: off-white or light gray
- Photo markers: warm accent color
- Camera arrows: same warm accent color
- Legend box: black fill with off-white border

## Prompt

```text
Create a clean inline SVG staging floor plan from the approved structured floor-plan interpretation.

Use the hand-drawn sketch (if provided) only as a visual reference and follow the approved structure exactly. If the user has said the sketch or layout is authoritative, copy its window count, marker placement, and marker directions exactly. Preserve topology, room relationships, wall openings, window positions, doorways, labels, photo-position markers, and camera-direction arrows. Preserve approximate proportions where measurements are missing, but do not claim exact dimensions.

Use a black-background professional leasing or listing presentation style with off-white walls, thin architectural linework, light gray labels, dark gray fixture or furniture-zone fills, and warm accent photo markers.

Return valid inline SVG only. Use a scalable viewBox and semantic groups with IDs for walls, windows, doors, photo-markers, labels, and legend. Do not rasterize sketches. Do not include external fonts, images, or dependencies.
```
