# Blender HTTP

**Drive Blender from anywhere on your computer via HTTP.**

## How it works

The add-on starts a small web server inside Blender. Anything that can make an HTTP request — an AI agent, a one-line `curl` command, a Python script, a web page open on your laptop — can now talk to Blender directly.

You send a chunk of Python code. Blender runs it. You get the result back.

```
   you  ──── send a script ────▶  Blender  ──── result + anything it printed ────▶  you
```

You can talk to it in two ways:

- **One-shot.** Send a script, wait, get one tidy JSON answer with anything the script printed and the value of its last line. As simple as `curl`. Best for short tasks.
- **Live.** Send the script and watch a feed come back as Blender works — every line it prints, every named step it reaches, every screenshot it takes, in real time. Best for long builds, because you can see what's happening and stop mid-way if it looks wrong.

There's one trick worth knowing. If your script wraps its work in a `build()` function with `yield` between steps, Blender runs **one step, lets the UI breathe, runs the next step, lets the UI breathe**, and so on. The viewport keeps redrawing, you can rotate the camera while it builds, and objects appear in the scene one by one instead of all popping in at the end. It's the difference between "Blender is frozen, please wait 30 seconds" and watching the model assemble itself in front of you.

Every script gets a small set of helpers handed to it automatically — for taking screenshots, rendering a multi-angle audit of the scene, asking what's in the scene, and writing to a shared output folder. No imports needed; they're just available.

The server only listens on your own machine (`127.0.0.1`, default port `9876`). It's not on the network. See [SECURITY.md](SECURITY.md) before changing that.

## Why this exists — vs the official Blender MCP server

Blender has an official server based on the [Model Context Protocol](https://modelcontextprotocol.io/) (MCP). It works. But for the kind of back-and-forth an AI agent does — *"add this, screenshot it, fix that, screenshot again"* — MCP has friction that adds up. This add-on takes the same idea and strips that friction out.

**Screenshots eat your context.** MCP returns images as base64 text mixed into the response. A single full-screen screenshot is about **1.3 MB** of context the agent has to carry. A 6-view audit? Around **8 MB just for the pictures**. With Blender HTTP, screenshots go to disk; the agent only sees them if it asks. Want a tiny preview to check progress? `?size=256` gives you a ~25 KB PNG. Want to check whether anything actually changed before re-rendering? `?if-changed=<hash>` returns "nope" with no payload at all.

**Every action is a separate round-trip.** With MCP, *"add a cube, name it, make it red, move it, take a screenshot"* is five separate request-and-response exchanges, each with its own protocol envelope. Blender HTTP lets you batch them into one round-trip — or just send one bigger script and skip the overhead entirely.

**The viewport freezes while a script runs.** MCP runs your Python synchronously: while it works, Blender's UI is locked, you can't see progress, you can't cancel. With Blender HTTP, if your script wraps its work in a generator that `yield`s between steps, the UI keeps redrawing — objects appear one by one, you can orbit the camera, and you can abort a runaway script mid-flight.

**You write everything from scratch.** MCP gives you "run this Python in Blender" and stops there. Want to know what's in the scene? Write a script that returns it. Want a 6-view audit of your model? Write the camera placement code in every project. Blender HTTP comes with that work pre-done: ask `/inspect` for a scene summary, `POST /audit` to render the audit suite, `/find` to search by name, `/bbox` for bounding boxes. All one HTTP call, all already debugged.

### Smaller benefits worth knowing

- Responses compress with gzip if you ask — usually 3–5× smaller.
- No SDK to install on the client side. `curl` works. Any language with an HTTP client works.
- The legacy one-liner `POST /` with the script as the raw body still does what you'd expect, so existing scripts written for [ptrthomas/blender-agent](https://github.com/ptrthomas/blender-agent) keep running.

## Install

**Requirements:** Blender **4.2+** (the modern extension system was introduced in 4.2; tested on 5.1, expected to work on 4.2 through 5.x). No external Python packages — the add-on uses only Blender's bundled Python and the stdlib. The optional client (`client/send.py`) needs Python 3.x with stdlib only.

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
> The repository is `https://github.com/ProfRino/blender-http` (a Blender 4.2+ extension that runs Python over HTTP for live agent control).
>
> Please do the following, **briefly explaining each step before you run it** and **asking before any destructive action**:
>
> 1. **Detect my OS** (Windows / macOS / Linux) and locate my Blender installation. Report the version. The plugin requires **Blender 4.2 or higher** — abort cleanly if mine is older.
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


## Try it

A handful of examples. Each one is the complete code.

### Make a cube

```bash
curl -s localhost:9876 --data-binary "
import bpy
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1))
'cube made'
"
```

Returns `{"ok": true, "output": "", "result": "cube made"}`.

### Watch a model build itself

Save as `pavilion.py`:

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

Then:

```bash
python client/send.py pavilion.py --stream
```

Step events arrive live as Blender works through it, and the objects appear in the viewport one by one rather than all at the end.

### Render a multi-angle audit of the current scene

Inside any script — one line:

```python
audit(f"{OUTPUT}/audits/pass1")
```

That auto-places six cameras (front, back, left, right, top, isometric) with bbox-aware framing, renders them all into `~/blender_http/output/audits/pass1/`, and cleans up after itself.

### Ask what's in the scene

```bash
curl localhost:9876/inspect
```

Returns a compact JSON summary — every object's name, type, and location, plus materials, active camera, and collections.

### Take a screenshot

```bash
# Full resolution PNG
curl "localhost:9876/snapshot?mode=opengl" -o now.png

# Tiny ~25 KB preview — useful for "did my change work?" checks
curl "localhost:9876/snapshot?mode=opengl&size=256" -o preview.png
```

### Stop a runaway script

```bash
curl -X DELETE localhost:9876/jobs/<job_id>
```

It stops at the next `yield`. No need to restart Blender.

## What scripts get for free

Just write Python — these names are already in scope, no imports needed:

- `bpy` — Blender's Python API
- `OUTPUT` — write your snapshots, renders, and `.blend` files here (defaults to `~/blender_http/output/`)
- `snapshot(path)`, `audit(dir)` — save images, run the audit suite
- `inspect()`, `find(pattern)`, `bbox()`, `scene_hash()` — query the scene
- `progress(current, total, label)` — emit a progress event into the live feed

The full list of endpoints, query parameters, and response shapes is in **[docs/protocol.md](docs/protocol.md)**.

## License

MIT. Copyright 2026 Ruggiero Lovreglio. See [LICENSE](LICENSE).

## Credits

Architecture inspired by [ptrthomas/blender-agent](https://github.com/ptrthomas/blender-agent). All code in this repository is independently written; no source was copied.
