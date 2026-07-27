#!/usr/bin/env bash
# Registers OCT E2E Viewer as the double-click handler for .e2e/.E2E files
# on this Linux machine (user-level install, no sudo required).
#
# Needs `oct-e2e-viewer` on PATH to find the installed console script,
# which already has its environment's Python baked into its shebang --
# that's what makes the .desktop launcher work without needing to
# re-activate anything when double-clicked.
#
# If you installed with pipx, it's already on PATH, just run this script.
# If you installed with `pip install -e .` in a venv/conda env instead,
# run this from *within* that environment (e.g. `conda activate <env>`
# or `source venv/bin/activate`) first.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

LAUNCHER="$(command -v oct-e2e-viewer || true)"
if [ -z "$LAUNCHER" ]; then
    echo "oct-e2e-viewer not found on PATH." >&2
    echo "Install it first (pipx install ..., or pip install -e . inside an activated venv/conda env) and re-run this script." >&2
    exit 1
fi

mkdir -p "$HOME/.local/share/mime/packages"
cp "$REPO_DIR/resources/x-heyex-e2e.xml" "$HOME/.local/share/mime/packages/"
update-mime-database "$HOME/.local/share/mime"

mkdir -p "$HOME/.local/share/applications"
sed "s#__LAUNCHER__#$LAUNCHER#" "$REPO_DIR/resources/oct-e2e-viewer.desktop.in" \
    > "$HOME/.local/share/applications/oct-e2e-viewer.desktop"
update-desktop-database "$HOME/.local/share/applications"

xdg-mime default oct-e2e-viewer.desktop application/x-heyex-e2e

echo "Registered $LAUNCHER as the default handler for .e2e/.E2E files."
echo "(If your file manager cached the old file type, you may need to log out/in.)"
