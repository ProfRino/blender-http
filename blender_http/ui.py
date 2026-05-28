"""N-panel UI and operators for Blender HTTP."""

import bpy

from . import jobs, server, workspace


def _workspace_changed(self, context):
    workspace.set_override(self.workspace_override)


class BHTTP_Settings(bpy.types.PropertyGroup):
    host: bpy.props.StringProperty(name="Host", default="127.0.0.1")
    port: bpy.props.IntProperty(name="Port", default=9876, min=1024, max=65535)
    workspace_override: bpy.props.StringProperty(
        name="Workspace",
        description="Override the workspace path (clears on Blender restart). Leave empty to use env var or default.",
        default="",
        subtype="DIR_PATH",
        update=_workspace_changed,
    )


class BHTTP_OT_Start(bpy.types.Operator):
    bl_idname = "blender_http.start"
    bl_label = "Start Server"
    bl_description = "Start the Blender HTTP server"

    def execute(self, context):
        s = context.scene.blender_http_settings
        try:
            ok = server.start(host=s.host, port=s.port)
        except OSError as e:
            self.report({"ERROR"}, f"Cannot bind {s.host}:{s.port} - {e}")
            return {"CANCELLED"}
        if ok:
            self.report({"INFO"}, f"Blender HTTP running on {s.host}:{s.port}")
        else:
            self.report({"WARNING"}, "Server already running")
        _redraw()
        return {"FINISHED"}


class BHTTP_OT_Stop(bpy.types.Operator):
    bl_idname = "blender_http.stop"
    bl_label = "Stop Server"
    bl_description = "Stop the Blender HTTP server"

    def execute(self, context):
        if server.stop():
            self.report({"INFO"}, "Blender HTTP stopped")
        _redraw()
        return {"FINISHED"}


class BHTTP_OT_Cancel(bpy.types.Operator):
    bl_idname = "blender_http.cancel"
    bl_label = "Cancel Job"
    bl_description = "Request cancellation of the current job"
    job_id: bpy.props.StringProperty()

    def execute(self, context):
        if jobs.cancel(self.job_id):
            self.report({"INFO"}, f"Cancellation requested for {self.job_id}")
        _redraw()
        return {"FINISHED"}


class BHTTP_PT_Panel(bpy.types.Panel):
    bl_label = "Blender HTTP"
    bl_idname = "BHTTP_PT_Panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "HTTP"

    def draw(self, context):
        layout = self.layout
        s = context.scene.blender_http_settings

        col = layout.column(align=True)
        col.prop(s, "host")
        col.prop(s, "port")

        if server.is_running():
            host, port = server.address()
            box = layout.box()
            box.label(text=f"Running: {host}:{port}", icon="LINKED")
            box.operator("blender_http.stop", icon="PAUSE")
        else:
            box = layout.box()
            box.label(text="Stopped", icon="UNLINKED")
            box.operator("blender_http.start", icon="PLAY")

        wbox = layout.box()
        wbox.label(text="Workspace", icon="FILE_FOLDER")
        wbox.prop(s, "workspace_override", text="")
        wbox.label(text=f"Active: {workspace.workspace()}")

        cur = jobs.current_job()
        if cur:
            layout.separator()
            box = layout.box()
            box.label(text=f"Job {cur.id}", icon="MODIFIER")
            box.label(text=f"Status: {cur.status}")
            box.label(text=f"Step: {cur.step_index}")
            op = box.operator("blender_http.cancel", text="Cancel", icon="CANCEL")
            op.job_id = cur.id


CLASSES = (
    BHTTP_Settings,
    BHTTP_OT_Start,
    BHTTP_OT_Stop,
    BHTTP_OT_Cancel,
    BHTTP_PT_Panel,
)


def _redraw():
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                area.tag_redraw()
    except Exception:
        pass


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.blender_http_settings = bpy.props.PointerProperty(type=BHTTP_Settings)


def unregister():
    if server.is_running():
        server.stop()
    if hasattr(bpy.types.Scene, "blender_http_settings"):
        del bpy.types.Scene.blender_http_settings
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except Exception:
            pass
