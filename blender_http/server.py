"""HTTP server: sync + async + SSE + cancel + snapshot + audit + inspect + batch + repl."""

import gzip
import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from . import executor, jobs, streaming, workspace, repl


_server = None
_thread = None
_SYNC_TIMEOUT = 600        # seconds
_SNAPSHOT_TIMEOUT = 120    # seconds
_AUDIT_TIMEOUT = 600       # seconds
_HELPER_TIMEOUT = 30       # seconds (inspect/find/bbox/scene-hash)
_BATCH_TIMEOUT = 1800      # seconds
_GZIP_MIN_BYTES = 1024     # don't compress tiny payloads


def _default_audit_dir() -> str:
    return str(workspace.timestamped_audit_dir())


def _resolve_save_path(save_param: str) -> str:
    """Resolve the ?save= query value to an absolute path.

    Empty / 'true' / '1' -> workspace snapshots dir with timestamp.
    Absolute path        -> used as-is.
    Relative path        -> resolved under <workspace>/output/.
    """
    val = (save_param or "").strip()
    if not val or val.lower() in ("true", "1", "yes"):
        return str(workspace.timestamped_snapshot_path())
    p = os.path.expanduser(val)
    if not os.path.isabs(p):
        p = str(workspace.output_dir() / p)
    return p


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return  # silence default request logging

    # ---- helpers --------------------------------------------------------

    def _read_body(self) -> str:
        n = int(self.headers.get("Content-Length", 0) or 0)
        return self.rfile.read(n).decode("utf-8") if n else ""

    def _json(self, status: int, payload: dict, extra_headers: list = None):
        body = json.dumps(payload).encode("utf-8")
        accept_enc = self.headers.get("Accept-Encoding", "") or ""
        use_gzip = "gzip" in accept_enc and len(body) >= _GZIP_MIN_BYTES
        if use_gzip:
            body = gzip.compress(body)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        if use_gzip:
            self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra_headers or []):
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ---- POST -----------------------------------------------------------

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        body = self._read_body()

        if path == "/":
            job = jobs.submit(body, pace=0.0)
            with job.event_cond:
                if not job.event_cond.wait_for(
                    lambda: job.status in ("completed", "failed", "cancelled"),
                    timeout=_SYNC_TIMEOUT,
                ):
                    self._json(504, {"ok": False, "error": "sync execution timed out"})
                    return
            output_lines = [
                e["data"]["line"] for e in job.events if e["type"] == "stdout"
            ]
            output = "\n".join(output_lines)
            if output_lines:
                output += "\n"
            if job.status == "completed":
                self._json(200, {"ok": True, "output": output, "result": job.result})
            else:
                self._json(200, {
                    "ok": False,
                    "output": output,
                    "error": job.error or job.status,
                })
            return

        if path == "/jobs":
            job = jobs.submit(body, pace=0.05)
            self._json(202, {"job_id": job.id, "status": job.status})
            return

        if path == "/audit":
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            mode = (query.get("mode", ["opengl"]) or ["opengl"])[0]
            out_dir = (query.get("dir", [None]) or [None])[0] or _default_audit_dir()
            self._handle_audit(mode, out_dir)
            return

        if path == "/batch":
            self._handle_batch(body)
            return

        if path == "/repl":
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            session = (query.get("session", [None]) or [None])[0]
            if not session:
                self._json(400, {"error": "session query param required"})
                return
            self._handle_repl(session, body)
            return

        if path == "/find":
            self._handle_find(body)
            return

        self._json(404, {"error": f"no POST handler for {path}"})

    # ---- GET ------------------------------------------------------------

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/health":
            self._json(200, {"ok": True})
            return

        if path == "/snapshot":
            mode = (query.get("mode", ["viewport"]) or ["viewport"])[0]
            save = (query.get("save", [None]) or [None])[0]
            size = (query.get("size", [None]) or [None])[0]
            if_changed = (query.get("if-changed", [None]) or [None])[0]
            try:
                size_int = int(size) if size else None
            except ValueError:
                self._json(400, {"error": f"invalid size: {size!r}"})
                return
            self._handle_snapshot(mode, save=save, size=size_int, if_changed=if_changed)
            return

        if path == "/inspect":
            detail = (query.get("detail", ["brief"]) or ["brief"])[0]
            self._handle_helper_call(f"inspect({detail!r})")
            return

        if path == "/bbox":
            name = (query.get("name", [None]) or [None])[0]
            code = f"bbox({name!r})" if name else "bbox()"
            self._handle_helper_call(code)
            return

        if path == "/scene-hash":
            self._handle_helper_call("scene_hash()")
            return

        if path == "/sessions":
            self._handle_helper_call(
                "__import__('bl_ext.user_default.blender_http.repl', fromlist=['list_sessions']).list_sessions()"
            )
            return

        if path.startswith("/jobs/") and path.endswith("/stream"):
            jid = path[len("/jobs/"):-len("/stream")]
            self._stream_job(jid)
            return

        if path.startswith("/jobs/"):
            jid = path[len("/jobs/"):]
            job = jobs.get(jid)
            if not job:
                self._json(404, {"error": "no such job"})
                return
            self._json(200, {
                "job_id": job.id,
                "status": job.status,
                "step_index": job.step_index,
                "error": job.error,
            })
            return

        self._json(404, {"error": f"no GET handler for {path}"})

    # ---- DELETE ---------------------------------------------------------

    def do_DELETE(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/jobs/"):
            jid = path[len("/jobs/"):]
            if jobs.cancel(jid):
                self._json(200, {"cancelled": True, "job_id": jid})
            else:
                self._json(404, {"error": "no such job"})
            return
        self._json(404, {"error": f"no DELETE handler for {path}"})

    # ---- snapshot / audit (delegated to the main-thread executor) -------

    def _await_job(self, code: str, timeout: int):
        job = jobs.submit(code, pace=0.0)
        with job.event_cond:
            ok = job.event_cond.wait_for(
                lambda: job.status in ("completed", "failed", "cancelled"),
                timeout=timeout,
            )
        return job, ok

    def _snapshot_call(self, path: str, mode: str, size):
        """Build a snapshot() call string with optional size, bundled with scene_hash()."""
        size_part = f", size={int(size)}" if size else ""
        return f"snapshot({path!r}, mode={mode!r}{size_part}); scene_hash()"

    def _handle_snapshot(self, mode: str, save=None, size=None, if_changed=None):
        """If `save` is provided, persist to that path and return JSON.
        Otherwise capture to a tempfile and return PNG bytes.
        If `if_changed` matches current scene_hash, return 304.
        `size` downscales opengl/render output (max pixel dim)."""
        # Conditional check
        if if_changed:
            hjob, hok = self._await_job("scene_hash()", _HELPER_TIMEOUT)
            if hok and hjob.status == "completed" and hjob.result == if_changed:
                self.send_response(304)
                self.send_header("ETag", str(hjob.result))
                self.end_headers()
                return

        # Persist path mode
        if save is not None:
            target = _resolve_save_path(save)
            code = self._snapshot_call(target, mode, size)
            job, ok = self._await_job(code, _SNAPSHOT_TIMEOUT)
            if not ok:
                self._json(504, {"error": "snapshot timed out"})
                return
            if job.status != "completed":
                self._json(500, {"error": job.error or job.status})
                return
            self._json(200, {
                "path": target,
                "mode": mode,
                "size": size,
                "scene_hash": job.result,
            })
            return

        # Bytes mode (tempfile)
        fd, tmp_path = tempfile.mkstemp(suffix=".png", prefix="bhttp_snap_")
        os.close(fd)
        code = self._snapshot_call(tmp_path, mode, size)
        job, ok = self._await_job(code, _SNAPSHOT_TIMEOUT)
        if not ok:
            self._json(504, {"error": "snapshot timed out"})
            self._cleanup_path(tmp_path)
            return
        if job.status != "completed":
            self._json(500, {"error": job.error or job.status})
            self._cleanup_path(tmp_path)
            return
        try:
            with open(tmp_path, "rb") as f:
                png = f.read()
        except FileNotFoundError:
            self._json(500, {"error": "snapshot file was not created"})
            return
        finally:
            self._cleanup_path(tmp_path)
        etag = str(job.result) if job.result else None
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        if etag:
            self.send_header("ETag", etag)
        self.send_header("Content-Length", str(len(png)))
        self.end_headers()
        try:
            self.wfile.write(png)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _handle_helper_call(self, code: str, timeout: int = None):
        """Submit a one-line helper call, return the JSON result."""
        job, ok = self._await_job(code, timeout or _HELPER_TIMEOUT)
        if not ok:
            self._json(504, {"error": "helper call timed out"})
            return
        if job.status != "completed":
            self._json(500, {"error": job.error or job.status})
            return
        self._json(200, job.result)

    def _handle_find(self, body: str):
        try:
            params = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid JSON"})
            return
        pattern = params.get("pattern", "*")
        types = params.get("types")
        code = f"find({pattern!r}, {types!r})"
        self._handle_helper_call(code)

    def _handle_batch(self, body: str):
        try:
            params = json.loads(body)
        except json.JSONDecodeError:
            self._json(400, {"error": "invalid JSON body"})
            return
        scripts = params.get("scripts")
        if not isinstance(scripts, list) or not scripts:
            self._json(400, {"error": "scripts must be a non-empty list"})
            return
        stop_on_error = bool(params.get("stop_on_error", True))
        job = jobs.submit_batch(scripts, stop_on_error=stop_on_error)
        with job.event_cond:
            ok = job.event_cond.wait_for(
                lambda: job.status in ("completed", "failed", "cancelled"),
                timeout=_BATCH_TIMEOUT,
            )
        if not ok:
            self._json(504, {"error": "batch timed out", "job_id": job.id})
            return
        duration_ms = None
        if job.finished_at and job.started_at:
            duration_ms = int((job.finished_at - job.started_at) * 1000)
        self._json(200, {
            "ok": job.status == "completed" and all(r.get("ok") for r in job.batch_results),
            "duration_ms": duration_ms,
            "results": job.batch_results,
        })

    def _handle_repl(self, session_id: str, body: str):
        job = jobs.submit(body, pace=0.0, session_id=session_id)
        with job.event_cond:
            ok = job.event_cond.wait_for(
                lambda: job.status in ("completed", "failed", "cancelled"),
                timeout=_SYNC_TIMEOUT,
            )
        if not ok:
            self._json(504, {"ok": False, "error": "repl call timed out"})
            return
        output = "\n".join(e["data"]["line"] for e in job.events if e["type"] == "stdout")
        if output:
            output += "\n"
        if job.status == "completed":
            self._json(200, {
                "ok": True,
                "output": output,
                "result": job.result,
                "session": session_id,
            })
        else:
            self._json(200, {
                "ok": False,
                "output": output,
                "error": job.error or job.status,
                "session": session_id,
            })

    def _handle_audit(self, mode: str, out_dir: str):
        code = f"audit({out_dir!r}, mode={mode!r})"
        job, ok = self._await_job(code, _AUDIT_TIMEOUT)
        if not ok:
            self._json(504, {"error": "audit timed out"})
            return
        if job.status != "completed":
            self._json(500, {"error": job.error or job.status})
            return
        self._json(200, {
            "dir": out_dir,
            "views": job.result or {},
        })

    def _cleanup_path(self, path: str):
        try:
            os.unlink(path)
        except OSError:
            pass

    # ---- SSE stream -----------------------------------------------------

    def _stream_job(self, jid: str):
        job = jobs.get(jid)
        if not job:
            self._json(404, {"error": "no such job"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        sent = 0
        try:
            while True:
                with job.event_cond:
                    terminal = job.status in ("completed", "failed", "cancelled")
                    while not terminal and sent >= len(job.events):
                        job.event_cond.wait(timeout=10)
                        terminal = job.status in ("completed", "failed", "cancelled")
                    to_send = list(job.events[sent:])
                    sent = len(job.events)
                for evt in to_send:
                    self.wfile.write(streaming.format_sse(evt).encode("utf-8"))
                self.wfile.flush()
                if terminal and sent >= len(job.events):
                    return
        except (BrokenPipeError, ConnectionResetError):
            return


# ---- module-level controls ---------------------------------------------------

def start(host: str = "127.0.0.1", port: int = 9876) -> bool:
    global _server, _thread
    if _server is not None:
        return False
    _server = ThreadingHTTPServer((host, port), _Handler)
    _thread = threading.Thread(
        target=_server.serve_forever, daemon=True, name="blender_http_server"
    )
    _thread.start()
    executor.start()
    return True


def stop() -> bool:
    global _server, _thread
    if _server is None:
        return False
    jobs.cancel_all_active()
    executor.stop()
    _server.shutdown()
    _server.server_close()
    _server = None
    _thread = None
    jobs.reset()
    return True


def is_running() -> bool:
    return _server is not None


def address() -> tuple:
    if _server is None:
        return ("", 0)
    return _server.server_address
