"""Snapshot and multi-view audit for Blender HTTP.

Three snapshot modes:
    viewport - captures the 3D viewport area as displayed
    opengl   - renders the scene via OpenGL through a camera (materials visible, fast)
    render   - full Cycles/Eevee render through a camera (slow, photoreal)

The `audit()` function places cameras at 6 canonical viewpoints with
bbox-aware framing and saves one image per view.
"""

import math
import os
from typing import Optional

import bpy
from mathutils import Vector

VIEW_DIRECTIONS = {
    "01_front":     (0.0, -1.0, 0.35),
    "02_back":      (0.0,  1.0, 0.35),
    "03_left":      (-1.0, 0.0, 0.35),
    "04_right":     (1.0,  0.0, 0.35),
    "05_top":       (0.0,  0.0, 1.0),
    "06_isometric": (1.0, -1.0, 0.65),
}


# --- bounding box -------------------------------------------------------------

def mesh_bbox():
    """Return (min, max, centre, size) for all visible mesh objects, or None."""
    meshes = [
        o for o in bpy.data.objects
        if o.type == "MESH" and not o.hide_viewport
    ]
    if not meshes:
        return None
    pts = []
    for o in meshes:
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    mn = Vector((
        min(p.x for p in pts),
        min(p.y for p in pts),
        min(p.z for p in pts),
    ))
    mx = Vector((
        max(p.x for p in pts),
        max(p.y for p in pts),
        max(p.z for p in pts),
    ))
    centre = (mn + mx) / 2
    size = mx - mn
    return mn, mx, centre, size


# --- camera placement ---------------------------------------------------------

def _place_camera(name: str, direction, centre, size, lens=35.0, margin=1.4):
    max_dim = max(size.x, size.y, size.z, 0.001)
    sensor_w = 36.0
    fov = 2.0 * math.atan((sensor_w / 2.0) / lens)
    distance = (max_dim / 2.0) / math.tan(fov / 2.0) * margin

    direction = Vector(direction).normalized()
    location = centre + direction * distance

    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.object
    cam.name = name
    cam.data.lens = lens
    cam.data.clip_end = max(distance * 10.0, 1000.0)

    # Aim at centre
    look = centre - location
    cam.rotation_euler = look.to_track_quat("-Z", "Y").to_euler()
    return cam


# --- viewport / render helpers ------------------------------------------------

def _ensure_dir(path: str):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)


def _viewport_screenshot(path: str) -> str:
    """Capture the current 3D viewport area (uses Blender's screen.screenshot_area)."""
    _ensure_dir(path)
    for win in bpy.context.window_manager.windows:
        for area in win.screen.areas:
            if area.type == "VIEW_3D":
                with bpy.context.temp_override(window=win, area=area):
                    bpy.ops.screen.screenshot_area(filepath=path)
                return path
    raise RuntimeError("No 3D viewport found for viewport screenshot")


def _opengl_render(path: str, camera=None, resolution=None) -> str:
    _ensure_dir(path)
    scene = bpy.context.scene
    saved_cam = scene.camera
    saved_fmt = scene.render.image_settings.file_format
    saved_res = (scene.render.resolution_x, scene.render.resolution_y)
    try:
        if camera is not None:
            scene.camera = camera
        if resolution is not None:
            scene.render.resolution_x, scene.render.resolution_y = resolution
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = path
        # view_context=False -> uses scene.camera and render settings, no viewport overlays/gizmos
        bpy.ops.render.opengl(write_still=True, view_context=False)
    finally:
        scene.camera = saved_cam
        scene.render.image_settings.file_format = saved_fmt
        scene.render.resolution_x, scene.render.resolution_y = saved_res
    return path


def _cycles_render(path: str, camera=None, resolution=None) -> str:
    _ensure_dir(path)
    scene = bpy.context.scene
    saved_cam = scene.camera
    saved_fmt = scene.render.image_settings.file_format
    saved_res = (scene.render.resolution_x, scene.render.resolution_y)
    try:
        if camera is not None:
            scene.camera = camera
        if resolution is not None:
            scene.render.resolution_x, scene.render.resolution_y = resolution
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
    finally:
        scene.camera = saved_cam
        scene.render.image_settings.file_format = saved_fmt
        scene.render.resolution_x, scene.render.resolution_y = saved_res
    return path


# --- public api ---------------------------------------------------------------

def snapshot(path: str, mode: str = "viewport", size: Optional[int] = None) -> str:
    """Save one image.

    mode = viewport | opengl | render
    size = None (use scene render resolution) | int (max pixel dim, keeps aspect).
           Only applies to opengl and render modes; viewport size is fixed by the area.
    """
    mode = mode.lower()
    resolution = _resolution_for_size(size) if size else None
    if mode == "viewport":
        return _viewport_screenshot(path)
    if mode == "opengl":
        return _opengl_render(path, resolution=resolution)
    if mode == "render":
        return _cycles_render(path, resolution=resolution)
    raise ValueError(f"unknown snapshot mode: {mode!r}")


def _resolution_for_size(size: int) -> tuple:
    """Compute (x, y) that fits within size x size, keeping current scene aspect."""
    s = bpy.context.scene.render
    cur_x = max(s.resolution_x, 1)
    cur_y = max(s.resolution_y, 1)
    aspect = cur_x / cur_y
    if aspect >= 1:
        return (int(size), max(1, int(round(size / aspect))))
    return (max(1, int(round(size * aspect))), int(size))


def thumbnail_b64(size: int = 128, mode: str = "opengl") -> str:
    """Render a tiny thumbnail and return base64 PNG (no `data:` prefix)."""
    import base64
    import os
    import tempfile
    fd, p = tempfile.mkstemp(suffix=".png", prefix="bhttp_thumb_")
    os.close(fd)
    try:
        snapshot(p, mode=mode, size=size)
        with open(p, "rb") as f:
            return base64.b64encode(f.read()).decode("ascii")
    finally:
        try:
            os.unlink(p)
        except OSError:
            pass


def audit(
    output_dir: str,
    mode: str = "opengl",
    views: Optional[list] = None,
    lens: float = 35.0,
    margin: float = 1.4,
    resolution=(1400, 1000),
    keep_cameras: bool = False,
) -> dict:
    """Render the canonical 6-view audit suite. Returns {view_name: filepath}.

    mode = "opengl" (fast, recommended) or "render" (slow, photoreal).
    Cameras are placed using scene bbox + lens FOV, then removed unless
    keep_cameras=True.
    """
    os.makedirs(output_dir, exist_ok=True)
    bb = mesh_bbox()
    if bb is None:
        return {}
    _, _, centre, size = bb

    view_keys = views or list(VIEW_DIRECTIONS.keys())
    results: dict = {}
    kept_cams: list = []
    saved_cam = bpy.context.scene.camera
    try:
        for view in view_keys:
            direction = VIEW_DIRECTIONS.get(view)
            if direction is None:
                continue
            cam = _place_camera(
                f"_audit_{view}", direction, centre, size,
                lens=lens, margin=margin,
            )
            path = os.path.join(output_dir, f"{view}.png")
            try:
                if mode == "render":
                    _cycles_render(path, camera=cam, resolution=resolution)
                else:
                    _opengl_render(path, camera=cam, resolution=resolution)
                results[view] = path
            finally:
                if keep_cameras:
                    kept_cams.append(cam)
                else:
                    data = cam.data
                    try:
                        bpy.data.objects.remove(cam, do_unlink=True)
                        if data and data.users == 0:
                            bpy.data.cameras.remove(data)
                    except Exception:
                        pass
    finally:
        bpy.context.scene.camera = saved_cam
    return results
