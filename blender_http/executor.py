"""Timer-driven script execution on Blender's main thread."""

import ast
import json
import sys
import traceback

import bpy

from . import jobs, streaming, workspace, inspect as _inspect_mod, repl
from . import snapshot as snap


# --- stdout / stderr capture --------------------------------------------------

class _LineWriter:
    def __init__(self, job, original):
        self.job = job
        self.original = original
        self._buf = ""

    def write(self, s):
        try:
            self.original.write(s)
        except Exception:
            pass
        if not isinstance(s, str):
            return
        self._buf += s
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            streaming.emit(self.job, "stdout", {"line": line})

    def flush(self):
        try:
            self.original.flush()
        except Exception:
            pass


class _Capture:
    def __init__(self, job):
        self.job = job
        self._old_out = None
        self._old_err = None

    def __enter__(self):
        self._old_out = sys.stdout
        self._old_err = sys.stderr
        sys.stdout = _LineWriter(self.job, self._old_out)
        sys.stderr = _LineWriter(self.job, self._old_err)
        return self

    def __exit__(self, *exc):
        for stream in (sys.stdout, sys.stderr):
            if isinstance(stream, _LineWriter) and stream._buf:
                streaming.emit(self.job, "stdout", {"line": stream._buf})
                stream._buf = ""
        sys.stdout = self._old_out
        sys.stderr = self._old_err
        return False


# --- helpers ------------------------------------------------------------------

def _exec_with_last_expr(code: str, namespace: dict):
    """exec the code; return the value of the trailing expression (if any)."""
    tree = ast.parse(code, mode="exec")
    last_expr = None
    if tree.body and isinstance(tree.body[-1], ast.Expr):
        last_expr = tree.body.pop().value
    exec(compile(tree, "<blender_http_job>", "exec"), namespace)
    if last_expr is None:
        return None
    return eval(compile(ast.Expression(last_expr), "<blender_http_job>", "eval"), namespace)


def _jsonify(value):
    try:
        json.dumps(value)
        return value
    except TypeError:
        return repr(value)


def _make_progress(job):
    def progress(current, total=None, label=None):
        streaming.emit(job, "progress", {
            "current": current,
            "total": total,
            "label": label,
        })
    return progress


def _make_snapshot(job):
    def snapshot(path, mode="viewport", size=None, thumb=False):
        result = snap.snapshot(path, mode=mode, size=size)
        evt_data = {"path": result, "mode": mode}
        if size is not None:
            evt_data["size"] = size
        if thumb:
            try:
                evt_data["thumb"] = snap.thumbnail_b64(size=128)
            except Exception as e:
                evt_data["thumb_error"] = str(e)
        streaming.emit(job, "snapshot", evt_data)
        return result
    return snapshot


def _make_audit(job):
    def audit(output_dir, **kwargs):
        results = snap.audit(output_dir, **kwargs)
        streaming.emit(job, "audit", {"dir": output_dir, "views": results})
        return results
    return audit


def _inject_helpers(namespace: dict, job):
    """Add the per-job callable helpers to a namespace (idempotent overwrite)."""
    namespace["progress"] = _make_progress(job)
    namespace["snapshot"] = _make_snapshot(job)
    namespace["audit"] = _make_audit(job)
    namespace["inspect"] = _inspect_mod.inspect
    namespace["find"] = _inspect_mod.find
    namespace["bbox"] = _inspect_mod.bbox
    namespace["scene_hash"] = _inspect_mod.scene_hash


def _fresh_namespace(job) -> dict:
    ns = {
        "__name__": "__blender_http__",
        "bpy": bpy,
        "WORKSPACE": str(workspace.workspace()),
        "OUTPUT": str(workspace.output_dir()),
    }
    _inject_helpers(ns, job)
    return ns


def _batch_generator(job):
    """Generator: run each batch script in its own fresh namespace, yield between."""
    for i, script in enumerate(job.scripts):
        yield f"batch {i+1}/{len(job.scripts)}"
        ns = _fresh_namespace(job)
        try:
            with _Capture(job):
                result = _exec_with_last_expr(script, ns)
            job.batch_results.append({"ok": True, "result": _jsonify(result)})
        except Exception as e:
            tb = traceback.format_exc()
            job.batch_results.append({
                "ok": False,
                "error": str(e),
                "traceback": tb,
            })
            if job.stop_on_error:
                # Stop — leave remaining slots unfilled
                return


# --- job lifecycle ------------------------------------------------------------

def _start_job(job):
    import time as _time
    if job.cancel_requested:
        _cancel(job)
        return None

    job.status = "running"
    job.started_at = _time.time()
    streaming.emit(job, "started", {"job_id": job.id})

    # Batch mode --------------------------------------------------------
    if job.scripts is not None:
        job.generator = _batch_generator(job)
        return job.pace

    # Build the namespace ----------------------------------------------
    if job.session_id is not None:
        # REPL: persistent namespace across calls; refresh per-job helpers each time
        namespace = repl.get_session(job.session_id)
        namespace["WORKSPACE"] = str(workspace.workspace())
        namespace["OUTPUT"] = str(workspace.output_dir())
        _inject_helpers(namespace, job)
    else:
        namespace = _fresh_namespace(job)

    # Exec the script body ----------------------------------------------
    try:
        with _Capture(job):
            result = _exec_with_last_expr(job.code, namespace)
    except Exception as e:
        _fail(job, e)
        return None

    build = namespace.get("build")
    if callable(build):
        try:
            with _Capture(job):
                gen = build()
        except Exception as e:
            _fail(job, e)
            return None
        if gen is None or not hasattr(gen, "__iter__"):
            _complete(job, _jsonify(gen if gen is not None else result))
            return None
        job.generator = iter(gen)
        return job.pace

    _complete(job, _jsonify(result))
    return None


def _step_job(job):
    if job.cancel_requested:
        _cancel(job)
        return None
    try:
        with _Capture(job):
            label = next(job.generator)
    except StopIteration:
        _complete(job, None)
        return None
    except Exception as e:
        _fail(job, e)
        return None
    streaming.emit(job, "step", {
        "label": str(label) if label is not None else None,
        "index": job.step_index,
    })
    job.step_index += 1
    return job.pace


def _complete(job, result):
    import time as _time
    job.result = result
    job.finished_at = _time.time()
    with job.event_cond:
        job.status = "completed"
        job.event_cond.notify_all()
    streaming.emit(job, "completed", {"result": result})
    jobs.clear_current()


def _fail(job, exc):
    tb = traceback.format_exc()
    job.error = str(exc)
    job.traceback = tb
    with job.event_cond:
        job.status = "failed"
        job.event_cond.notify_all()
    streaming.emit(job, "failed", {"error": str(exc), "traceback": tb})
    jobs.clear_current()


def _cancel(job):
    with job.event_cond:
        job.status = "cancelled"
        job.event_cond.notify_all()
    streaming.emit(job, "cancelled", {})
    jobs.clear_current()


# --- timer tick ---------------------------------------------------------------

def _tick():
    try:
        job = jobs.current_job()
        if job is None:
            job = jobs.pop_queued()
            if job is None:
                return 0.1
            interval = _start_job(job)
            return interval if interval is not None else 0.0
        if job.status == "running" and job.generator is not None:
            interval = _step_job(job)
            return interval if interval is not None else 0.0
        return 0.0
    except Exception:
        traceback.print_exc()
        return 0.5


def start():
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=0.0)


def stop():
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
