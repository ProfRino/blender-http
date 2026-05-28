# Blender HTTP

**Drive Blender from anywhere on your computer via HTTP.**

## How it works

The add-on starts a tiny HTTP server inside Blender (default `127.0.0.1:9876`). External processes — an AI coding agent, a CLI tool, a Python script, a web page — drive Blender by POSTing Python source to the server. The server runs that code on Blender's main thread, captures stdout and the value of the last expression, and returns the result.

```
                       POST /  (Python source as the body)
   external client  ────────────────────────────────────▶  Blender HTTP server
       (curl, Python urllib,                                      │
        Claude Code agent,                                        │ run on Blender's
        web page, ...)                                            │ main thread via
                                                                  │ bpy.app.timers
                       ◀────────────────────────────────  {ok, output, result}
                            JSON response
```

There are two execution modes:

- **Sync** (`POST /`) — runs the script, blocks until done, returns one JSON blob with the captured stdout and the value of the last expression. Compatible with simple `curl` one-liners.
- **Async + streaming** (`POST /jobs` → `GET /jobs/{id}/stream`) — returns a `job_id` immediately and streams events back over **Server-Sent Events**: every `print()` line, every `yield` from a `build()` generator, every `snapshot()` taken, every `progress()` update. Cancellable via `DELETE /jobs/{id}`.

Scripts that define a `build()` function returning a generator are run **one yield per timer tick**, which means Blender's event loop runs between steps — the viewport redraws, the UI stays responsive, and you can orbit the camera while the script executes. Objects appear progressively rather than all at once at the end.

Scripts get a small set of helpers injected into their namespace (`snapshot`, `audit`, `inspect`, `find`, `bbox`, `progress`, `OUTPUT`, `WORKSPACE`) so common operations don't need a Python boilerplate header.

Default port: **9876**. Default bind: `127.0.0.1` only.

## Why this exists — vs the official Blender MCP server

Blender has an official [Model Context Protocol](https://modelcontextprotocol.io/) server. It works, but for typical agent workflows it has structural overhead this add-on is designed to remove.

| Pain point with MCP | What Blender HTTP does instead |
|---|---|
| Each operation is a separate tool call with the protocol's request + tool_result envelope. A chatty 6-step build = 6 envelopes × overhead. | `POST /batch` runs N scripts in one round-trip. The script namespace already has `snapshot`, `audit`, `inspect`, etc., so one script does the work of several MCP tool calls. |
| Screenshots return as **base64 PNG inline in the tool_result** — a single full-res image eats ~1.3 MB of the agent's context window. A 6-view audit = ~8 MB just for the images. | `/snapshot` returns PNG bytes (or writes to disk with `?save=`). Zero context cost unless the agent explicitly reads the file. `?size=256` returns a ~25 KB preview. `?if-changed=<hash>` returns `304 Not Modified` for cheap polling. |
| `execute_blender_code` runs synchronously: the viewport freezes for the script's full duration, `print()` output only arrives at the end, no cancellation. | Generator-based execution yields control between steps — UI stays responsive, objects appear progressively, every `print` / yield / progress event streams over SSE the moment it happens, and `DELETE /jobs/{id}` aborts cleanly at the next yield. |
| No built-in scene introspection over the wire — you have to write `bpy` code, send it, parse the result. | `GET /inspect`, `POST /find`, `GET /bbox`, `GET /scene-hash` return compact JSON the agent can quote directly. |
| No built-in multi-view audit — you write camera placement + render loop in every script. | `POST /audit` (or `audit()` inside a script) renders the canonical 6-view suite with bbox-aware camera placement in one call. |
| No response compression — JSON payloads ship uncompressed. | `Accept-Encoding: gzip` compresses responses ~3–5×. |
| MCP requires the MCP SDK / runtime on the client side. | Pure HTTP. `curl` works. Any language with an HTTP client works. No SDK to install. |

It also keeps a **synchronous compat endpoint** (`POST /` with the script as the raw body) so existing one-liner `curl` workflows from the legacy [ptrthomas/blender-agent](https://github.com/ptrthomas/blender-agent) still work.

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
