# avsafe_descriptors/rules/profile_loader.py
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from .ieee_1789 import normalize_curve_config

log = logging.getLogger(__name__)


class ProfileError(Exception):
    """Raised when a rules profile cannot be parsed or is invalid."""


@dataclass(frozen=True)
class RulesProfile:
    """
    Parsed rules profile with normalized structures and convenient accessors.

    Attributes
    ----------
    name : str
        Human-friendly profile name.
    noise : Dict[str, Any]
        Noise section. Expected keys:
          - 'laeq_limits_db': { 'default': float, '<locale>': float, ...}
          - 'flag_threshold_pct': float
    flicker : Dict[str, Any]
        Flicker section. Expected keys:
          - 'percent_mod_vs_freq': normalized curve config (see ieee_1789.py)
          - 'flag_threshold_pct': float
    """
    name: str = "profile"
    noise: Dict[str, Any] = field(default_factory=dict)
    flicker: Dict[str, Any] = field(default_factory=dict)

    # -------- Convenience helpers --------
    def noise_limit_for(self, locale: Optional[str]) -> float:
        limits = self.noise.get("laeq_limits_db", {})
        if locale and locale in limits:
            return float(limits[locale])
        return float(limits.get("default", 55.0))

    @property
    def noise_flag_threshold_pct(self) -> float:
        return float(self.noise.get("flag_threshold_pct", 10.0))

    @property
    def flicker_flag_threshold_pct(self) -> float:
        return float(self.flicker.get("flag_threshold_pct", 0.0))

    @property
    def flicker_curve(self) -> Dict[str, Any]:
        # Normalized curve config (safe to pass to allowed_mod_percent / classify_modulation)
        return self.flicker.get("percent_mod_vs_freq", {})


def _coerce_float_map(d: Dict[str, Any]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for k, v in d.items():
        try:
            out[str(k)] = float(v)
        except Exception as e:
            raise ProfileError(f"Expected numeric value for '{k}' in laeq_limits_db, got {v!r}") from e
    return out


def _normalize_noise(cfg: Dict[str, Any]) -> Dict[str, Any]:
    noise = dict(cfg or {})
    limits = _coerce_float_map(noise.get("laeq_limits_db", {}))
    if "default" not in limits:
        # Provide a conservative default if none given
        limits["default"] = 55.0
        log.info("No 'default' noise limit found; using 55 dB(A).")
    noise["laeq_limits_db"] = limits

    # Threshold for flagging % of minutes over limit
    try:
        noise["flag_threshold_pct"] = float(noise.get("flag_threshold_pct", 10.0))
    except Exception as e:
        raise ProfileError("noise.flag_threshold_pct must be numeric") from e
    return noise


def _normalize_flicker(cfg: Dict[str, Any]) -> Dict[str, Any]:
    flicker = dict(cfg or {})
    curve = flicker.get("percent_mod_vs_freq", {})
    flicker["percent_mod_vs_freq"] = normalize_curve_config(curve)

    try:
        flicker["flag_threshold_pct"] = float(flicker.get("flag_threshold_pct", 0.0))
    except Exception as e:
        raise ProfileError("flicker.flag_threshold_pct must be numeric") from e
    return flicker


def _load_text(path_or_text: str) -> str:
    p = Path(path_or_text)
    if p.exists():
        return p.read_text(encoding="utf-8")
    # Allow passing raw YAML (e.g., API uploads) as a convenience
    return path_or_text


def load_profile(path_or_text: str) -> RulesProfile:
    """
    Load a rules profile from a YAML/JSON file path or raw YAML string.

    Parameters
    ----------
    path_or_text : str
        File path to YAML/JSON, or the YAML content itself.

    Returns
    -------
    RulesProfile

    Raises
    ------
    ProfileError
        If parsing or validation fails.
    """
    raw = _load_text(path_or_text)

    try:
        # Accept YAML superset (JSON is valid YAML)
        cfg = yaml.safe_load(raw)
        if not isinstance(cfg, dict):
            raise ProfileError("Profile document must be a mapping/dictionary at the top level.")
    except Exception as e:
        # Fall back to JSON parse to give a clearer error if user passed JSON with YAML disabled
        try:
            cfg = json.loads(raw)
        except Exception:
            raise ProfileError(f"Could not parse profile as YAML/JSON: {e}") from e

    name = cfg.get("name", "profile")

    noise = _normalize_noise(cfg.get("noise"))
    flicker = _normalize_flicker(cfg.get("flicker"))

    return RulesProfile(name=name, noise=noise, flicker=flicker)
