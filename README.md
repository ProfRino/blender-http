# Blender HTTP

**Drive Blender from anywhere on your computer via HTTP.**

## How it works

The add-on starts a small web server inside Blender. In a typical setup, the chain looks like this:

```
  you  ──prompt──▶  AI agent  ──HTTP request──▶  HTTP server  ──runs script──▶  Blender
                        ◀──────── result + printed output ◀────────────────────────┘
```

You tell the AI what you want in plain English. The AI (Claude Code, Codex, …) writes the Blender instructions for you and sends them to the add-on inside Blender. The add-on runs them, then hands back whatever happened — results, error messages, anything the script reported — for the AI to show you.

You don't have to go through an AI. Anything on your computer that can send instructions can talk to the add-on directly — a small script, a web page, a one-line command in a terminal. The AI is just the easiest way in.

The add-on runs your instructions in one of two styles:

- **All at once.** Send the instructions, wait, get the result back when they finish. Simple and quick — best for small tasks.
- **Step by step, live.** Send the instructions and watch them play out — every status message, every step the script announces, every screenshot it saves — arriving as it happens. Best for bigger tasks, because you can see how it's going and stop it if something looks wrong.

There's one nice trick. If the instructions are written as a series of named steps, Blender does step one, pauses long enough for the viewport to update, does step two, pauses again, and so on. You can rotate the camera while it builds, watch objects appear one at a time, and cancel halfway through if you change your mind. It's the difference between Blender freezing for thirty seconds and watching the scene assemble itself.

A few useful shortcuts are always available inside the instructions — for taking pictures of the scene, rendering it from six angles for review, asking what's currently in the scene, and saving files to a shared output folder. They're just there; no setup needed.

The add-on only listens to your own computer. It can't be reached over the internet or by anyone else on your network. (If you want to expose it deliberately, read [SECURITY.md](SECURITY.md) first.)

## Why this exists — vs the official Blender MCP server

With the official Blender [MCP](https://modelcontextprotocol.io/) server, the AI controls Blender through a fixed menu of pre-built tools — like a remote control with specific buttons. With Blender HTTP, the AI just writes Python — like having the keyboard. The remote works for what it covers; the keyboard is faster, cheaper, and never runs out of buttons.

**MCP gives the AI a fixed menu of buttons.** Around 20 of them — for things like adding objects, applying materials, asking what's in the scene, downloading assets. The AI carries that whole menu in its memory from the start of every conversation, even if you never use any of those buttons. With Blender HTTP there's no menu — the AI just writes the same kind of code it already knows.

**More buttons means more wrong guesses.** On every step the AI has to ask itself, *"is there a button for this, or should I just write the code?"* Sometimes a button looks right but doesn't quite do what's needed — so the AI tries it, sees it didn't work, then writes the code anyway. Each detour costs time and memory. With Blender HTTP there's no menu to guess against — there's only the code.

**Lots of little tasks turn into lots of little trips.** *"Add a cube, name it, colour it, move it, take a screenshot"* is five separate back-and-forths with MCP — five questions, five answers, every one of them costing a little extra. With Blender HTTP it's one back-and-forth: one short script that does all five things. The clock spends less time waiting, and the AI's memory fills up more slowly.

**Screenshots fill up the AI's memory.** When MCP takes a screenshot, the picture comes back inside the answer and stays in the AI's memory from then on. One full-quality screenshot is about 1.3 MB. A six-angle review of a scene is closer to 8 MB — just for the pictures. Blender HTTP saves screenshots to a folder on your disk instead. The AI only sees an image if it asks to. If you just want a *"did my change work?"* peek, you can ask for a tiny thumbnail. If nothing has changed since last time, the answer can be a one-word "nothing changed" with no picture at all.

**You can stop a long job partway through.** MCP runs every script to completion — there's no cancel button. If something is clearly going wrong five seconds into a thirty-second build, you wait out the other twenty-five seconds anyway. Blender HTTP gives you a stop request that interrupts the script cleanly at the next step. As a bonus, when a script is written as a series of named steps, Blender's window stays interactive between them — you can rotate the camera and watch the scene take shape instead of waiting for the final reveal.


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

## Use with an AI agent

The [`skill/`](skill/) folder is a Claude Code skill that teaches an AI agent how to drive this plugin — when to use streaming vs one-shot, how to write scripts as named steps, and the screenshot audit checklist for catching common AI-Blender mistakes (floating parts, wrong scale, missing materials, ...). Most agents auto-load it when the folder is in scope. See [`skill/SKILL.md`](skill/SKILL.md) for the full content.

## What's in this repo

```
blender-http/
├── blender_http/        the Blender add-on (installs into user_default/extensions)
├── client/              send.py + send.ps1 — Python and PowerShell helpers for sending scripts
├── docs/                protocol.md (full HTTP spec) + design.md (architecture notes)
├── examples/            ready-to-run sample scripts (sync, generator, audit, cancel)
├── skill/               Claude Code skill bundled for AI agents (SKILL.md + templates)
├── install.ps1          one-line Windows installer
├── LICENSE              MIT
├── README.md            this file
└── SECURITY.md          threat model and safe defaults — read before exposing the server
```

## License

MIT. Copyright 2026 Ruggiero Lovreglio. See [LICENSE](LICENSE).

## Credits

Architecture inspired by [ptrthomas/blender-agent](https://github.com/ptrthomas/blender-agent). All code in this repository is independently written; no source was copied.
