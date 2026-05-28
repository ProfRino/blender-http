"""Workspace path resolution.

The workspace is the project root where all generated content lives.
Layout:
    <workspace>/
    └── output/
        ├── snapshots/
        ├── audits/
        └── renders/

Resolution order (highest priority first):
    1. UI override (set via N-panel, session-only)
    2. BLENDER_HTTP_WORKSPACE environment variable
    3. ~/blender_http (default)

The path `<workspace>/output` is injected into every script's namespace as `OUTPUT`,
and the workspace root as `WORKSPACE`.
"""

import os
import time
from pathlib import Path

_DEFAULT = Path.home() / "blender_http"
_override: str | None = None


def set_override(path: str | None):
    """Set or clear the UI override. Pass None or '' to clear."""
    global _override
    _override = path.strip() if path else None


def workspace() -> Path:
    if _override:
        return Path(_override).expanduser()
    env = os.environ.get("BLENDER_HTTP_WORKSPACE")
    if env:
        return Path(env).expanduser()
    return _DEFAULT


def output_dir() -> Path:
    p = workspace() / "output"
    p.mkdir(parents=True, exist_ok=True)
    return p


def snapshots_dir() -> Path:
    p = output_dir() / "snapshots"
    p.mkdir(parents=True, exist_ok=True)
    return p


def audits_dir() -> Path:
    p = output_dir() / "audits"
    p.mkdir(parents=True, exist_ok=True)
    return p


def renders_dir() -> Path:
    p = output_dir() / "renders"
    p.mkdir(parents=True, exist_ok=True)
    return p


def timestamped_audit_dir() -> Path:
    p = audits_dir() / time.strftime("%Y%m%d_%H%M%S")
    p.mkdir(parents=True, exist_ok=True)
    return p


def timestamped_snapshot_path() -> Path:
    return snapshots_dir() / f"{time.strftime('%Y%m%d_%H%M%S')}.png"
