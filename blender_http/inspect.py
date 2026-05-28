"""Scene introspection helpers.

Compact, agent-friendly JSON summaries of the current Blender scene. Cheap
to call repeatedly; no I/O. Use instead of falling back to mcp__blender__*.
"""

import fnmatch
import hashlib
import json
from typing import Optional

import bpy
from mathutils import Vector


def inspect(detail: str = "brief") -> dict:
    """Return a compact summary of the current scene.

    detail = "brief" -> name, type, location only (smallest payload)
    detail = "full"  -> + rotation, scale, dimensions, materials, hide state, parent
    """
    scene = bpy.context.scene
    objects = []
    for obj in scene.objects:
        item = {
            "name": obj.name,
            "type": obj.type,
            "location": tuple(round(v, 4) for v in obj.location),
        }
        if detail == "full":
            item.update({
                "rotation_euler": tuple(round(v, 4) for v in obj.rotation_euler),
                "scale": tuple(round(v, 4) for v in obj.scale),
                "hide_viewport": obj.hide_viewport,
                "parent": obj.parent.name if obj.parent else None,
            })
            if obj.type == "MESH":
                item["dimensions"] = tuple(round(v, 4) for v in obj.dimensions)
                item["materials"] = [m.name for m in obj.data.materials if m]
            elif obj.type == "CAMERA":
                item["lens"] = round(obj.data.lens, 4)
            elif obj.type == "LIGHT":
                item["light_type"] = obj.data.type
                item["energy"] = round(obj.data.energy, 4)
        objects.append(item)
    active = bpy.context.view_layer.objects.active
    return {
        "frame": scene.frame_current,
        "engine": scene.render.engine,
        "active": active.name if active else None,
        "object_count": len(scene.objects),
        "mesh_count": sum(1 for o in scene.objects if o.type == "MESH"),
        "materials": [m.name for m in bpy.data.materials],
        "collections": [c.name for c in bpy.data.collections],
        "objects": objects,
    }


def find(pattern: str, types: Optional[list] = None) -> list:
    """Find objects whose name matches `pattern` (fnmatch glob).

    Optionally filter by Blender object type (e.g. ['MESH', 'CAMERA']).
    """
    matches = []
    for obj in bpy.data.objects:
        if not fnmatch.fnmatch(obj.name, pattern):
            continue
        if types and obj.type not in types:
            continue
        matches.append({
            "name": obj.name,
            "type": obj.type,
            "location": tuple(round(v, 4) for v in obj.location),
        })
    return matches


def bbox(name_or_pattern: Optional[str] = None) -> Optional[dict]:
    """Bounding box of the named object, matching pattern, or all visible meshes."""
    if name_or_pattern is None:
        objs = [o for o in bpy.data.objects if o.type == "MESH" and not o.hide_viewport]
    elif name_or_pattern in bpy.data.objects:
        objs = [bpy.data.objects[name_or_pattern]]
    else:
        objs = [
            o for o in bpy.data.objects
            if fnmatch.fnmatch(o.name, name_or_pattern) and o.type == "MESH"
        ]
    if not objs:
        return None
    pts = []
    for o in objs:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    mn = tuple(round(min(p[i] for p in pts), 4) for i in range(3))
    mx = tuple(round(max(p[i] for p in pts), 4) for i in range(3))
    centre = tuple(round((mn[i] + mx[i]) / 2, 4) for i in range(3))
    size = tuple(round(mx[i] - mn[i], 4) for i in range(3))
    return {
        "min": mn, "max": mx, "centre": centre, "size": size,
        "objects": [o.name for o in objs],
    }


def scene_hash() -> str:
    """Short deterministic hash of the scene state (16-char hex)."""
    summary = inspect(detail="brief")
    blob = json.dumps(summary, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]
