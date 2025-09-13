# avsafe_descriptors/rules/ieee_1789.py
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple


__all__ = [
    "allowed_mod_percent",
    "classify_modulation",
    "normalize_curve_config",
]


def normalize_curve_config(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a percent-modulation vs. frequency config.

    Expected shape (illustrative; align your values externally to IEEE-1789 practice):
    {
      "default": 1.0,                     # fallback allowed % if no segment matches
      "segments": [
        { "f_min": 80,  "f_max": 120,  "a": 0.10, "b": 600 },    # allowed = a + b/f
        { "f_min": 120, "f_max": 200,  "a": 0.30, "b": 480 },
        { "f_min": 200, "f_max": 1000, "a": 0.50, "b": 400 },
        { "f_min": 1000,"f_max": 10000,"a": 1.00, "b": 300 }
      ],
      # Optional global clamp of *allowed* percent to avoid unrealistic values:
      "clip_allowed_range": [0.0, 100.0]  # [min%, max%]
    }

    Returns a shallow-copied dict with:
    - segments sorted by f_min (ascending)
    - coercion of numeric fields to float
    - a safe "default" if missing (1.0)
    """
    out = dict(cfg or {})
    out.setdefault("default", 1.0)

    segs: List[Dict[str, float]] = []
    for s in (out.get("segments") or []):
        try:
            f_min = float(s["f_min"])
            f_max = float(s["f_max"])
            # Two supported segment forms:
            #   (1) "a"+"b" → allowed = a + b/f
            #   (2) "max_percent" → allowed = constant cap in the band
            seg: Dict[str, float] = {"f_min": f_min, "f_max": f_max}
            if "a" in s and "b" in s:
                seg["a"] = float(s["a"])
                seg["b"] = float(s["b"])
            if "max_percent" in s:
                seg["max_percent"] = float(s["max_percent"])
            segs.append(seg)
        except Exception:
            # Skip malformed segments silently (defensive)
            continue

    segs.sort(key=lambda x: x["f_min"])
    out["segments"] = segs

    clip = out.get("clip_allowed_range")
    if isinstance(clip, (list, tuple)) and len(clip) == 2:
        try:
            out["clip_allowed_range"] = [float(clip[0]), float(clip[1])]
        except Exception:
            out["clip_allowed_range"] = None
    else:
        out["clip_allowed_range"] = None

    return out


def _clip(value: float, lo: Optional[float], hi: Optional[float]) -> float:
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def allowed_mod_percent(f_hz: float, cfg: Dict[str, Any]) -> float:
    """
    Compute the **allowed percent modulation** at frequency `f_hz` given a
    piecewise configuration. This function provides an *illustrative*
    “a + b/f” style curve that you parameterize in your YAML profile. It is
    **not** a verbatim reproduction of IEEE-1789 text; tune the parameters
    externally to align with your chosen “low-risk” envelope.

    - If a segment has "a" and "b", allowed = a + b / f_hz
    - If a segment has "max_percent", allowed = that constant
    - If no segment matches, return cfg["default"] (or 1.0 if absent)
    - Finally, clamp using cfg["clip_allowed_range"] if provided

    Parameters
    ----------
    f_hz : float
        Temporal light modulation (TLM) frequency in Hz. Non-positive values
        return the default.
    cfg : dict
        Percent-modulation vs. frequency configuration (see above).

    Returns
    -------
    float : allowed percent modulation (>= 0)
    """
    if not isinstance(f_hz, (int, float)) or f_hz <= 0.0:
        return float(cfg.get("default", 1.0))

    ncfg = normalize_curve_config(cfg)
    default_val = float(ncfg.get("default", 1.0))
    segs: List[Dict[str, float]] = ncfg.get("segments", [])

    allowed = default_val
    for s in segs:
        if s["f_min"] <= f_hz <= s["f_max"]:
            if "a" in s and "b" in s:
                # Protect against division by zero with a tiny epsilon
                allowed = float(s["a"]) + float(s["b"]) / max(f_hz, 1e-6)
            elif "max_percent" in s:
                allowed = float(s["max_percent"])
            break

    # Global clamp to avoid unrealistic allowed values
    clip = ncfg.get("clip_allowed_range")
    if isinstance(clip, (list, tuple)) and len(clip) == 2:
        allowed = _clip(allowed, float(clip[0]), float(clip[1]))

    # Ensure non-negative
    return max(0.0, float(allowed))


def classify_modulation(
    f_hz: float,
    measured_mod_percent: float,
    cfg: Dict[str, Any],
) -> Dict[str, float | str]:
    """
    Convenience helper: classify a measured modulation depth at `f_hz`
    relative to the configured allowed curve.

    Returns
    -------
    dict with:
      - "allowed": float
      - "measured": float
      - "status": "within" | "exceeds"
      - "margin": measured - allowed  (positive if exceeding)
    """
    allowed = allowed_mod_percent(f_hz, cfg)
    measured = float(measured_mod_percent)
    status = "exceeds" if measured > allowed else "within"
    margin = measured - allowed
    return {
        "allowed": allowed,
        "measured": measured,
        "status": status,
        "margin": margin,
    }
