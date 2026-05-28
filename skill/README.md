# Blender HTTP Skill

A Claude Code skill for driving Blender through the [Blender HTTP](..) plugin (port 9877). This folder lives inside the plugin's repo — same clone gets you both.

## What this skill teaches

- The plugin's HTTP API and SSE event stream
- The injected helpers: `bpy`, `OUTPUT`, `WORKSPACE`, `snapshot()`, `audit()`, `progress()`
- The generator `build()` script pattern for live progress and a responsive viewport
- Assembly modelling rules (when modelling connected structures)
- Multi-view audit workflow and a checklist of common AI-Blender errors

See [SKILL.md](SKILL.md) for the full content.

## Quick start

1. **Install the plugin** (one-time):

   ```powershell
   ..\install.ps1
   ```

2. **Start Blender**, enable "Blender HTTP" in `Edit > Preferences > Add-ons`, then in the 3D Viewport press `N` -> `HTTP` tab -> **Start**.

3. **Drop a script** into [`scripts/generated_scene.py`](scripts/generated_scene.py) and send it:

   ```powershell
   python ..\client\send.py scripts\generated_scene.py --stream
   ```

## Try the example

```powershell
python ..\client\send.py examples\connected_scene_with_audit.py --stream
```

This builds a small pavilion with vector-aligned diagonal braces, runs the 6-view audit, and adds a joint close-up. Outputs land in `~/blender_http/output/audits/pavilion/`.

## Files

```
skill/
├── SKILL.md                              the skill content itself
├── README.md                             this file
├── examples/
│   └── connected_scene_with_audit.py     assembly + audit demo
├── scripts/
│   └── generated_scene.py                drop generated scripts here
└── templates/
    ├── assembly_plan_template.md         fill out before coding
    └── audit_report_template.md          fill out after auditing
```

## Notes

- This skill replaces the earlier `blender-http-assembly-skill` which targeted the legacy `ptrthomas/blender-agent` HTTP bridge on port 5656. The new plugin runs on **9877** and adds streaming, generator-based step execution, cancellation, snapshots, and multi-view audit.
- The skill is broad on the plugin contract (covers any Blender automation) and detailed on assembly + audit (its main use case for architectural / connected-geometry work).
