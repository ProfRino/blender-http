# Blender HTTP Protocol

Default base URL: `http://127.0.0.1:9876`. All endpoints accept and return UTF-8.

JSON responses honor `Accept-Encoding: gzip` and compress payloads >= 1 KB. Typical compression ratio 3–5×.

## Endpoints

### `POST /`

Synchronous execution (blender-agent compatible).

**Request body:** raw Python source.

**Response 200, success:**

```json
{"ok": true, "output": "<captured stdout>", "result": <last-expression-as-json>}
```

**Response 200, error:**

```json
{"ok": false, "output": "<stdout so far>", "error": "<exception message>"}
```

**Response 504** when execution exceeds the sync timeout (default 600s).

If the script defines `build()` returning a generator, the server runs all steps before responding.

### `POST /jobs`

Async submission.

**Request body:** raw Python source.

**Response 202:**

```json
{"job_id": "abc123def456", "status": "queued"}
```

### `GET /jobs/{id}`

Job status snapshot.

```json
{
  "job_id": "abc123def456",
  "status": "queued|running|completed|failed|cancelled",
  "step_index": 7,
  "error": null
}
```

### `GET /jobs/{id}/stream`

Server-Sent Events stream from the start of the job until terminal status. Replays past events on connect, then streams live.

```
event: started
data: {"job_id": "abc123def456"}

event: stdout
data: {"line": "creating base slab"}

event: step
data: {"label": "base slab", "index": 0}

event: progress
data: {"current": 3, "total": 12, "label": "column 3/12"}

event: completed
data: {"result": null}
```

Consume with `curl -N http://127.0.0.1:9876/jobs/<id>/stream` or any SSE client.

### `DELETE /jobs/{id}`

Cooperative cancel. Sets `cancel_requested`; the executor stops at the next yield (or before starting if still queued).

```json
{"cancelled": true, "job_id": "abc123def456"}
```

### `GET /health`

```json
{"ok": true}
```

### `GET /inspect`

Compact scene summary.

| Query | Default | Meaning |
|---|---|---|
| `detail` | `brief` | `brief` (name, type, location) or `full` (+ rotation, scale, dimensions, materials, parent, etc.) |

```json
{
  "frame": 1, "engine": "BLENDER_EEVEE", "active": "Cube",
  "object_count": 3, "mesh_count": 1,
  "materials": ["Material"], "collections": ["Collection"],
  "objects": [{"name": "Cube", "type": "MESH", "location": [0,0,0]}, ...]
}
```

### `POST /find`

Body: `{"pattern": "Cu*", "types": ["MESH"]}` — `types` optional. `pattern` uses fnmatch globbing.

```json
[{"name": "Cube", "type": "MESH", "location": [0,0,0]}, ...]
```

### `GET /bbox?name=<name_or_pattern>`

Returns the world bounding box. Without `name`, returns the bbox of all visible mesh objects.

```json
{"min": [-1,-1,-1], "max": [1,1,1], "centre": [0,0,0], "size": [2,2,2], "objects": ["Cube"]}
```

### `GET /scene-hash`

Returns a 16-char hex hash of the current scene state. Use as the `if-changed` parameter for `/snapshot` to poll-without-rendering.

```json
"89980d9f49705254"
```

### `POST /batch`

Run multiple scripts sequentially in one request. Each script runs in a fresh namespace; the executor yields between them so the UI stays responsive.

**Body:**

```json
{
  "scripts": ["code1", "code2", ...],
  "stop_on_error": true
}
```

**Response:**

```json
{
  "ok": true,
  "duration_ms": 87,
  "results": [
    {"ok": true, "result": "a"},
    {"ok": true, "result": "b"},
    {"ok": false, "error": "NameError: ...", "traceback": "..."}
  ]
}
```

### `POST /repl?session=<id>`

Like `POST /`, but the namespace **persists across calls for that session**. Define a helper or variable once, reuse it in later calls.

**Body:** raw Python.

**Response:**

```json
{"ok": true, "output": "", "result": 42, "session": "demo"}
```

### `GET /sessions`

List active REPL session IDs.

```json
["demo", "agent_1"]
```

### `GET /snapshot`

Capture one image of the current scene.

| Query | Default | Meaning |
|---|---|---|
| `mode` | `viewport` | `viewport` (3D viewport area as displayed) · `opengl` (active camera, materials, fast) · `render` (full Cycles/Eevee, slow) |
| `save` | *unset* | If set, persist the PNG to disk and return JSON `{path, mode, size, scene_hash}` instead of bytes. Accepts: `true` (uses `<workspace>/output/snapshots/<timestamp>.png`), an absolute path, or a path relative to `<workspace>/output/`. |
| `size` | *unset* | Maximum pixel dimension. Downscales `opengl` / `render` (preserves aspect). Tiny previews: `size=256` -> ~25 KB PNG vs ~1 MB. Ignored for `viewport` mode. |
| `if-changed` | *unset* | If provided and the current `scene_hash()` equals this value, returns `304 Not Modified` with no body. Use the `ETag` header from a previous response. |

If `save` is not set, returns raw `image/png` bytes with an `ETag` header equal to the current scene hash.

### `POST /audit`

Render the canonical 6-view audit suite (`01_front`, `02_back`, `03_left`, `04_right`, `05_top`, `06_isometric`). Cameras are placed automatically with bbox-aware framing, then removed.

| Query | Default | Meaning |
|---|---|---|
| `mode` | `opengl` | `opengl` (fast) or `render` (full) |
| `dir` | `<workspace>/output/audits/<timestamp>/` | Output directory; created if missing |

**Response 200:**

```json
{
  "dir": "C:/Users/.../blender_http_audits/20260528_154212",
  "views": {
    "01_front":     "C:/.../01_front.png",
    "02_back":      "C:/.../02_back.png",
    "03_left":      "C:/.../03_left.png",
    "04_right":     "C:/.../04_right.png",
    "05_top":       "C:/.../05_top.png",
    "06_isometric": "C:/.../06_isometric.png"
  }
}
```

## Event types

| Type | When | Data |
|---|---|---|
| `started` | Job picked up by the executor | `{job_id}` |
| `stdout` | Each line printed by the script | `{line}` |
| `step` | Each `yield` from `build()` or a batch boundary | `{label, index}` |
| `progress` | Script calls `progress(current, total, label)` | `{current, total, label}` |
| `snapshot` | Script calls `snapshot(path, mode, size, thumb)` | `{path, mode, size?, thumb?}` (`thumb` is a base64 PNG when `thumb=True`) |
| `audit` | Script calls `audit(dir, mode)` | `{dir, views}` |
| `completed` | Job finished without error | `{result}` |
| `failed` | Exception during exec | `{error, traceback}` |
| `cancelled` | Job cancelled via DELETE | `{}` |

## Script execution model

- Code runs in a fresh namespace per job (or a persistent one with `/repl`). Preloaded: `bpy`, `progress`, `snapshot`, `audit`, `inspect`, `find`, `bbox`, `scene_hash`, `OUTPUT`, `WORKSPACE`.
- `WORKSPACE` is the active workspace root (`str`). `OUTPUT` is `<WORKSPACE>/output/` (auto-created).
- Workspace resolution: N-panel override > `BLENDER_HTTP_WORKSPACE` env var > `~/blender_http` default.
- **Sync mode** (no `build`): the entire script runs in one timer tick. UI freezes during that tick.
- **Generator mode** (`build()` returns a generator): one `next()` call per timer tick. Default tick interval 0.05s (configurable in the N-panel via the `port`/`host` panel later versions).
- Output (`stdout` + `stderr`) is captured per-job and emitted as `stdout` events line by line.
- `result` is the value of the last expression in sync mode. Generator mode currently returns `null`.
