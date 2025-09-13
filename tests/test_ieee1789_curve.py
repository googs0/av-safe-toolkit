# tests/test_ieee1789_curve.py
import math
import pytest

from avsafe_descriptors.rules.ieee_1789 import (
    allowed_mod_percent,
    classify_modulation,
    normalize_curve_config,
)


def _baseline_cfg():
    # Mirrors your profile structure (illustrative params).
    return {
        "default": 1.0,
        "segments": [
            # allowed = a + b/f (so allowed decreases as f increases)
            {"f_min": 80, "f_max": 120, "a": 0.10, "b": 600.0},
            {"f_min": 120, "f_max": 200, "a": 0.30, "b": 480.0},
            {"f_min": 200, "f_max": 1000, "a": 0.50, "b": 400.0},
            # constant cap example band
            {"f_min": 1000, "f_max": 2000, "max_percent": 8.0},
        ],
        "clip_allowed_range": [0.0, 100.0],
    }


def test_normalize_sorts_and_coerces():
    cfg = {
        "segments": [
            {"f_min": 200, "f_max": 1000, "a": "0.5", "b": "400"},
            {"f_min": 80, "f_max": 120, "a": 0.1, "b": 600},
        ]
    }
    ncfg = normalize_curve_config(cfg)
    segs = ncfg["segments"]
    assert segs[0]["f_min"] == 80.0
    assert isinstance(segs[0]["a"], float)
    assert isinstance(segs[0]["b"], float)
    assert ncfg.get("default", None) == 1.0  # filled in if missing


def test_default_used_for_nonpositive_frequency():
    cfg = _baseline_cfg()
    assert allowed_mod_percent(0.0, cfg) == pytest.approx(cfg["default"])
    assert allowed_mod_percent(-50.0, cfg) == pytest.approx(cfg["default"])


def test_piecewise_decreases_with_frequency_in_a_plus_b_over_f_segment():
    cfg = _baseline_cfg()
    # In the 80–120 Hz band with a=0.1, b=600, the curve should decrease as f increases.
    a, b = 0.1, 600.0
    f1, f2, f3 = 90.0, 100.0, 110.0
    y1 = allowed_mod_percent(f1, cfg)
    y2 = allowed_mod_percent(f2, cfg)
    y3 = allowed_mod_percent(f3, cfg)
    assert y1 == pytest.approx(a + b / f1, rel=1e-6)
    assert y2 == pytest.approx(a + b / f2, rel=1e-6)
    assert y3 == pytest.approx(a + b / f3, rel=1e-6)
    assert y1 > y2 > y3  # monotonic within this segment


def test_constant_cap_segment_respected():
    cfg = _baseline_cfg()
    # 1500 Hz falls in the constant-cap band (1000–2000 Hz, max_percent=8)
    y = allowed_mod_percent(1500.0, cfg)
    assert y == pytest.approx(8.0)


def test_outside_segments_uses_default():
    cfg = _baseline_cfg()
    # 50 Hz is below first segment (80–120) → default applies
    y = allowed_mod_percent(50.0, cfg)
    assert y == pytest.approx(cfg["default"])


def test_clip_allowed_range_applied():
    # Make a band that would give a large allowed % at very low f, but clip to <= 10%
    cfg = {
        "default": 1.0,
        "segments": [{"f_min": 1, "f_max": 100, "a": 0.0, "b": 1000.0}],
        "clip_allowed_range": [0.0, 10.0],
    }
    y = allowed_mod_percent(5.0, cfg)  # raw would be 0 + 1000/5 = 200%
    assert y == pytest.approx(10.0)    # clipped


def test_classify_modulation_within_and_exceeds():
    cfg = _baseline_cfg()
    f = 100.0  # a=0.1, b=600 → allowed = 6.1%
    res_within = classify_modulation(f, 5.0, cfg)
    res_exceed = classify_modulation(f, 7.0, cfg)

    assert res_within["status"] == "within"
    assert res_within["allowed"] == pytest.approx(6.1, rel=1e-6)
    assert res_within["margin"] < 0.0

    assert res_exceed["status"] == "exceeds"
    assert res_exceed["allowed"] == pytest.approx(6.1, rel=1e-6)
    assert res_exceed["margin"] > 0.0
