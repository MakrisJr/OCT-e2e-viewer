"""
recent_files.py

Tracks the most recently opened .E2E files, persisted as JSON under
~/.config, so the File menu can offer an "Open Recent" list across
sessions.
"""

import json
from pathlib import Path

MAX_RECENT_FILES = 10
CONFIG_DIR = Path.home() / ".config" / "oct-e2e-viewer"
RECENT_FILES_PATH = CONFIG_DIR / "recent_files.json"


def load_recent_files():
    try:
        paths = json.loads(RECENT_FILES_PATH.read_text())
    except (FileNotFoundError, ValueError):
        return []
    return [p for p in paths if isinstance(p, str)]


def add_recent_file(path):
    path = str(Path(path).resolve())
    paths = [p for p in load_recent_files() if p != path]
    paths.insert(0, path)
    paths = paths[:MAX_RECENT_FILES]
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    RECENT_FILES_PATH.write_text(json.dumps(paths, indent=2))
    return paths


def clear_recent_files():
    RECENT_FILES_PATH.unlink(missing_ok=True)
