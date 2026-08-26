# OCT E2E Viewer

A small desktop app for scrolling through the B-scans of a Heidelberg Heyex `.E2E` OCT file, one slice at a time, with the current slice's position marked on the en-face fundus image. It can also open a plain directory of B-scan PNGs when you don't have the original `.E2E` file. Built on [eyepy](https://github.com/MedVisBonn/eyepy) for reading `.E2E` files and Qt (PySide6) for the UI.

![Demo of scrolling through B-scans](assets/demo.webp)

## Install

The easiest way to install is with [pipx](https://pipx.pypa.io/), which puts the app in its own isolated environment and puts the `oct-e2e-viewer` command on your PATH, without you needing to create or activate anything:

```bash
pipx install git+https://github.com/MakrisJr/oct-e2e-viewer.git
```

(Install pipx itself first if you don't have it: `python3 -m pip install --user pipx && python3 -m pipx ensurepath`.)

If you're developing on the code instead, use an editable install in a venv (or conda env) of your own:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Either way, this installs the `oct-e2e-viewer` command and the `oct_e2e_viewer` package, including PySide6, so no system Qt/GUI packages need to be installed separately.

> **Note:** editable installs (`pip install -e .` or `pipx install --editable .`) don't re-resolve dependencies on their own. If you pull changes that add or update a dependency and the app then fails to start with an import error, re-run the install command to pick up the change.

## Run

```bash
oct-e2e-viewer                     # opens with File > Open
oct-e2e-viewer path/to/scan.e2e    # opens a .E2E file directly
oct-e2e-viewer path/to/png_dir     # opens a directory of B-scan PNGs directly
```

You can also drag and drop a `.e2e`/`.E2E` file or a directory of PNGs onto the window, or use **File > Open File...** / **File > Open Directory...** (`Ctrl+O` / `Ctrl+Shift+O`).

## Opening a directory of PNG B-scans

If you have B-scans exported as individual images, point the app at the folder they're in (**File > Open Directory...**, `Ctrl+Shift+O`, drag-and-drop, or `oct-e2e-viewer path/to/dir` on the command line):

- Every `.png` file directly inside that folder is loaded as one B-scan slice (subfolders aren't searched).
- Files are ordered by the numbers in their filename, not alphabetically (so `scan-2.png` sorts before `scan-10.png` regardless of digit padding), and file names don't need to follow any particular convention (`004-0.png`, `bscan_07.png`, `12.png` all work) as long as the slice order is encoded somewhere in the number(s) in the name.
- Each image is converted to 8-bit grayscale on load, whatever its original color mode.

A directory laid out like this works out of the box:

```text
004/
    004-0.png
    004-1.png
    004-2.png
    ...
    004-48.png
```

Because a plain PNG folder carries none of an `.E2E` file's extra data, a few things are unavailable and the UI adapts accordingly:

- No fundus/localizer image — the app shows just the B-scan (no empty "No fundus image" panel).
- No laterality, scan date, quality, averaging, or axial-scale metadata in the status bar.
- No layer segmentations — the "Layer annotations"/"Layer Legend" controls and B-scan alignment (which needs a segmented reference layer) have nothing to draw.

## Controls

**Navigation**
- Left/Right arrow keys, mouse scroll wheel (over the chart), the slider, the index box, or Prev/Next buttons: step through B-scans.
- Page Up/Page Down: jump 10 slices at a time.
- Home/End: jump to the first/last B-scan.
- Type an index in the box and press Enter to jump directly to it.

## Setup double-click to open (Linux)

To make this app the default handler for a `.e2e`/`.E2E` file, run this after the installation:

```bash
oct-e2e-viewer --install-desktop-entry
```

It registers a MIME type for `.e2e`/`.E2E` files, installs a `.desktop` launcher (with icon) under `~/.local/share/applications`, and sets it as the default handler via `xdg-mime`. It's a user-level install (no sudo). 

## Project layout

```text
src/oct_e2e_viewer/
    loader.py                # thin wrapper around eyepy's import_heyex_e2e
    png_loader.py            # loads a directory of B-scan PNGs
    app.py                   # PySide6 (Qt) UI
    alignment.py             # B-scan alignment ("Stabilize B-scan Position")
    recent_files.py          # Open Recent persistence
    desktop_integration.py   # `--install-desktop-entry` (Linux launcher + MIME type)
    resources/               # icon, .desktop template, MIME type definition
```
