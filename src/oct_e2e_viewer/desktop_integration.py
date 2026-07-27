"""
desktop_integration.py

Registers OCT E2E Viewer as the double-click handler for .e2e/.E2E files on
Linux (user-level install, no sudo). Installs a .desktop launcher (with
icon) and a MIME type definition, both read from the packaged resources, so
this works whether the app was installed with pipx or `pip install -e .` --
no local git checkout required.
"""

import shutil
import subprocess
import sys
from importlib.resources import files
from pathlib import Path

DESKTOP_ENTRY_NAME = "oct-e2e-viewer.desktop"
MIME_PACKAGE_NAME = "x-heyex-e2e.xml"


def _find_launcher():
    # sys.argv[0] is the exact script the user invoked -- prefer it over a
    # PATH search, which could resolve to a *different* install of this
    # package if more than one is on PATH. Falls back to PATH only for the
    # `python -m oct_e2e_viewer` case, where argv[0] isn't the console script.
    argv0 = Path(sys.argv[0]).resolve()
    if argv0.name == "oct-e2e-viewer":
        return str(argv0)
    launcher = shutil.which("oct-e2e-viewer")
    if launcher is None:
        raise SystemExit("oct-e2e-viewer not found on PATH.")
    return launcher


def install_desktop_entry():
    launcher = _find_launcher()
    resources = files("oct_e2e_viewer") / "resources"
    icon_path = resources / "icon.png"

    mime_dir = Path.home() / ".local/share/mime/packages"
    mime_dir.mkdir(parents=True, exist_ok=True)
    (mime_dir / MIME_PACKAGE_NAME).write_bytes((resources / MIME_PACKAGE_NAME).read_bytes())
    subprocess.run(["update-mime-database", str(Path.home() / ".local/share/mime")], check=True)

    apps_dir = Path.home() / ".local/share/applications"
    apps_dir.mkdir(parents=True, exist_ok=True)
    template = (resources / "oct-e2e-viewer.desktop.in").read_text()
    desktop_entry = template.replace("__LAUNCHER__", launcher).replace("__ICON__", str(icon_path))
    (apps_dir / DESKTOP_ENTRY_NAME).write_text(desktop_entry)
    subprocess.run(["update-desktop-database", str(apps_dir)], check=True)

    subprocess.run(["xdg-mime", "default", DESKTOP_ENTRY_NAME, "application/x-heyex-e2e"], check=True)

    print(f"Registered {launcher} as the default handler for .e2e/.E2E files.")
    print("(If your file manager cached the old file type, you may need to log out/in.)")
