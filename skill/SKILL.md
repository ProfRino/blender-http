---
name: blender-http-skill
description: Use this skill whenever an agent needs to drive Blender through the local Blender HTTP plugin (default 127.0.0.1:9876). Covers the HTTP API, the SSE event stream, the injected OUTPUT/WORKSPACE/snapshot/audit/progress helpers, the generator build() script pattern, and an assembly-and-audit workflow for connected 3D models (buildings, towers, furniture, machines, structures, pipes, railings, stairs, vehicles, modular objects) — with a screenshot audit checklist for catching common AI-Blender errors before final output. Do not use the legacy ptrthomas/blender-agent on 5656 or the mcp__blender__* tools while this skill is active.
---

# Blender HTTP Skill

This skill teaches an agent how to drive Blender through the **Blender HTTP** plugin: a local HTTP add-on that runs Python in Blender's main thread with live SSE streaming, cancellable jobs, screenshots, and multi-view audit.

The skill is broad: the core plugin contract applies to any Blender work. The **assembly** and **audit** sections apply specifically when modelling connected geometry and verifying it visually.

---

## When to use

Use this skill when:

- Driving Blender via HTTP on port 9876 — any modelling, materials, lighting, rendering, animation, video editing
- Generating connected assemblies or structures (buildings, towers, furniture, machines, pipes, railings, stairs, vehicles, modular objects)
- Repairing AI-generated Blender geometry
- Auditing a scene visually from multiple viewpoints
- Capturing screenshots or renders programmatically

Do **not** use this skill when:

- Talking to a different Blender mechanism (the legacy `ptrthomas/blender-agent` on port 5656, or `mcp__blender__*` MCP tools). Only the HTTP plugin on **9876**.
- Running scripts that need internet access from Blender
- Deleting user files outside the `OUTPUT` workspace
- Executing untrusted Python

---

## The plugin in one screen

**Endpoint:** `http://127.0.0.1:9876`

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/` | Sync exec. Returns `{ok, output, result, error}`. |
| `POST` | `/jobs` | Async submit. Returns `{job_id, status}`. |
| `GET` | `/jobs/{id}` | Status snapshot. |
| `GET` | `/jobs/{id}/stream` | SSE stream of `started`, `step`, `stdout`, `progress`, `snapshot`, `audit`, `completed`, `failed`, `cancelled`. |
| `DELETE` | `/jobs/{id}` | Cooperative cancel. |
| `GET` | `/snapshot?mode=&save=` | Single image. PNG bytes (default) or JSON `{path, mode}` if `save` set. |
| `POST` | `/audit?mode=&dir=` | 6-view audit suite. Returns JSON `{dir, views}`. |
| `GET` | `/health` | Liveness. |

**Send a script:**

```bash
curl -s localhost:9876 --data-binary @script.py            # sync
python ..\blender-http\client\send.py script.py --stream   # async + SSE
```

---

## What every script gets (no imports needed)

The plugin injects these into the script's namespace:

| Name | Type | Purpose | Example |
|---|---|---|---|
| `bpy` | module | Blender Python API | standard |
| `WORKSPACE` | str | workspace root | path-relative ops |
| `OUTPUT` | str | `<WORKSPACE>/output/`, auto-created | `snapshot(f"{OUTPUT}/snap.png")` |
| `progress(current, total=None, label=None)` | callable | emit `progress` SSE event | `progress(3, 12, "column 3")` |
| `snapshot(path, mode="viewport")` | callable | save one image | `snapshot(f"{OUTPUT}/snap.png", mode="opengl")` |
| `audit(output_dir, mode="opengl", margin=1.4, lens=35)` | callable | 6-view suite with bbox-aware cameras | `audit(f"{OUTPUT}/audits/pass1")` |

Workspace resolution: N-panel override > `BLENDER_HTTP_WORKSPACE` env var > `~/blender_http` default.

---

## Two script styles

### Sync (one-shot)

The script runs in a single timer tick. UI freezes briefly. The last expression becomes `result`.

```python
import bpy
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1))
"cube made"
```

Good for quick edits, queries, scene introspection.

### Generator (streamed, progressive)

If the script defines `build()` returning a generator, the server runs one `next()` per timer tick. **Between ticks Blender's event loop runs** — viewport redraws, UI stays responsive, objects appear progressively, cancel works at every yield.

```python
import bpy

def build():
    yield "base"
    bpy.ops.mesh.primitive_plane_add(size=6)
    for i in range(4):
        yield f"column {i+1}/4"
        bpy.ops.mesh.primitive_cube_add(size=0.4, location=(i-2, 0, 1))
    yield "roof"
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 2))
```

Each `yield <label>` emits a `step` SSE event.

**Prefer the generator style for anything non-trivial.** It is the difference between "Blender freezes for 30 seconds" and "I watch the scene assemble in real time."

---

## Core workflow

For non-trivial work the agent should:

1. **Understand the request.** Identify whether it is assembly, organic modelling, animation, render setup, video editing, etc.
2. **For assemblies, write a plan first** (see [templates/assembly_plan_template.md](templates/assembly_plan_template.md)).
3. **Write one `build()` generator** with yields between meaningful steps.
4. **Send via `/jobs` + stream** so progress and stdout arrive live.
5. **If `failed`, patch and resend** — read the traceback in the `failed` event.
6. **Audit:** call `audit(f"{OUTPUT}/audits/<run>")` at the end of `build()`.
7. **Inspect the audit images** against the [checklist](#screenshot-audit-checklist).
8. **Repair if needed** and re-run.
9. **Only report success once the audit passes.**

---

## Assembly modelling rules

Apply when modelling connected geometry — buildings, frames, machines, furniture, vehicles, modular objects.

### 1. Plan before coding

List, before writing geometry:

- object names + types + dimensions + centre positions
- contact faces and required overlaps / clearances
- parent-child relationships
- expected bounding box
- audit views required

**Calculate** centre positions from dimensions and contact faces. Never guess placement when parts must connect.

### 2. Cubes / rectangular parts

`primitive_cube_add(size=2)` creates a 2x2x2 cube. Use a helper that sets `dimensions` then applies transforms so the object has clean scale:

```python
def create_box(name, center, dimensions, material=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    return obj
```

### 3. Cylinders / pipes / beams / rails between two points

Do **not** use Euler rotations for "from point A to point B" — they are fragile. Use vector alignment via quaternion:

```python
from mathutils import Vector

def create_cylinder_between_points(name, p1, p2, radius, material=None, vertices=32):
    p1, p2 = Vector(p1), Vector(p2)
    midpoint = (p1 + p2) / 2
    direction = p2 - p1
    length = direction.length
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=length, location=midpoint)
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat('Z', 'Y').to_euler()
    if material:
        obj.data.materials.append(material)
    return obj
```

### 4. Materials that actually render

`mat.diffuse_color` is the *viewport* color. To get a colour in Cycles / Eevee renders, set the **Principled BSDF Base Color**:

```python
def make_mat(name, color):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
    m.diffuse_color = color  # kept for Solid viewport mode
    return m
```

### 5. Connection rules

- Connected parts must actually touch.
- Use small **intentional overlaps** for realistic joints — `beam penetrates column by 0.02 m`, `rail penetrates post by 0.01 m`, `wall sits flush on floor with no visible gap`.
- Avoid large unrealistic intersections unless explicitly requested.

### 6. Naming + organisation

- Name every object clearly — `column_1`, `front_beam`, `roof_slab` — never leave `Cube.001`.
- Group related objects into collections when modelling more than a handful of parts: `bpy.data.collections.new("Columns")`.

---

## Audit workflow

Before declaring a model done, run the audit. The plugin's `audit()` does everything for you:

```python
audit(f"{OUTPUT}/audits/pass1", mode="opengl", margin=1.4)
```

This writes 6 PNGs to that folder, each rendered through a programmatically placed camera:

- `01_front.png`
- `02_back.png`
- `03_left.png`
- `04_right.png`
- `05_top.png`
- `06_isometric.png`

What the helper does:

- Computes scene bounding box from all visible mesh objects
- Places a camera per view at `distance = (max_dim / 2) / tan(fov/2) * margin`
- Lens 35 mm by default; bump margin to 1.6+ if you see cropping
- Aims each camera at scene centre
- Renders via `bpy.ops.render.opengl(view_context=False)` so no grid, gizmos, or other viewport overlays leak into the renders
- Removes each camera after its render — scene is left clean

### Optional joint close-up

The standard `audit()` doesn't include a joint close-up. Add one manually when a connection point matters:

```python
target = Vector((2.5, -1.5, 3.05))                                 # the joint
bpy.ops.object.camera_add(location=(3.0, -2.4, 3.7))
cam = bpy.context.object
cam.name = "_closeup"
cam.data.lens = 50
cam.data.clip_end = 1000
look = target - cam.location
cam.rotation_euler = look.to_track_quat('-Z', 'Y').to_euler()
bpy.context.scene.camera = cam
snapshot(f"{OUTPUT}/audits/pass1/07_joint_closeup.png", mode="opengl")
bpy.data.objects.remove(cam, do_unlink=True)
```

---

## Screenshot audit checklist

When reviewing the audit images, check for these classic AI-Blender errors. **Do not report the model as complete if any of these are visible.**

1. Floating or disconnected parts
2. Exploded assembly
3. Wrong scale (cube too big, radius vs diameter confusion)
4. Wrong rotation (cylinders/beams not aligned)
5. Unwanted intersections
6. Gaps at joints
7. Duplicated objects
8. Origin / anchor problems
9. Materials missing or wrong (still gray when they should be coloured -> wrong shading mode or missing Principled BSDF)
10. Lighting too dim or blown out
11. Camera too close / object cropped at edges
12. Missing components (compare against assembly plan)
13. Black or empty render
14. Clipping issues (near / far planes)
15. Object hidden behind another
16. Model not centred in frame
17. Top view shows only the roof — use isometric for structural check
18. Audit cameras / gizmos leaking into renders (should not happen — `audit()` uses `view_context=False` by default)

---

## Repair loop

When you find an issue:

1. Identify it clearly: which view, which object, which checklist item.
2. Locate the most likely cause in the code.
3. Patch the script.
4. Resend (use `POST /jobs` + stream so you see progress + new audit events live).
5. Re-run the audit (a new run name keeps history).
6. Iterate until all checks pass, or ask the user for a design decision.

| Common issue | Likely cause | Fix |
|---|---|---|
| Floating part | wrong centre / contact face math | recompute from contact face |
| Exploded assembly | scene cleared mid-build, units mismatch | clear at start only, check metric units |
| Wrong scale | radius vs diameter, unit error | halve / double, re-check |
| Wrong rotation | Euler instead of vector alignment | use `to_track_quat` |
| Cropped render | model larger than expected | `margin=1.6` or higher |
| Missing material | forgot to call `make_mat()` or `.materials.append()` | assign in the create helper |
| Duplicate geometry | re-ran without clearing | clear at top of `build()` |

---

## Output workspace

Every generated artefact should land under `OUTPUT`. Standard layout the plugin creates and the skill follows:

```
<WORKSPACE>/                          (default ~/blender_http/)
└── output/                           = OUTPUT
    ├── snapshots/                    (single ad-hoc images)
    ├── audits/<run_name>/            (audit suites)
    └── renders/                      (final renders)
```

Scripts should never hardcode paths. Always use `OUTPUT`:

```python
snapshot(f"{OUTPUT}/snapshots/preview.png", mode="opengl")
audit(f"{OUTPUT}/audits/pavilion_v3")
scene.render.filepath = f"{OUTPUT}/renders/hero.png"
bpy.ops.wm.save_as_mainfile(filepath=f"{OUTPUT}/scene.blend")
```

---

## Safety rules

Scripts run via Blender HTTP must not:

- Delete arbitrary local files. Write only under `OUTPUT`.
- Access the internet from inside Blender.
- Run shell commands.
- Read sensitive local files.
- Install Python packages.
- Bind the server beyond `127.0.0.1`.
- Execute untrusted user-supplied code.

The plugin server binds to localhost only. Do **not** expose port 9876 to the network.

---

## What this skill is *not*

This skill is broad on the plugin contract and detailed on assembly + audit. For other domains (organic sculpting, geometry nodes, full animation rigs, video editing in the VSE, compositing) the **same plugin contract works** — generator `build()`, `OUTPUT`, `snapshot()`, etc. — but the assembly-specific helpers above (`create_box`, `create_cylinder_between_points`) and the audit checklist don't all apply. Write domain-appropriate helpers in those cases.

---

## Files in this skill

```
blender-http-skill/
├── SKILL.md                              (this file)
├── README.md                             (orientation)
├── examples/
│   └── connected_scene_with_audit.py     (full assembly + audit demo)
├── scripts/
│   └── generated_scene.py                (drop generated scripts here)
└── templates/
    ├── assembly_plan_template.md         (use before coding)
    └── audit_report_template.md          (use after auditing)
```

## Related

- Plugin source: `../` (the parent folder of this skill)
- Plugin protocol spec: `../docs/protocol.md`
- Plugin design notes: `../docs/design.md`
- Plugin examples: `../examples/`
- Plugin client: `../client/send.py` (`send.ps1` on Windows)

## Credits

This skill replaces an earlier version (`blender-http-assembly-skill`, port 5656) that targeted the legacy `ptrthomas/blender-agent` HTTP bridge. The new plugin is independently written and adds streaming, generator step execution, cancellation, snapshots, and multi-view audit. Earlier inspiration:

- [ptrthomas/blender-agent](https://github.com/ptrthomas/blender-agent) — HTTP bridge concept
- Prof Rino's Blender MCP Assembly Skill — assembly-first modelling rules
