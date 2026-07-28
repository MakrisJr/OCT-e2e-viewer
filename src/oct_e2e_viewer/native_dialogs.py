"""
native_dialogs.py

Cross-platform file-open/save dialogs. On Windows and macOS, Tkinter's
built-in dialogs already delegate to the native OS picker. On Linux, Tk's
built-in dialog is its own dated Tcl/Tk widget rather than the desktop's
file manager UI, so here we shell out to whichever native dialog tool is
available (kdialog on KDE, zenity elsewhere) and fall back to Tk's dialog
if neither is installed.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from tkinter import filedialog

_IS_LINUX = sys.platform.startswith("linux")


def ask_open_filename(title, filetypes):
    if _IS_LINUX:
        path = _linux_open(title, filetypes)
        if path is not None:
            return path
    return filedialog.askopenfilename(title=title, filetypes=filetypes)


def ask_save_filename(title, filetypes, defaultextension, initialfile):
    if _IS_LINUX:
        path = _linux_save(title, filetypes, initialfile)
        if path is not None:
            return _with_default_extension(path, defaultextension)
    return filedialog.asksaveasfilename(
        title=title,
        filetypes=filetypes,
        defaultextension=defaultextension,
        initialfile=initialfile,
    )


def _with_default_extension(path, defaultextension):
    if path and defaultextension and not Path(path).suffix:
        return path + defaultextension
    return path


def _linux_open(title, filetypes):
    if shutil.which("kdialog"):
        cmd = ["kdialog", "--title", title, "--getopenfilename", str(Path.home()), _kdialog_filter(filetypes)]
        return _run(cmd)
    if shutil.which("zenity"):
        cmd = ["zenity", "--file-selection", f"--title={title}", *_zenity_filters(filetypes)]
        return _run(cmd)
    return None


def _linux_save(title, filetypes, initialfile):
    start = str(Path.cwd() / initialfile) if initialfile else str(Path.home())
    if shutil.which("kdialog"):
        cmd = ["kdialog", "--title", title, "--getsavefilename", start, _kdialog_filter(filetypes)]
        return _run(cmd)
    if shutil.which("zenity"):
        cmd = [
            "zenity",
            "--file-selection",
            "--save",
            "--confirm-overwrite",
            f"--title={title}",
            f"--filename={start}",
            *_zenity_filters(filetypes),
        ]
        return _run(cmd)
    return None


def _run(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
    except OSError:
        return None
    if result.returncode != 0:
        return ""  # user cancelled the dialog
    return result.stdout.strip()


def _kdialog_filter(filetypes):
    return "\n".join(f"{_all_files_glob(patterns)}|{label}" for label, patterns in filetypes)


def _zenity_filters(filetypes):
    return [f"--file-filter={label} | {_all_files_glob(patterns)}" for label, patterns in filetypes]


def _all_files_glob(patterns):
    # Tk's "*.*" convention would exclude extensionless files under a real
    # shell glob; kdialog/zenity expect "*" for "match everything".
    return "*" if patterns == "*.*" else patterns
