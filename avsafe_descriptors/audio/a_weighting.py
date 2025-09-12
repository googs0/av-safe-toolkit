
"""
A-weighting utilities (IEC 61672) + 1/3-octave helpers (IEC 61260-1)

- Accurate A-weighting using precise IEC break frequencies and exact 1 kHz normalization
- Third-octave band center generation (geometric), with nominal rounding
- Overall A-weighted level from band SPLs

References:
  * IEC 61672-1: Sound level meters — A-weighting frequency response
  * IEC 61260-1: Octave-band and fractional-octave-band filters (band definitions)

Author: AV-SAFE Toolkit
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Iterable, Dict, List, Sequence

# ---- Precise IEC 61672 break frequencies (Hz) ----
# Commonly rounded forms (20.6, 107.7, 737.9, 12200) are acceptable but slightly off.
_F1 = 20.598997
_F2 = 107.65265
_F3 = 737.86223
_F4 = 12194.217

_F1_2 = _F1 * _F1
_F2_2 = _F2 * _F2
_F3_2 = _F3 * _F3
_F4_2 = _F4 * _F4


@lru_cache(maxsize=2048)
def a_weight_db(f_hz: float) -> float:
    """
    A-weighting correction (dB) at frequency f_hz.

    Returns the dB value to ADD to a narrowband SPL at frequency f_hz
    (i.e., L_A(f) = L(f) + A(f)). Exactly 0.00 dB at 1000 Hz.

    Parameters
    ----------
    f_hz : float
        Frequency in Hz (> 0).

    Raises
    ------
    ValueError
        If f_hz <= 0.

    Notes
    -----
    IEC 61672 magnitude:
      R_A(f) = ( (f^2 + f4^2) * f^4 ) /
               ( (f^2 + f1^2) * sqrt( (f^2 + f2^2)*(f^2 + f3^2) ) * f4^2 )

    We compute A(f) = 20*log10( R_A(f) / R_A(1000) ) to force 0 dB at 1 kHz exactly.
    """
    if f_hz <= 0.0:
        raise ValueError("Frequency must be > 0 Hz")

    f2 = f_hz * f_hz

    # Numerator and denominator per IEC (arranged to avoid overflow for typical audio freqs)
    num = (f2 + _F4_2) * (f2 * f2)
    den = (f2 + _F1_2) * math.sqrt((f2 + _F2_2) * (f2 + _F3_2)) * _F4_2
    ra = num / den

    # Normalize to 0 dB at 1 kHz
    _f1k2 = 1_000.0 * 1_000.0
    num_1k = (_f1k2 + _F4_2) * (_f1k2 * _f1k2)
    den_1k = (_f1k2 + _F1_2) * math.sqrt((_f1k2 + _F2_2) * (_f1k2 + _F3_2)) * _F4_2
    ra_1k = num_1k / den_1k

    return 20.0 * math.log10(ra / ra_1k)


def a_weight_db_many(freqs_hz: Iterable[float]) -> List[float]:
    """Vector-friendly wrapper around a_weight_db."""
    return [a_weight_db(float(f)) for f in freqs_hz]


# ---- IEC 61260-1: third-octave band centers (exact geometric) ----

def third_octave_centers(
    fmin_hz: float = 20.0,
    fmax_hz: float = 20_000.0,
    fref_hz: float = 1000.0,
) -> List[float]:
    """
    Generate third-octave centers as exact geometric series:
      f_c(k) = f_ref * 2^(k/3), for integer k.

    Centers are returned within [fmin_hz, fmax_hz], inclusive.

    Notes
    -----
    Nominal printed centers (e.g., 31.5 Hz) are rounded forms of the geometric series.
    If you want nominal labels, round to 1 or 2 sig figs for display only.
    """
    # Find k range so that f_c within [fmin, fmax]
    k_min = math.ceil(3.0 * math.log2(fmin_hz / fref_hz))
    k_max = math.floor(3.0 * math.log2(fmax_hz / fref_hz))
    centers = [fref_hz * (2.0 ** (k / 3.0)) for k in range(k_min, k_max + 1)]
    return centers


def third_octave_band_edges(fc_hz: float) -> tuple[float, float]:
    """
    Lower/upper band-edge frequencies for a 1/3-octave band centered at fc_hz:
      f_lo = f_c / 2^(1/6),  f_hi = f_c * 2^(1/6)
    """
    k = 2.0 ** (1.0 / 6.0)
    return (fc_hz / k, fc_hz * k)


# ---- Convenience tables & overall A-weighted level ----

def a_weight_table(
    centers_hz: Sequence[float] | None = None,
    rounding: int | None = 1,
) -> Dict[float, float]:
    """
    Build a mapping: center_frequency -> A-weighting correction (dB).
    If rounding is not None, round the dB values to `rounding` decimals for presentation.
    """
    if centers_hz is None:
        centers_hz = third_octave_centers()

    tbl: Dict[float, float] = {}
    for c in centers_hz:
        val = a_weight_db(float(c))
        if rounding is not None:
            val = round(val, rounding)
        # round center for a nicer nominal label (optional; doesn’t affect math)
        tbl[round(c, 1)] = val
    return tbl


def overall_level_dba(
    band_levels_db: Sequence[float],
    band_centers_hz: Sequence[float],
) -> float:
    """
    Compute overall A-weighted level (dB(A)) from band SPLs (dB),
    applying the A-weighting correction per band and summing energies.

      L_Aeq = 10*log10( sum_i 10^{(L_i + A(f_i))/10} )

    Parameters
    ----------
    band_levels_db : Sequence[float]
        Sound pressure levels per band (e.g., 1/3-octave) in dB.
    band_centers_hz : Sequence[float]
        Matching band center frequencies in Hz.

    Returns
    -------
    float
        Overall A-weighted level in dB(A).

    Raises
    ------
    ValueError
        If lengths mismatch.
    """
    if len(band_levels_db) != len(band_centers_hz):
        raise ValueError("band_levels_db and band_centers_hz must have same length")

    total_lin = 0.0
    for L, fc in zip(band_levels_db, band_centers_hz):
        La = L + a_weight_db(float(fc))
        total_lin += 10.0 ** (La / 10.0)

    if total_lin <= 0.0:
        return float("-inf")
    return 10.0 * math.log10(total_lin)


# ---- Quick self-checks (run if module executed directly) ----
if __name__ == "__main__":
    # Known anchor points (approx):
    # A(1000 Hz) ≈ 0.00 dB by construction
    # A(100 Hz) ≈ -19.1 dB
    # A(20 Hz)  ≈ -50.5 dB
    # A(10 kHz) ≈ -2.6 dB
    for f in (20.0, 100.0, 1000.0, 10_000.0):
        print(f"{f:>7.1f} Hz  ->  {a_weight_db(f):6.2f} dB")

    # Example: table at nominal centers (20 Hz .. 20 kHz)
    centers = third_octave_centers(20.0, 20_000.0)
    tbl = a_weight_table(centers)
    print("\nA-weighting @ 1/3-oct centers (dB):")
    for fc in centers[:6] + centers[-6:]:
        print(f"  {round(fc,1):>7} Hz : {tbl[round(fc,1)]:>6.1f}")
