"""
oct_e2e_viewer — a small desktop viewer for Heyex .E2E OCT files.
"""

from .loader import E2EVolume, load_e2e

__all__ = ["E2EVolume", "load_e2e"]
__version__ = "0.1.0"
