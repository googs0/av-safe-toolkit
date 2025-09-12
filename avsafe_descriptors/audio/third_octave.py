"""
Third-octave band utilities (IEC 61260-1) — extended range (≈10 Hz … 40 kHz)

Provides:
  - third_octave_centers(fmin, fmax): exact geometric centers
  - third_octave_centers_extended(): convenience for 10 Hz … 40 kHz
  - third_octave_band_edges(fc): (flo, fhi) using ±1/6 octave ratio
  - nominal_center_label(fc): canonical labels (10, 12.5, 16, …, 31.5k, 40k)
  - nominal_centers(...), nominal_centers_extended(): labeled sequences
  - find_band_for_frequency(f): locate containing 1/3-oct band
  - bin_narrowband_levels_to_third_octave(freqs, levels): energy-sum binner

No external dependencies (NumPy optional elsewhere).
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Dict, List, Sequence, Tuple

__all__ = [
    "third_octave_centers",
    "third_octave_centers_extended",
    "third_octave_band_edges",
    "nominal_center_label",
    "nominal_centers",
    "nominal_centers_extended",
    "find_band_for_frequency",
    "bin_narrowband_levels_to_third_octave",
]

# Ratios for third-octave math
_OCT_THIRD = 2.0 ** (1.0 / 3.0)   # center-to-center ratio
_HALF_THIRD = 2.0 ** (1.0 / 6.0)  # edge factor around the center (±1/6 octave)

_DEFAULT_FREF = 1000.0

# Preferred nominal multipliers within a decade (IEC-friendly labeling)
_NOMINAL_DECADE = [1.00, 1.25, 1.60, 2.00, 2.50, 3.15, 4.00, 5.00, 6.30, 8.00]


# -------- Core IEC math --------

def index_range_for_limits(
    fmin_hz: float,
    fmax_hz: float,
    fref_hz: float = _DEFAULT_FREF,
) -> Tuple[int, int]:
    """Return integer (k_min, k_max) so centers f_ref*2^(k/3) lie within [fmin, fmax]."""
    if fmin_hz <= 0 or fmax_hz <= 0 or fmax_hz <= fmin_hz:
        raise ValueError("fmin_hz and fmax_hz must be > 0 and fmax_hz > fmin_hz")
    k_min = math.ceil(3.0 * math.log2(fmin_hz / fref_hz))
    k_max = math.floor(3.0 * math.log2(fmax_hz / fref_hz))
    return k_min, k_max


def center_from_index(k: int, fref_hz: float = _DEFAULT_FREF) -> float:
    """Third-octave center f_c(k) = f_ref * 2^(k/3)."""
    return fref_hz * (2.0 ** (k / 3.0))


def third_octave_centers(
    fmin_hz: float = 20.0,
    fmax_hz: float = 20_000.0,
    fref_hz: float = _DEFAULT_FREF,
) -> List[float]:
    """Exact geometric third-octave centers within [fmin_hz, fmax_hz]."""
    k_min, k_max = index_range_for_limits(fmin_hz, fmax_hz, fref_hz)
    return [center_from_index(k, fref_hz) for k in range(k_min, k_max + 1)]


def third_octave_centers_extended(
    fmin_hz: float = 10.0,
    fmax_hz: float = 40_000.0,
    fref_hz: float = _DEFAULT_FREF,
) -> List[float]:
    """Convenience: extended-range centers (≈10 Hz … 40 kHz)."""
    return third_octave_centers(fmin_hz=fmin_hz, fmax_hz=fmax_hz, fref_hz=fref_hz)


def third_octave_band_edges(fc_hz: float) -> Tuple[float, float]:
    """Lower/upper edges: f_lo = f_c / 2^(1/6),  f_hi = f_c * 2^(1/6)."""
    return (fc_hz / _HALF_THIRD, fc_hz * _HALF_THIRD)


# -------- Nominal labeling (IEC-style display) --------

@lru_cache(maxsize=4096)
def nominal_center_label(fc_hz: float) -> float:
    """
    Map an exact geometric center to the canonical nominal label used in plots & tables.

    Algorithm:
      1) Write fc = m * 10^p with 1 <= m < 10.
      2) Snap m to nearest value in _NOMINAL_DECADE.
      3) Return snapped * 10^p, keeping one decimal *only if* needed (e.g., 12.5, 31.5).

    Examples:
      31.622... -> 31.5
      99.999... -> 100
      629.96... -> 630
    """
    if fc_hz <= 0:
        raise ValueError("fc_hz must be > 0")

    p = math.floor(math.log10(fc_hz))
    m = fc_hz / (10.0 ** p)

    best = min(_NOMINAL_DECADE, key=lambda x: abs(x - m))
    val = best * (10.0 ** p)

    # Keep a single decimal only when it matters (e.g., 12.5, 31.5)
    val_1 = round(val, 1)
    return val_1 if abs(val_1 - round(val_1)) > 1e-9 else round(val_1)


def nominal_centers(
    fmin_hz: float = 20.0,
    fmax_hz: float = 20_000.0,
    fref_hz: float = _DEFAULT_FREF,
) -> List[float]:
    """Canonical nominal labels for centers within the limits."""
    return [nominal_center_label(fc) for fc in third_octave_centers(fmin_hz, fmax_hz, fref_hz)]


def nominal_centers_extended(
    fmin_hz: float = 10.0,
    fmax_hz: float = 40_000.0,
    fref_hz: float = _DEFAULT_FREF,
) -> List[float]:
    """Nominal labels across the extended range (10, 12.5, 16, …, 31.5k, 40k)."""
    return [nominal_center_label(fc) for fc in third_octave_centers_extended(fmin_hz, fmax_hz, fref_hz)]


# -------- Find / bin helpers --------

def find_band_for_frequency(
    f_hz: float,
    fref_hz: float = _DEFAULT_FREF,
) -> Tuple[int, float, Tuple[float, float]]:
    """
    Given frequency f_hz, return (k, fc, (flo, fhi)) for the containing 1/3-oct band.
    If exactly on an upper edge, assign to the higher band by convention.
    """
    if f_hz <= 0:
        raise ValueError("f_hz must be > 0")

    k = int(round(3.0 * math.log2(f_hz / fref_hz)))
    fc = center_from_index(k, fref_hz)
    flo, fhi = third_octave_band_edges(fc)

    if f_hz <= flo:
        k -= 1
        fc = center_from_index(k, fref_hz)
        flo, fhi = third_octave_band_edges(fc)
    elif f_hz > fhi:
        k += 1
        fc = center_from_index(k, fref_hz)
        flo, fhi = third_octave_band_edges(fc)

    return k, fc, (flo, fhi)


def bin_narrowband_levels_to_third_octave(
    freqs_hz: Sequence[float],
    levels_db: Sequence[float],
    fmin_hz: float = 10.0,
    fmax_hz: float = 40_000.0,
    fref_hz: float = _DEFAULT_FREF,
) -> Dict[float, float]:
    """
    Aggregate narrowband SPLs (dB) into 1/3-octave band SPLs (dB), summing energies.

    Notes
    -----
    - Treats each narrowband as an impulse at its center frequency.
      For high-resolution FFTs this is accurate. If you have PSDs with bin widths,
      integrate power before converting to dB.
    """
    if len(freqs_hz) != len(levels_db):
        raise ValueError("freqs_hz and levels_db must have the same length")

    centers = third_octave_centers(fmin_hz, fmax_hz, fref_hz)
    edges = [third_octave_band_edges(fc) for fc in centers]
    labels = [nominal_center_label(fc) for fc in centers]

    sums_lin: Dict[float, float] = {label: 0.0 for label in labels}

    for f, L in zip(freqs_hz, levels_db):
        if f <= 0:
            continue
        if f < edges[0][0] or f > edges[-1][1]:
            continue

        # Estimate an index near the correct band
        k_est = int(round(3.0 * math.log2(f / fref_hz) - 3.0 * math.log2(centers[0] / fref_hz)))
        k = min(max(k_est, 0), len(centers) - 1)

        # Walk to the containing band if the estimate is off
        while k > 0 and f < edges[k][0]:
            k -= 1
        while k < len(centers) - 1 and f > edges[k][1]:
            k += 1

        if edges[k][0] < f <= edges[k][1]:
            sums_lin[labels[k]] += 10.0 ** (L / 10.0)

    # Convert back to dB
    out: Dict[float, float] = {}
    for lbl, s in sums_lin.items():
        out[lbl] = float("-inf") if s <= 0.0 else 10.0 * math.log10(s)
    return out


if __name__ == "__main__":
    # Show a taste of the extended label sequence
    labs = nominal_centers_extended()
    print("First 8:", labs[:8], " ...  Last 8:", labs[-8:])

    # Band edges around 1 kHz (sanity)
    flo, fhi = third_octave_band_edges(1000.0)
    print(f"1 kHz band edges: {flo:.1f} – {fhi:.1f} Hz")
