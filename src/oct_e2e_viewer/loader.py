"""
loader.py

Thin wrapper around eyepy for loading Heyex .E2E OCT files, giving the
viewer app a small, stable surface instead of talking to eyepy directly.
"""

from datetime import datetime
from pathlib import Path

import numpy as np
import eyepy


class E2EVolume:
    """A loaded .E2E scan: the B-scan stack plus its en-face fundus image."""

    # E2E stores laterality as a raw ASCII code (82/76), which eyepy passes
    # through undecoded rather than resolving to 'R'/'L'.
    _LATERALITY_CODES = {82: "R", 76: "L"}

    def __init__(self, ev, path):
        self.ev = ev
        self.path = Path(path)
        self._pixel_range = None

    @property
    def n_bscans(self):
        return self.ev.shape[0]

    def bscan(self, index):
        """Return the B-scan image at `index` as a 2D numpy array."""
        return np.asarray(self.ev[index].data)

    @property
    def pixel_range(self):
        """Return (min, max) pixel intensity across the whole B-scan stack,
        computed once and cached. Used as the bounds for the contrast/
        brightness sliders, so they cover every slice rather than just the
        one currently on screen.
        """
        if self._pixel_range is None:
            data = np.asarray(self.ev.data)
            self._pixel_range = (float(data.min()), float(data.max()))
        return self._pixel_range

    @property
    def fundus(self):
        """Return the en-face localizer image as a 2D numpy array, or None."""
        if self.ev.localizer is None:
            return None
        return np.asarray(self.ev.localizer.data)

    @property
    def laterality(self):
        raw = self.ev.meta.get("laterality")
        if raw is None:
            return None
        try:
            return self._LATERALITY_CODES.get(int(raw), str(raw))
        except (TypeError, ValueError):
            return str(raw)

    @property
    def axial_scale_um(self):
        """Axial (depth) pixel size in micrometers, from the first B-scan's
        metadata. volume_meta's scale fields are always a 1px placeholder for
        E2E files in eyepy, so this is the only real device calibration
        available.
        """
        try:
            return self.ev[0].meta["scale_y"] * 1000
        except Exception:
            return None

    def bscan_quality(self, index):
        """Return the LibE2E quality score (0-1) for the B-scan at `index`,
        or None if unavailable.
        """
        try:
            return float(self.ev[index].meta["quality"])
        except Exception:
            return None

    def bscan_num_averages(self, index):
        """Return the number of averaged frames (ART) for the B-scan at
        `index`, or None if unavailable.
        """
        try:
            return int(self.ev[index].meta["numAve"])
        except Exception:
            return None

    @property
    def scan_date(self):
        """Return the volume's acquisition date/time (from its first B-scan's
        metadata), or None if it isn't present or can't be parsed.
        """
        try:
            raw = self.ev[0].meta["acquisitionTime"]
            return datetime.fromisoformat(raw)
        except Exception:
            return None

    @property
    def layer_names(self):
        """Names of segmented retinal layers available for this volume, if any."""
        return list(self.ev.layers.keys())

    def bscan_layers(self, index):
        """Return {layer_name: 1D height array} for the B-scan at `index`.

        Each height array holds one y-pixel position per A-scan (column) in
        the B-scan, with NaN where the segmentation is undefined.
        """
        return {
            name: np.asarray(self.ev[index].layers[name].data)
            for name in self.layer_names
        }

    def bscan_line(self, index):
        """Return ((x0, y0), (x1, y1)) for `index`'s scan line in fundus pixel
        coordinates, or None if the position can't be resolved (e.g. no
        localizer, or malformed per-B-scan position metadata).
        """
        if self.ev.localizer is None:
            return None
        try:
            h, w = self.ev.localizer.shape
            # eyepy's _pos_to_localizer_region computes `region_offset` from
            # region[*].start, which becomes NaN if given as None (i.e. from
            # np.s_[:, :]) -- pass explicit bounds instead.
            region = (slice(0, h), slice(0, w))
            meta = self.ev[index].meta
            start = self.ev._pos_to_localizer_region(meta["start_pos"], region)
            end = self.ev._pos_to_localizer_region(meta["end_pos"], region)
            return tuple(start), tuple(end)
        except Exception:
            return None


def load_e2e(path):
    """Load a Heyex .E2E file and return an E2EVolume.

    Multi-series files: eyepy's import_heyex_e2e returns only the first
    series. Use eyepy.io.HeE2eReader directly if you need the others.
    """
    ev = eyepy.import_heyex_e2e(str(path))
    return E2EVolume(ev, path)
