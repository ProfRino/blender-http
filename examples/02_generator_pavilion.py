"""Generator-style: each yield is a step. Objects appear progressively.

Run with streaming to feel the difference:
    python client/send.py examples/02_generator_pavilion.py --stream
"""

import bpy


def _mat(name, color):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = color
    m.diffuse_color = color
    return m


def _box(name, center, dims, mat=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dims
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        obj.data.materials.append(mat)
    return obj


def build():
    # Clear
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.materials):
        bpy.data.materials.remove(m)
    yield "scene cleared"

    concrete = _mat("Concrete", (0.72, 0.70, 0.66, 1.0))
    steel = _mat("Steel", (0.22, 0.24, 0.28, 1.0))
    accent = _mat("Accent", (0.85, 0.35, 0.15, 1.0))

    yield "base slab"
    _box("base", (0, 0, 0.1), (6, 4, 0.2), concrete)

    columns = [(-2.5, -1.5), (2.5, -1.5), (-2.5, 1.5), (2.5, 1.5)]
    for i, (x, y) in enumerate(columns, start=1):
        yield f"column {i}/4"
        _box(f"col_{i}", (x, y, 1.7), (0.25, 0.25, 3.0), steel)
        progress(i, len(columns), f"placing column {i}")

    yield "front beam"
    _box("front_beam", (0, -1.5, 3.05), (5.4, 0.18, 0.22), accent)
    yield "back beam"
    _box("back_beam", (0, 1.5, 3.05), (5.4, 0.18, 0.22), accent)
    yield "left beam"
    _box("left_beam", (-2.5, 0, 3.05), (0.18, 3.4, 0.22), accent)
    yield "right beam"
    _box("right_beam", (2.5, 0, 3.05), (0.18, 3.4, 0.22), accent)

    yield "roof slab"
    _box("roof", (0, 0, 3.3), (6, 4, 0.2), concrete)

    print("pavilion complete")
    yield "done"
