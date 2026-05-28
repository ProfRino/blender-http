"""Drop your generated Blender script here.

Send to the Blender HTTP plugin with:

    python ..\\..\\blender-http\\client\\send.py scripts\\generated_scene.py --stream

The plugin injects these into the script's namespace (no imports needed):
    bpy        - Blender Python API
    WORKSPACE  - str path to the workspace root
    OUTPUT     - str path to <WORKSPACE>/output/  (auto-created)
    progress(current, total=None, label=None)
    snapshot(path, mode="viewport")
    audit(output_dir, mode="opengl", margin=1.4, lens=35)

For non-trivial work, define a `build()` generator and yield between steps
so the viewport stays responsive and SSE step events stream live:

    def build():
        yield "step 1"
        ...
        yield "step 2"
        ...
        audit(f"{OUTPUT}/audits/run1")
"""
