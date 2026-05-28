"""Persistent script namespaces (REPL sessions).

Submit a script via POST /repl?session=<id> and the namespace persists across
calls for that session. Helpers defined once, variables retained, no re-imports.
"""

import bpy

_sessions: dict = {}


def get_session(session_id: str) -> dict:
    """Return or create the persistent namespace for a session."""
    ns = _sessions.get(session_id)
    if ns is None:
        ns = {
            "__name__": f"__bhttp_repl_{session_id}__",
            "bpy": bpy,
        }
        _sessions[session_id] = ns
    return ns


def forget_session(session_id: str) -> bool:
    return _sessions.pop(session_id, None) is not None


def list_sessions() -> list:
    return list(_sessions.keys())


def reset():
    _sessions.clear()
