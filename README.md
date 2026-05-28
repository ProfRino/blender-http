# Blender HTTP

A Blender 5.0+ add-on that runs Python scripts over HTTP with **live streaming output**, **cancellable jobs**, and **chunked execution that keeps the viewport responsive**.

Inspired by [ptrthomas/blender-agent](https://github.com/ptrthomas/blender-agent) — rewritten from scratch to add Server-Sent Events streaming, a job queue, generator-based step execution, and a cancel API.

Default port: **9876**.

## Why this exists

The "send a Python script over HTTP, get one big JSON response back" pattern works, but has three flaws:

1. **Blender freezes** while a big script runs (single main thread).
2. **No visibility** — `print()` output only arrives after the script ends.
3. **No cancel** — a runaway 5-minute job holds the whole UI hostage.

Blender HTTP fixes all three by:

- Running scripts as **generators** that `yield` between steps. Between yields, Blender's event loop runs — viewport redraws, UI stays responsive, objects appear progressively.
- Streaming events back via **Server-Sent Events** (SSE) — every `print()` line, every step label, every progress update arrives live.
- Exposing a **job API** with `DELETE /jobs/{id}` to cancel cooperatively.

It also keeps a **synchronous compat endpoint** so existing one-liner `curl` workflows still work.

## Install

**Requirements:** Blender 5.0+. No external Python packages — the add-on uses only Blender's bundled Python and the stdlib. The optional client (`client/send.py`) needs Python 3.x with stdlib only.

The add-on lives under Blender's `extensions/user_default/blender_http` folder. Each OS has a different parent path; copy or symlink the `blender_http/` subdirectory into it.

### Windows

```powershell
git clone https://github.com/ProfRino/blender-http
cd blender-http
.\install.ps1                          # or: .\install.ps1 -BlenderVersion 5.2
```

Installs to `%APPDATA%\Blender Foundation\Blender\5.1\extensions\user_default\blender_http`.

### macOS

```bash
git clone https://github.com/ProfRino/blender-http
cd blender-http
mkdir -p ~/Library/Application\ Support/Blender/5.1/extensions/user_default
ln -sf "$(pwd)/blender_http" ~/Library/Application\ Support/Blender/5.1/extensions/user_default/blender_http
```

(Symlink means edits to the source are picked up on Blender restart.)

### Linux

```bash
git clone https://github.com/ProfRino/blender-http
cd blender-http
mkdir -p ~/.config/blender/5.1/extensions/user_default
ln -sf "$(pwd)/blender_http" ~/.config/blender/5.1/extensions/user_default/blender_http
```

### Enable + start the server (all platforms)

1. Launch Blender, open `Edit > Preferences > Add-ons`, search **Blender HTTP**, tick the checkbox.
2. In the 3D Viewport, press `N` → click the `HTTP` tab → **Start**.
3. Verify:
   ```bash
   curl http://127.0.0.1:9876/health
   # {"ok": true}
   ```

### Install with an AI agent (Claude Code, Codex, etc.)

If you have an AI coding agent with shell access, you can hand it this prompt and it will do the install for you. Copy the block between the lines:

---

> I want to install the Blender HTTP plugin into my existing Blender installation.
>
> The repository is `https://github.com/ProfRino/blender-http` (a Blender 5.0+ extension that runs Python over HTTP for live agent control).
>
> Please do the following, **briefly explaining each step before you run it** and **asking before any destructive action**:
>
> 1. **Detect my OS** (Windows / macOS / Linux) and locate my Blender installation. Report the version. The plugin requires **Blender 5.0 or higher** — abort cleanly if mine is older.
>
> 2. **Clone the repository** to a sensible location:
>    - Windows: `%USERPROFILE%\source\blender-http`
>    - macOS / Linux: `~/source/blender-http`
>
>    If `git` isn't installed, tell me and stop.
>
> 3. **Install the add-on** into the matching user-extensions directory for my Blender version `<ver>`:
>    - **Windows**: run the bundled `install.ps1` (copies into `%APPDATA%\Blender Foundation\Blender\<ver>\extensions\user_default\blender_http`). Use `-BlenderVersion <ver>` if my version isn't 5.1.
>    - **macOS**: symlink the `blender_http/` subfolder into `~/Library/Application Support/Blender/<ver>/extensions/user_default/`.
>    - **Linux**: symlink into `~/.config/blender/<ver>/extensions/user_default/`.
>
> 4. If an existing install is already present, show me its path and **ask before replacing**.
>
> 5. **Tell me exactly what to do inside Blender**:
>    - Open Blender (or restart if it was already running).
>    - `Edit > Preferences > Add-ons`, search "Blender HTTP", tick the checkbox.
>    - In the 3D Viewport press `N`, click the `HTTP` tab, click **Start**.
>
> 6. **Wait for me to confirm I've clicked Start.** Then verify by curling `http://127.0.0.1:9876/health` — expect `{"ok": true}`.
>
> Don't proceed if you can't confirm my Blender version. Don't overwrite anything without asking. Keep output concise — I want progress, not a tutorial.

---


## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/` | Sync exec. Returns `{ok, output, result, error}` when script ends. Compatible with blender-agent. |
| `POST` | `/jobs` | Async submit. Returns `{job_id, status}` immediately. |
| `GET` | `/jobs/{id}` | Job status JSON. |
| `GET` | `/jobs/{id}/stream` | SSE stream of events (`started`, `step`, `stdout`, `progress`, `snapshot`, `audit`, `completed`, `failed`, `cancelled`). |
| `DELETE` | `/jobs/{id}` | Cancel running job. |
| `POST` | `/batch` | Run multiple scripts in one request. Returns per-script results. |
| `POST` | `/repl?session=<id>` | Run a script with a persistent namespace for the session. |
| `GET` | `/sessions` | List active REPL sessions. |
| `GET` | `/snapshot` | Capture one image (`?mode=&size=&save=&if-changed=`). PNG bytes or JSON with `save`. `size` for tiny previews; `if-changed` for cheap polling. |
| `POST` | `/audit` | Render the 6-view audit suite (front/back/left/right/top/iso), returns `{dir, views}`. |
| `GET` | `/inspect?detail=brief|full` | Compact scene summary. |
| `POST` | `/find` | Find objects by name pattern. Body: `{pattern, types?}`. |
| `GET` | `/bbox?name=<pattern>` | World bounding box of named object(s) or whole scene. |
| `GET` | `/scene-hash` | 16-char hex hash of current scene state. |
| `GET` | `/health` | Liveness check. |

All JSON responses honor `Accept-Encoding: gzip` (~3-5× smaller).

See [docs/protocol.md](docs/protocol.md) for full details.

## Writing scripts

### Sync (one-shot) — same as blender-agent

```python
import bpy
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1))
"cube made"   # last expression -> result
```

### Generator (streaming + progressive) — new

```python
import bpy

def build():
    yield "base"
    bpy.ops.mesh.primitive_plane_add(size=6)
    for i in range(4):
        yield f"column {i+1}/4"
        bpy.ops.mesh.primitive_cube_add(size=0.4, location=(i, 0, 1))
    yield "roof"
    bpy.ops.mesh.primitive_plane_add(size=6, location=(0, 0, 2))
```

If `build` is defined and returns a generator, the server runs one yield per timer tick. Each yield emits a `step` event over SSE. Between ticks Blender redraws, so the viewport shows objects appearing live.

If `build` is not defined, the script runs in one shot (sync compatibility).

Helpers and constants injected into every script's namespace:

- `progress(current, total=None, label=None)` — explicit progress events.
- `snapshot(path, mode="viewport", size=None, thumb=False)` — save one image. `size` downscales (opengl/render), `thumb=True` also embeds a 128 px base64 preview in the SSE event.
- `audit(output_dir, mode="opengl", margin=1.4, lens=35)` — render the canonical 6-view audit suite (front, back, left, right, top, isometric) with bbox-aware camera framing. Returns `{view_name: path}`.
- `inspect(detail="brief")` — scene summary dict.
- `find(pattern, types=None)` — fnmatch-glob object search.
- `bbox(name_or_pattern=None)` — world bounding box.
- `scene_hash()` — 16-char hex hash of the scene state.
- `OUTPUT` — string path to `<workspace>/output/`, auto-created. Use as `f"{OUTPUT}/snapshots/before.png"`.
- `WORKSPACE` — string path to the workspace root.

Workspace defaults to `~/blender_http/`. Override via N-panel ("Workspace" field, session-only) or env var `BLENDER_HTTP_WORKSPACE` at Blender launch.

## Quick test

```powershell
# Sync (curl-like)
python client\send.py examples\01_simple_cube.py

# Streaming (watch events arrive live)
python client\send.py examples\02_generator_pavilion.py --stream
```

## License

MIT. Copyright 2026 Ruggiero Lovreglio. See [LICENSE](LICENSE).

## Credits

Architecture inspired by [ptrthomas/blender-agent](https://github.com/ptrthomas/blender-agent). All code in this repository is independently written; no source was copied.
