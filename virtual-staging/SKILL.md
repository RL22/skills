---
name: virtual-staging
description: Virtual staging for real estate. Enforces multi-angle fidelity via strict masking (PWA) and exact-manifest prompts. Preserves original architecture.
author: "Sprintz"
date_added: "2026-09-05"
---

# Virtual Staging

## Quick Start

Use this for real estate listing visuals built from photos and optional layout sketches. Prioritize spatial fidelity and strict determinism. Load [references/workflows.md](references/workflows.md) for step-by-step processes, [references/presets.md](references/presets.md) for style directions, and [assets/prompt-templates.md](assets/prompt-templates.md) for reusable templates.

Anchor multi-angle consistency structurally. Mandate a **smart mask** (generated via the local PWA) before running any generative staging.

## Floor Plan Fidelity

Before generating floor plans, output this structured interpretation using Markdown tables:

Orientation:
| Side | Observed feature | Confidence | Notes |
| --- | --- | --- | --- |
| Top |  |  |  |

Rooms:
| Room name | Position | Approximate size | Connections | Windows | Doors/openings | Notes |
| --- | --- | --- | --- | --- | --- | --- |

Markers:
| Marker | Location | Direction | Corresponding source photo | Confidence | Notes |
| --- | --- | --- | --- | --- | --- |

Uncertainties:
- List items that cannot be confidently read.

Rules: Preserve topology exactly. Mark ambiguous details as uncertain. 
- **Cross-Space Verification**: Reconcile boundaries visible in multiple photos. Ensure primary access points are consistently identified.

After approval, render exclusively from the approved structured plan. Use [assets/svg-floor-plan-template.md](assets/svg-floor-plan-template.md) for inline SVG output.

## Virtual Staging Rules

Preserve permanent property features exactly: room layout, windows, blinds, doors, trim, baseboards, crown molding, flooring, wall color, ceiling lights, outlets, fixtures, cabinets, and appliances.

Retain existing finishes exactly. Execute renovations only when explicitly requested as a renovation concept.

Staging plausibility: Place furniture clear of windows, radiators, vents, doorways, and walking paths.

## Photo Prep: Clean Plate

Prepare source photos with deterministic tools only (`sips`, ImageMagick). 
Create a **clean plate** by explicitly removing unwanted debris (like cables or trash) via targeted inpainting before placing any staging assets. 

Stage exclusively from the unedited original at its native aspect ratio.

## Execution: Smart Masking

These rules govern every staging generation call to ensure cross-view fidelity:

1. **One photo per call.** Compose comparison grids locally from individually staged images.
2. **Edit mode.** Execute exclusively in edit/inpainting mode upon the source photo.
3. **Aspect ratio.** Match the source aspect ratio.
4. **Camera-relative placement.** Translate the approved plan into each photo's viewpoint (e.g., "left of frame", "in front of the far wall").
5. **Structural Anchoring.** Secure multi-angle consistency by generating strict B/W bounding box masks via the local Smart Masking PWA. Pass this mask to the backend to constrain the render geometry.

## Per-Photo Fidelity Contract

For each view:
1. **Inventory:** Catalog visible permanent features (windows, radiator covers, sconces, outlets, trim, flooring) and name them explicitly in the prompt.
2. **Self-QC:** After generating, compare side-by-side against the source. Verify:
   - Aspect ratio and framing match.
   - Window count, position, and blinds match.
   - Radiator covers, sconces, outlets, and fixtures match.
   - Wall color, trim, and floor match.
   - Furniture scale is plausible and paths are clear.
3. **Completion:** On failure, retry up to twice with a corrective delta prompt naming the specific violation. Halt and request human review after two corrective failures.

## Final Image Prompt: Exact Manifest

Use a strict **exact manifest** to suppress hallucinated decor. Fill `[NAMED FEATURE INVENTORY]` with actual visible permanent features and `[CAMERA-RELATIVE PLACEMENT NOTES]` with viewpoint-translated furniture placement.

```text
EDIT the existing local file [FILENAME] in this directory. Apply mask [MASK_FILENAME]. Pass aspect_ratio [ASPECT_RATIO] matching the input photo's framing exactly. Save the result as [OUTPUT_FILENAME]. Apply exactly this edit:

TASK: Edit this photo. Virtually stage it in a [STYLE] direction as if a premium staging team designed it for a real estate listing. Keep the exact framing, camera perspective, and existing lighting of the source photo.

PRESERVE exactly as photographed: [NAMED FEATURE INVENTORY]. 

ADD (exact manifest):
[CAMERA-RELATIVE PLACEMENT NOTES - e.g., 1. One low three-seat sofa...]
Nothing else. No objects beyond this list.

CONSTRAINTS: Keep the windows, radiators, doors, and walking paths fully visible. Natural scale, correct perspective, real floor contact and shadows.

FINISH: Bright, airy, professional real-estate photograph, accurate to the property.
```

## Approval Gates

Stop and request approval after:
1. The structured floor-plan interpretation.
2. The clean schematic floor plan.
3. The staged preview sample (single view or locally composed contact sheet).
4. The final high-resolution staged images.
