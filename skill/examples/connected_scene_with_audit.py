"""Assembly + audit demo using the Blender HTTP plugin.

Sends progressively (one yield per timer tick), captures the canonical 6-view
audit suite via the injected `audit()` helper, and adds a manual joint close-up.

Run with:
    python ..\\blender-http\\client\\send.py examples\\connected_scene_with_audit.py --stream

Outputs land in: <WORKSPACE>/output/audits/pavilion/
"""

import bpy
from mathutils import Vector


# ---- helpers ---------------------------------------------------------------

def make_mat(name, color):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
    m.diffuse_color = color
    return m


def create_box(name, center, dimensions, material=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        obj.data.materials.append(material)
    return obj


def create_cylinder_between_points(name, p1, p2, radius, material=None, vertices=32):
    p1, p2 = Vector(p1), Vector(p2)
    midpoint = (p1 + p2) / 2
    direction = p2 - p1
    length = direction.length
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=length, location=midpoint
    )
    obj = bpy.context.object
    obj.name = name
    obj.rotation_euler = direction.to_track_quat("Z", "Y").to_euler()
    if material:
        obj.data.materials.append(material)
    return obj


def add_light(name, kind, location, energy):
    bpy.ops.object.light_add(type=kind, location=location)
    light = bpy.context.object
    light.name = name
    light.data.energy = energy
    return light


# ---- build -----------------------------------------------------------------

def build():
    # Clear scene
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    yield "scene cleared"

    # Materials (Principled BSDF, render-visible)
    concrete = make_mat("Concrete", (0.65, 0.65, 0.65, 1))
    steel = make_mat("Steel", (0.25, 0.25, 0.28, 1))
    blue = make_mat("BluePanels", (0.10, 0.25, 0.80, 1))

    # Base slab
    yield "base slab"
    create_box("base_slab", (0, 0, 0.1), (6, 4, 0.2), concrete)

    # Four columns on the slab
    columns = [(-2.5, -1.5), (2.5, -1.5), (-2.5, 1.5), (2.5, 1.5)]
    for i, (x, y) in enumerate(columns, start=1):
        yield f"column {i}/4"
        create_box(f"column_{i}", (x, y, 1.7), (0.25, 0.25, 3.0), steel)
        progress(i, len(columns), f"column {i}")

    # Cross beams (slight overlap into columns)
    yield "front beam"
    create_box("front_beam", (0, -1.5, 3.05), (5.4, 0.18, 0.22), steel)
    yield "back beam"
    create_box("back_beam", (0, 1.5, 3.05), (5.4, 0.18, 0.22), steel)
    yield "left beam"
    create_box("left_beam", (-2.5, 0, 3.05), (0.18, 3.4, 0.22), steel)
    yield "right beam"
    create_box("right_beam", (2.5, 0, 3.05), (0.18, 3.4, 0.22), steel)

    # Diagonal braces -- vector-aligned cylinders
    yield "front diagonal brace"
    create_cylinder_between_points("front_diag", (-2.5, -1.62, 0.4), (2.5, -1.62, 3.0), 0.05, blue)
    yield "back diagonal brace"
    create_cylinder_between_points("back_diag", (-2.5, 1.62, 3.0), (2.5, 1.62, 0.4), 0.05, blue)

    # Roof slab
    yield "roof slab"
    create_box("roof_slab", (0, 0, 3.3), (6, 4, 0.2), concrete)

    # Lights
    yield "lights"
    add_light("Sun", "SUN", (5, -5, 8), 3.0)
    add_light("Fill", "AREA", (0, -4, 6), 400.0)

    # Audit -- automatic 6-view suite
    out_dir = f"{OUTPUT}/audits/pavilion"
    yield f"audit -> {out_dir}"
    audit(out_dir, mode="opengl", margin=1.4)

    # Joint close-up (not part of the standard suite)
    yield "joint close-up"
    target = Vector((2.5, -1.5, 3.05))   # front-right column / beam junction
    bpy.ops.object.camera_add(location=(3.0, -2.4, 3.7))
    cam = bpy.context.object
    cam.name = "_closeup"
    cam.data.lens = 50
    cam.data.clip_end = 1000
    look = target - cam.location
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    snapshot(f"{out_dir}/07_joint_closeup.png", mode="opengl")
    bpy.data.objects.remove(cam, do_unlink=True)

    # Save the .blend alongside the audit
    bpy.ops.wm.save_as_mainfile(filepath=f"{out_dir}/pavilion.blend")

    print(f"pavilion + audit complete: {out_dir}")
    yield "done"
