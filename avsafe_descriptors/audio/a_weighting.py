"""
A-weighting utilities (IEC 61672) — exact constants, 1 kHz normalization
Valid for f > 0; numerically stable through ~40 kHz.

Provides:
  - a_weight_db(f): A-weighting correction in dB at frequency f (adds to SPL)
  - a_weight_db_many(freqs): convenience vector form
  - a_weight_table(centers): mapping center -> A(dB)
  - overall_level_dba(band_levels_db, band_centers_hz): overall dB(A) from bands

References:
  * IEC 61672-1: Sound level meters — Frequency weighting characteristics
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Dict, List, Sequence

__all__ = [
    "a_weight_db",
    "a_weight_db_many",
    "a_weight_table",
    "overall_level_dba",
]

# ---- Precise IEC 61672 break frequencies (Hz) ----
# (Common rounded forms 20.6, 107.7, 737.9, 12200 are slightly off.)
_F1 = 20.598997
_F2 = 107.65265
_F3 = 737.86223
_F4 = 12194.217

_F1_2 = _F1 * _F1
_F2_2 = _F2 * _F2
_F3_2 = _F3 * _F3
_F4_2 = _F4 * _F4


def _ra_unscaled(f_hz: float) -> float:
    """
    IEC 61672 magnitude response (not in dB, not normalized), R_A(f).

    R_A(f) = ((f^2 + f4^2) * f^4) /
             ((f^2 + f1^2) * sqrt((f^2 + f2^2)(f^2 + f3^2)) * f4^2)
    """
    f2 = f_hz * f_hz
    num = (f2 + _F4_2) * (f2 * f2)
    den = (f2 + _F1_2) * math.sqrt((f2 + _F2_2) * (f2 + _F3_2)) * _F4_2
    return num / den


# Normalize exactly to 0.00 dB at 1 kHz (precompute once)
_RA_1K = _ra_unscaled(1000.0)


@lru_cache(maxsize=4096)
def a_weight_db(f_hz: float) -> float:
    """
    A-weighting correction (dB) at frequency f_hz (Hz), to ADD to an SPL at f.

    Exactly 0.00 dB at 1000 Hz by construction.

    Raises
    ------
    ValueError : if f_hz <= 0 (DC is undefined for A-weighting).
    """
    if f_hz <= 0.0:
        raise ValueError("Frequency must be > 0 Hz (DC is undefined for A-weighting).")
    ra = _ra_unscaled(f_hz) / _RA_1K
    return 20.0 * math.log10(ra)


def a_weight_db_many(freqs_hz: Sequence[float]) -> List[float]:
    """Vector-friendly wrapper around a_weight_db."""
    return [a_weight_db(float(f)) for f in freqs_hz]


def a_weight_table(
    centers_hz: Sequence[float],
    rounding: int | None = 1,
) -> Dict[float, float]:
    """
    Build a mapping: center_frequency -> A-weighting correction (dB).

    Parameters
    ----------
    centers_hz : Sequence[float]
        Frequencies (e.g., 1/3-octave centers) at which to compute A-weighting.
    rounding : int | None
        If not None, round the dB corrections to this many decimals.
    """
    tbl: Dict[float, float] = {}
    for c in centers_hz:
        val = a_weight_db(float(c))
        tbl[float(c)] = round(val, rounding) if rounding is not None else val
    return tbl


def overall_level_dba(
    band_levels_db: Sequence[float],
    band_centers_hz: Sequence[float],
) -> float:
    """
    Compute overall A-weighted level (dB(A)) from band SPLs (dB),
    applying A-weighting to each band and summing energies:

        L_Aeq = 10*log10( sum_i 10^{(L_i + A(f_i))/10} )

    Raises
    ------
    ValueError : if lengths mismatch.
    """
    if len(band_levels_db) != len(band_centers_hz):
        raise ValueError("band_levels_db and band_centers_hz must have same length")

    total_lin = 0.0
    for L, fc in zip(band_levels_db, band_centers_hz):
        La = L + a_weight_db(float(fc))
        total_lin += 10.0 ** (La / 10.0)

    return float("-inf") if total_lin <= 0.0 else 10.0 * math.log10(total_lin)


if __name__ == "__main__":
    # Quick anchors
    for f in (10.0, 20.0, 100.0, 1000.0, 10_000.0, 40_000.0):
        print(f"{f:>7.1f} Hz  ->  {a_weight_db(f):6.2f} dB")
