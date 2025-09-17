# avsafe_descriptors/light/tlm.py
# SPDX-License-Identifier: MIT

from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, Generator, Optional, Tuple
import math
import numpy as np

# ---------------------------
# Core per-window computation
# ---------------------------

def _percent_modulation(x: np.ndarray) -> float:
    """
    Percent Modulation (IEEE parlance: Modulation Depth in %)
    PM = (max - min) / (max + min) * 100
    x is assumed to be non-negative illuminance (lux or relative).
    """
    if x.size == 0:
        return float("nan")
    x_min = float(np.min(x))
    x_max = float(np.max(x))
    denom = x_max + x_min
    if denom <= 0:
        return 0.0
    return (x_max - x_min) / denom * 100.0


def _flicker_index(x: np.ndarray, fs: float, f_hint: Optional[float]) -> float:
    """
    Flicker Index (dimensionless). Approximated per one dominant-cycle segment:
      FI = (Area above mean over one period) / (Total area under curve over one period)
    If we can't robustly segment by cycle, fall back to whole-window approximation.
    """
    # Ensure strictly positive (illum) for area computation
    x = np.asarray(x, dtype=float)
    x = np.maximum(x, 0.0)

    # Try to infer a fundamental frequency for a single-cycle slice
    f_dom = _dominant_frequency(x, fs, mains_hint=f_hint)
    if not math.isfinite(f_dom) or f_dom <= 0.0:
        # Whole-window approximation
        mean = float(np.mean(x)) if x.size else 0.0
        if mean <= 0:
            return 0.0
        area_above = float(np.sum(np.clip(x - mean, 0.0, None)))
        area_total = float(np.sum(x))
        return (area_above / area_total) if area_total > 0 else 0.0

    # Number of samples in one period
    n_period = max(8, int(round(fs / f_dom)))  # at least 8 samples for stability
    if x.size < n_period:
        # Not enough samples for a cycle; fall back
        mean = float(np.mean(x)) if x.size else 0.0
        if mean <= 0:
            return 0.0
        area_above = float(np.sum(np.clip(x - mean, 0.0, None)))
        area_total = float(np.sum(x))
        return (area_above / area_total) if area_total > 0 else 0.0

    # Take a centered slice of ~1 period to minimize boundary effects
    start = (x.size - n_period) // 2
    x1 = x[start:start + n_period]
    mean = float(np.mean(x1))
    if mean <= 0:
        return 0.0

    # Discrete-time area ~ sum over samples
    area_above = float(np.sum(np.clip(x1 - mean, 0.0, None)))
    area_total = float(np.sum(x1))
    return (area_above / area_total) if area_total > 0 else 0.0


def _dominant_frequency(x: np.ndarray, fs: float, mains_hint: Optional[float]) -> float:
    """
    Estimate dominant flicker frequency via FFT peak (excluding DC).
    If mains_hint (50 or 60) is given, prefer peaks near its first few harmonics (2*mains ~ 100/120 Hz etc.).
    Returns frequency in Hz.
    """
    x = np.asarray(x, dtype=float)
    if x.size < 8 or fs <= 0:
        return float("nan")

    # Remove DC and slow trend
    x = x - np.mean(x)
    # Zero-pad for resolution
    n = int(1 << (int(np.ceil(np.log2(x.size))) + 1))
    spec = np.fft.rfft(x, n=n)
    freqs = np.fft.rfftfreq(n, d=1.0 / fs)
    mags = np.abs(spec)

    # Ignore DC and very low bins (< 2 Hz)
    lo = np.searchsorted(freqs, 2.0, side="left")
    if lo >= mags.size:
        return float("nan")

    if mains_hint in (50.0, 60.0):
        # Candidate bands near 100/120 Hz and a few harmonics
        cands: Dict[float, Tuple[int, int]] = {}
        for k in (2, 3, 4, 5):  # multiples of mains (e.g., 2*50=100 Hz)
            f0 = mains_hint * k
            bw = max(2.0, f0 * 0.05)  # ±5% or 2 Hz min
            i0 = max(lo, np.searchsorted(freqs, f0 - bw))
            i1 = min(mags.size - 1, np.searchsorted(freqs, f0 + bw))
            cands[f0] = (i0, i1)

        # Pick the band with max magnitude
        best_f = float("nan")
        best_mag = -1.0
        for f0, (i0, i1) in cands.items():
            if i1 <= i0:
                continue
            j = i0 + int(np.argmax(mags[i0:i1]))
            if mags[j] > best_mag:
                best_mag = float(mags[j])
                best_f = float(freqs[j])
        if math.isfinite(best_f):
            return best_f

    # Generic peak search
    j = lo + int(np.argmax(mags[lo:]))
    return float(freqs[j])


def tlm_metrics(
    x: np.ndarray,
    fs: float,
    mains_hint: Optional[float] = None
) -> Dict[str, float]:
    """
    Compute TLM metrics for a single window of light samples.

    Args:
        x: 1D array of illuminance (lux or relative) samples (non-negative recommended).
        fs: sample rate in Hz.
        mains_hint: 50.0 or 60.0 if known; helps bias frequency selection.

    Returns:
        {
          "f_flicker_Hz": float,
          "pct_mod": float,            # Percent Modulation (%)
          "flicker_index": float       # Flicker Index (0..1 typical)
        }
    """
    x = np.asarray(x, dtype=float)
    if x.size == 0 or fs <= 0:
        return {"f_flicker_Hz": float("nan"), "pct_mod": float("nan"), "flicker_index": float("nan")}

    # Robustness: clip negatives (sensor noise), guard NaNs
    x = np.nan_to_num(x, nan=0.0, neginf=0.0, posinf=0.0)
    x = np.maximum(x, 0.0)

    f_dom = _dominant_frequency(x, fs, mains_hint)
    pm = _percent_modulation(x)
    fi = _flicker_index(x, fs, mains_hint)

    # Boundaries
    if not math.isfinite(pm) or pm < 0:
        pm = 0.0
    if not math.isfinite(fi) or fi < 0:
        fi = 0.0

    return {"f_flicker_Hz": float(f_dom), "pct_mod": float(pm), "flicker_index": float(fi)}

# ---------------------------------
# Sliding window + minute aggregator
# ---------------------------------

def window_metrics(
    x: np.ndarray,
    fs: float,
    window_s: float = 1.0,
    step_s: float = 1.0,
    mains_hint: Optional[float] = None
) -> Generator[Dict[str, float], None, None]:
    """
    Yield per-window TLM metrics over a time series.
    """
    x = np.asarray(x, dtype=float)
    n_win = max(1, int(round(window_s * fs)))
    n_step = max(1, int(round(step_s * fs)))
    if x.size < n_win:
        yield tlm_metrics(x, fs, mains_hint)
        return
    for start in range(0, x.size - n_win + 1, n_step):
        seg = x[start:start + n_win]
        yield tlm_metrics(seg, fs, mains_hint)


@dataclass
class MinuteAggregator:
    """
    Collect per-window TLM metrics and emit minute-level summaries
    consistent with AV-SAFE minute JSONL fields.
    """
    # internal storage
    _f: list = None
    _pm: list = None
    _fi: list = None

    def __post_init__(self):
        self._f, self._pm, self._fi = [], [], []

    def add(self, metrics: Dict[str, float]) -> None:
        f = metrics.get("f_flicker_Hz", float("nan"))
        pm = metrics.get("pct_mod", float("nan"))
        fi = metrics.get("flicker_index", float("nan"))
        if math.isfinite(f): self._f.append(float(f))
        if math.isfinite(pm): self._pm.append(float(pm))
        if math.isfinite(fi): self._fi.append(float(fi))

    def summary(self) -> Dict[str, float]:
        """
        Returns:
            {
              "f_flicker_Hz": <dominant freq median>,
              "pct_mod_p95": <95th percentile PM>,
              "flicker_index_p95": <95th percentile FI>
            }
        """
        def _p(arr: list, q: float, default: float = float("nan")) -> float:
            return float(np.percentile(arr, q)) if arr else default

        f_med = _p(self._f, 50.0)
        pm_p95 = _p(self._pm, 95.0, 0.0)
        fi_p95 = _p(self._fi, 95.0, 0.0)
        # Guard bounds
        pm_p95 = max(0.0, pm_p95)
        fi_p95 = max(0.0, fi_p95)
        return {
            "f_flicker_Hz": f_med,
            "pct_mod_p95": pm_p95,
            "flicker_index_p95": fi_p95
        }
