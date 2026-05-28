# Blender HTTP

**Drive Blender from anywhere on your computer via HTTP.**

A lightweight local HTTP add-on for controlling an already-open Blender session with Python — with SSE progress streaming, cooperative cancellation, screenshots, and multi-view audits. For script-heavy AI workflows it can reduce tool-description overhead and round-trips compared with many granular MCP setups.

> **⚠ Security note:** Blender HTTP executes arbitrary Python inside Blender. Keep it bound to `127.0.0.1`, do not expose the port to a network, and only run scripts you trust. See [SECURITY.md](SECURITY.md) for the full threat model.

## How it works

The add-on starts a small web server inside Blender. In a typical setup, the chain looks like this:

```
   You  ──prompt──▶  AI agent  ──script──▶  HTTP server  ──runs──▶  Blender
    ▲                                                                   │
    └─────────────────── result flows back ─────────────────────────────┘
```

You tell the AI what you want; it writes the Blender instructions and sends them to the add-on. The add-on runs them and returns the result. You can also send instructions directly — any HTTP client works, no AI needed.

Two run modes:

- **All at once.** Send, wait, get the result. Good for small tasks.
- **Step by step, live.** Watch progress arrive in real time. Good for big tasks — you can stop midway if it looks wrong.

When a script is written as a series of named steps, Blender pauses between them so the viewport stays interactive — you can rotate the camera, watch objects appear one at a time, and cancel cleanly.

Scripts get a few shortcuts in scope automatically: take a screenshot, render a 6-angle audit, ask what's in the scene, save to a shared output folder.

The add-on only listens on your own computer (`127.0.0.1`). See [SECURITY.md](SECURITY.md) before changing that.

## Why this exists — vs the official Blender MCP server

The official Blender [MCP](https://modelcontextprotocol.io/) server exposes a set of pre-built tools the AI calls through the MCP protocol. With Blender HTTP, the AI sends Python directly over a local HTTP endpoint. Different design choices with different trade-offs:

- **Easier to set up.** A typical MCP setup needs a Blender add-on plus a Python package plus a JSON config edit in your AI tool plus a restart. Blender HTTP needs the Blender add-on and one click.
- **No tool menu to memorise.** Many granular MCP servers load 15-20 tool descriptions into the AI's memory every conversation, used or not. Blender HTTP exposes one main entry point.
- **Fewer tool/code decisions.** When MCP exposes a curated tool surface, the AI sometimes tries a tool, sees it doesn't fit, then writes Python anyway. With Blender HTTP there's only the code.
- **Can reduce round-trips.** When the MCP setup offers granular per-action tools, *"add a cube, name it, colour it, move it, take a screenshot"* can become five back-and-forths. In Blender HTTP it's one short script.
- **Screenshots don't have to fill up memory.** Many MCP screenshot tools return images as base64 inline in the response — a full screenshot is ~1.3 MB of context the AI carries. Blender HTTP saves them to disk by default; the AI only sees an image if it asks.
- **Cooperative cancellation.** The official Blender MCP's `execute_blender_code` runs every script to completion. Blender HTTP supports a stop request that interrupts cleanly at the next `yield` in a generator-based script.

> These trade-offs depend on the MCP server implementation, the AI client, and the task. They land hardest for **script-heavy** workflows (procedural modelling, multi-step scene edits, audits). For workflows that fit cleanly into structured tool calls, MCP may suit you better.


## Install

**Requirements:** Blender **4.2+**. No external Python packages — the add-on uses only Blender's bundled Python and the stdlib. The optional client (`client/send.py`) needs Python 3.x with stdlib only.

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
   curl http://127.0.0.1:9877/health
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
> 6. **Wait for me to confirm I've clicked Start.** Then verify by curling `http://127.0.0.1:9877/health` — expect `{"ok": true}`.
>
> Don't proceed if you can't confirm my Blender version. Don't overwrite anything without asking. Keep output concise — I want progress, not a tutorial.

---


## What it looks like

Send a Python script with `curl`:

```bash
curl -s localhost:9877 --data-binary "
import bpy
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1))
'cube made'
"
```

Blender runs it; you get back `{"ok": true, "output": "", "result": "cube made"}`.

More examples — a script that builds a model step by step, a one-line multi-angle audit, a cancellation demo — live in [`examples/`](examples/).

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
