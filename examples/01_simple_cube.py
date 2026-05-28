"""Simplest sync-style script - runs in one shot, returns last expression."""

import bpy

# clear scene
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
cube = bpy.context.object
cube.name = "simple_cube"

print(f"created {cube.name} at {tuple(cube.location)}")

# Last expression -> JSON result
{"object": cube.name, "location": tuple(cube.location)}
