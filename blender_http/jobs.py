"""Job queue and lifecycle for Blender HTTP."""

import threading
import uuid
from collections import deque

_lock = threading.Lock()
_queue: deque = deque()
_jobs: dict = {}
_current = None
MAX_HISTORY = 50


class Job:
    """A unit of script execution.

    Three flavours:
      - plain script:  code is a Python string
      - batch:         scripts is a list of Python strings
      - REPL:          code + session_id, namespace persists across calls
    """

    def __init__(
        self,
        code: str = None,
        pace: float = 0.05,
        scripts: list = None,
        stop_on_error: bool = True,
        session_id: str = None,
    ):
        import time as _time
        self.id = uuid.uuid4().hex[:12]
        self.code = code
        self.pace = max(0.0, float(pace))
        self.status = "queued"   # queued | running | completed | failed | cancelled
        self.step_index = 0
        self.events: list = []
        self.event_cond = threading.Condition()
        self.generator = None
        self.cancel_requested = False
        self.result = None
        self.error = None
        self.traceback = None
        # batch
        self.scripts = scripts
        self.stop_on_error = stop_on_error
        self.batch_results: list = []
        # repl
        self.session_id = session_id
        # timing
        self.created_at = _time.time()
        self.started_at: float = 0.0
        self.finished_at: float = 0.0


def submit(code: str, pace: float = 0.05, session_id: str = None) -> Job:
    job = Job(code=code, pace=pace, session_id=session_id)
    with _lock:
        _jobs[job.id] = job
        _queue.append(job)
        _trim_history_locked()
    return job


def submit_batch(scripts: list, stop_on_error: bool = True, pace: float = 0.0) -> Job:
    job = Job(scripts=scripts, stop_on_error=stop_on_error, pace=pace)
    with _lock:
        _jobs[job.id] = job
        _queue.append(job)
        _trim_history_locked()
    return job


def _trim_history_locked():
    if len(_jobs) > MAX_HISTORY:
        terminals = [
            (jid, j) for jid, j in _jobs.items()
            if j.status in ("completed", "failed", "cancelled")
        ]
        terminals.sort(key=lambda kv: kv[1].id)
        for jid, _ in terminals[: len(_jobs) - MAX_HISTORY]:
            _jobs.pop(jid, None)


def get(job_id: str):
    with _lock:
        return _jobs.get(job_id)


def pop_queued():
    """Pick the next queued job. Sets it as current. Returns None if busy or empty."""
    global _current
    with _lock:
        if _current is not None:
            return None
        if _queue:
            _current = _queue.popleft()
            return _current
    return None


def current_job():
    with _lock:
        return _current


def clear_current():
    global _current
    with _lock:
        _current = None


def cancel(job_id: str) -> bool:
    """Mark a job for cancellation. The executor will pick it up on the next tick."""
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return False
        if job.status in ("completed", "failed", "cancelled"):
            return False
        job.cancel_requested = True
    return True


def cancel_all_active():
    """Force-cancel any queued or running job — used on server shutdown."""
    with _lock:
        active = [j for j in _jobs.values() if j.status in ("queued", "running")]
    for j in active:
        with j.event_cond:
            j.status = "cancelled"
            j.event_cond.notify_all()


def reset():
    """Clear all state — called when server stops."""
    global _current
    with _lock:
        _queue.clear()
        _jobs.clear()
        _current = None
