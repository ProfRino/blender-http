# Assembly Plan Template

Fill this out **before** writing the Blender Python. Translates the user's request into a concrete object/connection/audit plan that the `build()` generator can implement.

## Model request

One sentence describing what is being modelled and why.

## Objects

| Object | Type (primitive) | Dimensions (X, Y, Z) | Centre position | Material | Notes |
|---|---|---:|---:|---|---|
| base_slab | cube | 6.0, 4.0, 0.2 | (0, 0, 0.1) | concrete | sits flush on ground |

## Connections

| Connection | Contact faces | Required overlap / clearance | Verification method |
|---|---|---:|---|
| column -> slab | column bottom, slab top | overlap 0.0 (flush) | visual audit + bounds check |
| beam -> column | beam side, column top | overlap 0.02 m | visual audit |

## Bounding box estimate

- Minimum corner:
- Maximum corner:
- Centre:
- Maximum dimension:

## Camera framing

- Lens (mm): 35 (default; increase for tighter framing, decrease for wider)
- Margin: 1.4 (default; bump to 1.6 if cropping)
- Audit views: front, back, left, right, top, isometric (the default `audit()` suite)
- Joint close-ups: list any junctions needing a manual `snapshot()`

## Output

- Audit directory: `f"{OUTPUT}/audits/<run_name>"`
- Final render path (if any): `f"{OUTPUT}/renders/<run_name>.png"`
- Save .blend to: `f"{OUTPUT}/audits/<run_name>/<name>.blend"`

## Script outline

Rough `build()` outline as a list of yield steps:

1. "scene cleared"
2. "base slab"
3. "column 1/N", "column 2/N", ...
4. "beams"
5. "roof slab"
6. "lights"
7. "audit -> {OUTPUT}/audits/<run>"
8. "joint close-up" (optional)
9. "done"

## Known risks

- Camera too close -> model cropped
- Floating parts (wrong centre / contact face math)
- Wrong rotation (use vector alignment for cylinders, not Euler)
- Scale errors (cube size vs dimensions confusion)
- Gaps at joints
- Unwanted intersections
- Materials not assigned, or only `diffuse_color` set (won't show in render -- use Principled BSDF base color)
- Duplicate geometry (forgot to clear scene at top of `build()`)
