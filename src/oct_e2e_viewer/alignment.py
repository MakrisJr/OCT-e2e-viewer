"""
alignment.py

Vertical B-scan alignment against a segmented layer (or combination of
layers), so the retina doesn't visibly jump up/down between B-scans due
to eye motion during acquisition.

For each B-scan, a single "reference row" is estimated from the chosen
layer(s)' heights using an edge-weighted median: columns near the center
of the B-scan are down-weighted (weight -> 0), so a lesion that only
disturbs the central layers -- a macular hole punching through the inner
retina, say -- can't bias the estimate towards itself. The untouched
retina at the flanks, where the true axial position of the volume
actually lives, dominates instead.

Given reference rows for a window of B-scans (e.g. a whole volume, or
whatever subset a renderer is displaying together), each B-scan is
shifted vertically to align its reference row with the window's median
reference row.
"""

import numpy as np

DEFAULT_EDGE_POWER = 2.0


def weighted_median(values, weights):
    """Return the weighted median of `values`, using `weights`.

    Entries with a non-finite value or non-positive weight are ignored.
    Returns None if nothing remains.
    """
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    mask = np.isfinite(values) & (weights > 0)
    if not np.any(mask):
        return None

    values = values[mask]
    weights = weights[mask]
    order = np.argsort(values)
    values = values[order]
    weights = weights[order]

    cumulative = np.cumsum(weights)
    cutoff = cumulative[-1] / 2
    index = min(int(np.searchsorted(cumulative, cutoff)), len(values) - 1)
    return float(values[index])


def reference_row(layers, layer_names, edge_power=DEFAULT_EDGE_POWER):
    """Compute the edge-weighted reference row for one B-scan.

    `layers` is a {layer_name: 1D height array} mapping, as returned by
    E2EVolume.bscan_layers. `layer_names` selects which of those layers
    to use; when more than one is given, they're averaged per column
    (ignoring NaNs) into a single combined curve before the weighted
    median is taken, so e.g. a column where only one of two selected
    layers segmented successfully still contributes.

    Returns None if none of the requested layers are present, or every
    column is NaN (e.g. total segmentation failure).
    """
    curves = [np.asarray(layers[name], dtype=float) for name in layer_names if name in layers]
    if not curves:
        return None

    stacked = np.vstack(curves)
    counts = np.count_nonzero(~np.isnan(stacked), axis=0)
    sums = np.nansum(stacked, axis=0)
    combined = np.divide(sums, counts, out=np.full(stacked.shape[1], np.nan), where=counts > 0)

    width = combined.shape[0]
    x = np.linspace(-1, 1, width)
    weights = np.abs(x) ** edge_power
    return weighted_median(combined, weights)


def compute_shifts(layers_by_index, layer_names, edge_power=DEFAULT_EDGE_POWER):
    """Compute a vertical pixel shift for each B-scan in `layers_by_index`
    (a {index: {layer_name: heights}} mapping) that aligns it against the
    window's shared target row (the median reference row across the
    window).

    B-scans whose reference row can't be resolved are left unshifted
    (shift 0) rather than guessed.
    """
    ref_rows = {
        index: reference_row(layers, layer_names, edge_power)
        for index, layers in layers_by_index.items()
    }
    resolved = [row for row in ref_rows.values() if row is not None]
    if not resolved:
        return {index: 0 for index in ref_rows}

    target_row = float(np.median(resolved))
    return {
        index: 0 if row is None else int(round(target_row - row))
        for index, row in ref_rows.items()
    }


def compute_volume_shifts(volume, indices, layer_names, edge_power=DEFAULT_EDGE_POWER):
    """Convenience wrapper around `compute_shifts` that pulls layer heights
    for `indices` from `volume` (anything exposing `.bscan_layers(index)`,
    e.g. E2EVolume). This is the shared entry point any renderer should
    call, right after fetching B-scans/layers and before plotting.
    """
    layers_by_index = {index: volume.bscan_layers(index) for index in indices}
    return compute_shifts(layers_by_index, layer_names, edge_power)


def shift_image(image, shift, fill_value=0):
    """Return `image` translated vertically by `shift` pixels (positive
    moves content down), padding exposed rows with `fill_value` instead
    of wrapping around.
    """
    if not shift:
        return image
    shifted = np.full_like(image, fill_value)
    if shift > 0:
        shifted[shift:] = image[:-shift]
    else:
        shifted[:shift] = image[-shift:]
    return shifted


def shift_curve(heights, shift):
    """Return a layer height curve translated by `shift` pixels, matching
    `shift_image`, so overlay lines stay aligned with a shifted B-scan.
    """
    if not shift:
        return heights
    return np.asarray(heights, dtype=float) + shift
