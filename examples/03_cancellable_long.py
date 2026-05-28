"""Long, cancellable job. Submit, then DELETE /jobs/{id} mid-flight.

Each step adds a UV sphere along the X axis. Watch them appear one at a time.
Cancel from the N-panel, or:

    Invoke-WebRequest -Uri http://127.0.0.1:9876/jobs/<id> -Method DELETE
"""

import bpy


def build():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    yield "cleared"

    TOTAL = 50
    for i in range(TOTAL):
        yield f"sphere {i+1}/{TOTAL}"
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=0.15,
            location=(i * 0.4 - (TOTAL * 0.4 / 2), 0, 0.5),
            segments=16, ring_count=8,
        )
        progress(i + 1, TOTAL, f"sphere {i+1}")
