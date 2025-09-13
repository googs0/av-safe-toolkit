# avsafe_descriptors/rules/evaluator.py
from __future__ import annotations

import json
import math
import statistics
from typing import Dict, Iterable, List, Mapping, Optional, Tuple, Union, Any

from .profile_loader import RulesProfile  # your loader’s return type (dataclass or dict-like)
from .ieee_1789 import allowed_mod_percent


ProfileLike = Union[RulesProfile, Mapping[str, Any]]


def _get_section(profile: ProfileLike, name: str) -> Dict[str, Any]:
    """
    Pull a section from the profile whether it's a dataclass (attrs) or a dict.
    """
    if hasattr(profile, name):
        return getattr(profile, name) or {}
    if isinstance(profile, Mapping):
        return dict(profile.get(name, {}) or {})
    return {}


def _get_meta(profile: ProfileLike, key: str, default: Any = None) -> Any:
    """
    Read a metadata key (e.g., profile_id, schema_version) from either object or dict.
    """
    if hasattr(profile, key):
        return getattr(profile, key, default)
    if isinstance(profile, Mapping):
        return profile.get(key, default)
    return default


def _normalize_locale(raw_locale: Optional[str], profile: ProfileLike) -> Optional[str]:
    """
    Normalize a user-provided locale against profile locales/aliases.
    Returns normalized key if found, else the original lowercased token, else None.
    """
    if not raw_locale:
        return None

    token = str(raw_locale).strip().casefold()
    locales = _get_section(profile, "locales")
    aliases = (locales.get("aliases") or {}) if isinstance(locales, dict) else {}

    # Direct match first
    noise = _get_section(profile, "noise")
    laeq_limits = noise.get("laeq_limits_db", {}) if isinstance(noise, dict) else {}
    if token in laeq_limits:
        return token

    # Alias map (e.g., “köln” → “cologne”)
    mapped = aliases.get(token)
    if mapped:
        mapped_cf = str(mapped).strip().casefold()
        if mapped_cf in laeq_limits:
            return mapped_cf
        return mapped_cf

    return token  # return normalized token; caller can still fall back to default


def _percentile(values: List[float], p: float) -> Optional[float]:
    """
    Compute the p-th percentile (0–100) using linear interpolation (no NumPy dependency).
    Returns None if the list is empty.
    """
    if not values:
        return None
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    xs = sorted(values)
    k = (len(xs) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(xs[int(k)])
    return float(xs[f] + (xs[c] - xs[f]) * (k - f))


def _collect_minutes(minutes_path: str) -> List[dict]:
    """
    Load JSONL minutes file into a list of dicts (ignore blank lines).
    """
    minutes: List[dict] = []
    with open(minutes_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            minutes.append(json.loads(line))
    return minutes


def _clip(value: float, lo: Optional[float], hi: Optional[float]) -> float:
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value


def evaluate(minutes_path: str, profile: ProfileLike, locale: Optional[str] = None) -> Dict[str, Any]:
    """
    Evaluate a stream of AV minute descriptors against a WHO/IEEE-aligned profile.

    Parameters
    ----------
    minutes_path : str
        Path to JSONL file with one minute record per line.
    profile : RulesProfile or dict
        Loaded rules profile (supports both dataclass-like and dict-like objects).
    locale : Optional[str]
        Locale key (e.g., 'munich', 'berlin'). Aliases are resolved if provided in profile.

    Returns
    -------
    dict
        {
          "n_minutes": int,
          "flags": [str, ...],
          "noise": {
             "limit_db": float,
             "pct_over": float,
             "mean_laeq": float | null,
             "percentiles": {"p50": float|None, "p90": float|None}
          },
          "flicker": {
             "evaluated": int, "violations": int, "pct_violations": float,
             "percentiles": {"p50": float|None, "p90": float|None}
          },
          "trace": {...}
        }
    """
    minutes = _collect_minutes(minutes_path)
    n = len(minutes)

    out: Dict[str, Any] = {
        "n_minutes": n,
        "flags": [],
        "noise": {},
        "flicker": {},
        "trace": {
            "profile_id": _get_meta(profile, "profile_id"),
            "schema_version": _get_meta(profile, "schema_version"),
            "locale_requested": locale,
        },
    }

    if n == 0:
        out["flags"].append("no data")
        return out

    # -------------------------
    # Noise (LAeq) evaluation
    # -------------------------
    noise_cfg = _get_section(profile, "noise")
    laeq_limits = noise_cfg.get("laeq_limits_db", {}) if isinstance(noise_cfg, dict) else {}
    loc_norm = _normalize_locale(locale, profile)
    limit_src = "default"
    limit = None

    if isinstance(laeq_limits, dict):
        if loc_norm and loc_norm in laeq_limits:
            limit = laeq_limits[loc_norm]
            limit_src = loc_norm
        else:
            limit = laeq_limits.get("default", 55)

    out["trace"]["locale_resolved"] = loc_norm
    out["trace"]["noise_limit_source"] = limit_src

    laeq_vals: List[float] = []
    for m in minutes:
        a = m.get("audio") or {}
        v = a.get("laeq_db")
        if isinstance(v, (int, float)):
            laeq_vals.append(float(v))

    mean_laeq = statistics.fmean(laeq_vals) if laeq_vals else None
    pct_over = (
        100.0 * sum(1 for x in laeq_vals if x > float(limit)) / max(len(laeq_vals), 1)
        if laeq_vals and limit is not None
        else 0.0
    )

    # Optional percentiles for display
    display_cfg = _get_section(profile, "display")
    pct_list: List[int] = display_cfg.get("percentiles", [50, 90]) if isinstance(display_cfg, dict) else [50, 90]
    noise_percentiles = {f"p{p}": _percentile(laeq_vals, float(p)) for p in pct_list}

    out["noise"] = {
        "limit_db": float(limit) if limit is not None else None,
        "pct_over": float(pct_over),
        "mean_laeq": float(mean_laeq) if mean_laeq is not None else None,
        "percentiles": noise_percentiles,
    }

    noise_flag_threshold = float(noise_cfg.get("flag_threshold_pct", 10.0)) if isinstance(noise_cfg, dict) else 10.0
    if pct_over > noise_flag_threshold and limit is not None:
        out["flags"].append(f"Noise: LAeq > {limit:.0f} dB in {pct_over:.1f}% of minutes")

    # -------------------------
    # Flicker evaluation
    # -------------------------
    flick_cfg = _get_section(profile, "flicker")
    clip_range = flick_cfg.get("clip_percent_mod_range") if isinstance(flick_cfg, dict) else None
    clip_lo = clip_range[0] if isinstance(clip_range, (list, tuple)) and len(clip_range) > 0 else None
    clip_hi = clip_range[1] if isinstance(clip_range, (list, tuple)) and len(clip_range) > 1 else None

    violations = 0
    evaluated = 0
    tlm_mod_values: List[float] = []

    for m in minutes:
        l = m.get("light") or {}
        f = l.get("tlm_freq_hz")
        mod = l.get("tlm_mod_percent")

        if not isinstance(f, (int, float)) or not isinstance(mod, (int, float)):
            continue

        # Clip measured modulation to configured range (avoid silly values from bad devices)
        mod_c = _clip(float(mod), float(clip_lo) if clip_lo is not None else None,
                      float(clip_hi) if clip_hi is not None else None)

        allowed = allowed_mod_percent(float(f), flick_cfg.get("percent_mod_vs_freq", {}))  # type: ignore[arg-type]
        evaluated += 1
        tlm_mod_values.append(mod_c)

        if mod_c > allowed:
            violations += 1

    pct_viol = 100.0 * violations / max(evaluated, 1)
    flick_percentiles = {f"p{p}": _percentile(tlm_mod_values, float(p)) for p in pct_list}

    out["flicker"] = {
        "evaluated": evaluated,
        "violations": violations,
        "pct_violations": float(pct_viol),
        "percentiles": flick_percentiles,
    }

    flick_flag_threshold = float(flick_cfg.get("flag_threshold_pct", 0.0)) if isinstance(flick_cfg, dict) else 0.0
    if pct_viol > flick_flag_threshold:
        out["flags"].append(f"Flicker: {pct_viol:.1f}% minutes exceed IEEE-1789 curve")

    # Deduplicate flags while preserving order
    seen = set()
    uniq_flags = []
    for f in out["flags"]:
        if f not in seen:
            uniq_flags.append(f)
            seen.add(f)
    out["flags"] = uniq_flags

    # Trace what we displayed
    out["trace"]["display_percentiles"] = pct_list

    return out
