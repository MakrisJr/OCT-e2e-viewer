"""
png_loader.py

Loads a directory of standalone B-scan PNGs (no fundus image, metadata, or
layer segmentations available) behind the same read-only interface app.py
uses for E2EVolume, so the viewer can display either.
"""

import re
from pathlib import Path

import numpy as np
from PIL import Image

_DIGITS_RE = re.compile(r"\d+")


def _natural_sort_key(path):
    """Split a filename into text/number chunks so e.g. '004-2.png' sorts
    before '004-10.png' regardless of digit padding.
    """
    parts = _DIGITS_RE.split(path.name)
    numbers = _DIGITS_RE.findall(path.name)
    key = []
    for part, number in zip(parts, numbers + [None]):
        key.append(part)
        if number is not None:
            key.append(int(number))
    return key


class PNGDirectoryVolume:
    """A B-scan stack loaded from a directory of PNG images."""

    # A bare PNG directory never carries a fundus image, unlike .E2E where
    # one is just sometimes missing -- app.py uses this to skip the fundus
    # axes entirely rather than showing an empty "No fundus image" panel.
    supports_fundus = False

    def __init__(self, paths, path):
        self.paths = paths
        self.path = Path(path)
        self._pixel_range = None

    @property
    def n_bscans(self):
        return len(self.paths)

    def bscan(self, index):
        """Return the B-scan image at `index` as a 2D uint8 numpy array."""
        return np.asarray(Image.open(self.paths[index]).convert("L"))

    @property
    def pixel_range(self):
        # Pillow's "L" conversion always yields 8-bit grayscale, so the
        # full range is known without loading every frame up front.
        if self._pixel_range is None:
            self._pixel_range = (0.0, 255.0)
        return self._pixel_range

    @property
    def fundus(self):
        return None

    @property
    def laterality(self):
        return None

    @property
    def axial_scale_um(self):
        return None

    def bscan_quality(self, index):
        return None

    def bscan_num_averages(self, index):
        return None

    @property
    def scan_date(self):
        return None

    @property
    def layer_names(self):
        return []

    def bscan_layers(self, index):
        return {}

    def bscan_line(self, index):
        return None


def load_png_directory(path):
    """Load all PNGs directly inside `path` (non-recursive) as a
    PNGDirectoryVolume, naturally sorted by filename.
    """
    directory = Path(path)
    paths = sorted(
        (p for p in directory.iterdir() if p.is_file() and p.suffix.lower() == ".png"),
        key=_natural_sort_key,
    )
    if not paths:
        raise ValueError(f"No PNG images found in {directory}")
    return PNGDirectoryVolume(paths, directory)
