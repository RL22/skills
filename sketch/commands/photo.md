# sketch photo

Turn a finished, clean render into a photo of a real notebook page — paper curl, soft shadow, pen sheen —
for hero images. Runs after another command; its output varies run to run, so the render stays the
source of truth.

## Steps

1. Start from a **clean** PNG render (see SKILL.md) at `--scale 2` or higher.
2. Give it to an image model that edits from a reference image and preserves text (e.g. GPT Image or
   Gemini image editing), with the layout locked:
   > Using this image as the exact layout reference, produce a photo of this sketch on a cream notebook page lying
   > on a desk, soft daylight. Keep every drawn element and every word exactly as drawn.
3. Compare the photo against the render: every word, arrow, and hatched button present and legible.

## Checks

- The words and marks match the render one-for-one; any drift means reroll or ship the render instead.
