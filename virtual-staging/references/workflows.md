# Workflows

## Mode 1: Listing Photo Polish

Use for factual real estate listing photos where the property must remain exactly as-is.

Allowed changes:
- Crop
- Lighting
- Exposure
- White balance
- Perspective
- Sharpness
- Contrast
- Lens correction

Not allowed:
- Adding furniture
- Removing furniture
- Changing finishes
- Changing fixtures
- Restyling the room

## Mode 2: AD-Style Virtual Staging

Use for empty spaces, vacant homes or apartments, underwhelming listing photos, premium listing concepts, property manager or broker marketing assets, landing pages, social posts, and before/after reels.

Preserve room architecture, floor plan, window placement, wall color, flooring, cabinets, countertops, appliances, built-ins, doors, trim, ceiling height, and natural light direction. Add only removable furniture and decor unless the user explicitly asks for renovation concepts.

## Assessment-First Choice

After analyzing a photo, ask the user how they would like to proceed with the visual sample and recommendations:

```text
I've assessed the photo. Would you like the recommendations as:

1. Text Recommendations - a clear breakdown of what would improve the photo and staging direction.
2. Visual Staging Sample - generate visual concepts. Please select your preferred format:
   - Option A: Single Image (1 style variation)
   - Option B: 1x1 Side-by-Side comparison (2 style variations or before/after side-by-side)
   - Option C: 2x2 Tile Grid (4 style variations in a grid)

Default recommendation: Choose a Visual Staging Sample (e.g., Option C: 2x2 Tile Grid) if you want fast visual direction before selecting a final staging concept.
```

If the user chooses a Visual Staging Sample, ask them to select their preferred format (Option A, B, or C) and choice of styles from [presets.md](presets.md). Offer default style sets for 1x1 or 2x2 layouts as a shortcut (e.g., Boho Warm Minimal and Mid-Century Modern for 1x1; Boho Warm Minimal, Mid-Century Modern, Scandinavian Neutral, and Organic Modern Luxury for 2x2).

## Text Recommendation Output

```text
## Photo Assessment

This space has the strongest market potential if we emphasize:
- [Natural light / floor space / windows / hardwood floors / modern kitchen / open layout]
- [Any visual advantage]
- [Any buyer or renter-facing selling point]

## Recommended Staging Direction

Recommended preset: [Style Name]
Why:
- [Reason 1]
- [Reason 2]
- [Reason 3]

## Suggested Furniture Plan

- Sofa:
- Rug:
- Coffee table:
- Lighting:
- Art:
- Plants/decor:

## Listing Photo Enhancements

- Correct vertical lines.
- Brighten exposure.
- Balance white balance.
- Use a wider, cleaner crop.
- Preserve realistic room scale.

## Conversion Note

This direction should help the space feel more premium, move-in ready, and emotionally easier for prospective occupants to imagine living in.
```

## Floor Plan Workflow

1. Perform cross-photo verification to map camera positions, view directions, and shared boundaries directly from photo assets.
2. Reconstruct the room layout and floor plan relationships into a structured spec. If a sketch is provided, integrate it to resolve details. Do not request a sketch unless multiple cross-photo verification attempts fail to resolve the layout.
3. Stop for approval and correction.
4. Render a clean 2D schematic from the approved spec only.
5. Stop for approval again before using the plan to guide staging.

Never ask an image model to directly recreate a sketch or drawing when fidelity matters.

If a structured layout (either via cross-photo verification or a sketch) is approved or corrected by the user to lock details, treat those details as locked. Do not use photos to re-map windows, marker positions, marker directions, or topology after that point.

If the user says "proceed" after corrections, continue only to the next clear approval gate. If the next artifact is not explicit, ask whether they want the schematic, SVG, staged preview, or final images before creating anything.

## Multi-Photo Consistency Workflow

Use this when the user has already selected a style across multiple listing photos:

1. Create a furnished floor plan or staging map if needed, then translate it into camera-relative placement notes per view (image prompts must not contain compass directions).
2. Prepare source photos deterministically (EXIF rotation, exposure, verticals) — no generative enhancement.
3. Stage the **hero view** first: one photo, one call, edit mode, source aspect ratio, per-photo feature inventory in the prompt. Self-QC against the source, then stop for approval.
4. Stage each remaining view one at a time, passing the view's source photo plus the approved hero as a furniture identity reference. Self-QC each output.
5. Compose a contact sheet locally (PIL/ImageMagick — never a model-generated grid) and stop for approval.
6. Generate any remaining high-resolution finals using the approved direction, one view per call.

Local contact sheet (PIL):

```bash
python3 - <<'EOF'
from PIL import Image
paths = ["staged_03.png", "staged_05.png", "staged_09.png", "staged_12.png"]
imgs = [Image.open(p) for p in paths]
h = min(i.height for i in imgs)
imgs = [i.resize((int(i.width * h / i.height), h)) for i in imgs]
cols = 2
rows = (len(imgs) + cols - 1) // cols
w = max(i.width for i in imgs)
sheet = Image.new("RGB", (w * cols, h * rows), "white")
for n, i in enumerate(imgs):
    sheet.paste(i, ((n % cols) * w, (n // cols) * h))
sheet.save("consistency-contact-sheet.png")
EOF
```
