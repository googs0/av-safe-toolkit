# tests/test_rules_eval.py
from __future__ import annotations

import json
from pathlib import Path
import pytest

from avsafe_descriptors.rules.profile_loader import load_profile
from avsafe_descriptors.rules.evaluator import evaluate


def _write_minutes_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _make_minute(idx: int, laeq: float, lcpeak: float = None,
                 tlm_freq_hz: float = 120.0, tlm_mod_percent: float = 7.5,
                 flicker_index: float = 0.06) -> dict:
    """Construct a minimal minute descriptor compatible with the pipeline."""
    if lcpeak is None:
        lcpeak = laeq + 10.0
    return {
        "idx": idx,
        "ts": f"2025-01-01T00:{idx:02d}:00Z",
        "audio": {
            "laeq_db": float(laeq),
            "lcpeak_db": float(lcpeak),
            # empty 1/3-octave map is allowed by our evaluator
            "third_octave_db": {}
        },
        "light": {
            "tlm_freq_hz": float(tlm_freq_hz),
            "tlm_mod_percent": float(tlm_mod_percent),
            "flicker_index": float(flicker_index)
        },
        # chain hash is validated elsewhere; use a stub for testing evaluator
        "chain": {"hash": "0" * 64}
    }


def _load_default_profile() -> dict:
    # Path relative to repo root; tests run from project root in CI
    profile_path = Path("avsafe_descriptors/rules/profiles/who_ieee_profile.yaml")
    assert profile_path.exists(), f"Missing profile: {profile_path}"
    return load_profile(str(profile_path))


def test_rules_flag_when_over_limit(tmp_path: Path):
    """
    Build 10 minutes where the first half are clearly above the WHO night guideline
    (e.g., 70 dB) and the rest below (50 dB). Expect a non-zero exceedance proportion.
    """
    minutes = []
    for i in range(10):
        la = 70.0 if i < 5 else 50.0
        minutes.append(_make_minute(i, la))
    mp = tmp_path / "minutes_over.jsonl"
    _write_minutes_jsonl(mp, minutes)

    prof = _load_default_profile()
    res = evaluate(str(mp), prof, locale="default")

    # Be tolerant to structure: expect a "noise" section with pct_over > 0
    assert isinstance(res, dict)
    assert "noise" in res and isinstance(res["noise"], dict)
    pct_over = res["noise"].get("pct_over")
    assert isinstance(pct_over, (int, float)), "noise.pct_over should be numeric"
    assert pct_over > 0.0, "Expected some exceedance"

    # If the evaluator exposes a boolean flag, it should be true here
    flag = res["noise"].get("flag", res["noise"].get("exceeded"))
    if flag is not None:
        assert bool(flag) is True


def test_rules_all_clear_when_below_limit(tmp_path: Path):
    """
    Build 10 minutes all comfortably below a typical night guideline (e.g., 35 dB).
    Expect zero exceedance and (if present) a false flag.
    """
    minutes = [_make_minute(i, 35.0) for i in range(10)]
    mp = tmp_path / "minutes_clear.jsonl"
    _write_minutes_jsonl(mp, minutes)

    prof = _load_default_profile()
    res = evaluate(str(mp), prof, locale="default")

    assert isinstance(res, dict)
    assert "noise" in res and isinstance(res["noise"], dict)
    pct_over = res["noise"].get("pct_over")
    assert isinstance(pct_over, (int, float))
    assert pct_over == 0 or pytest.approx(pct_over, abs=1e-9) == 0

    flag = res["noise"].get("flag", res["noise"].get("exceeded"))
    if flag is not None:
        assert bool(flag) is False


def test_light_fields_do_not_break_noise_evaluation(tmp_path: Path):
    """
    Even if light metrics vary or are borderline, noise exceedance logic should still run.
    This is a smoke test to ensure evaluator tolerates empty/varied third_octave maps, etc.
    """
    minutes = []
    # Alternate modulation around a low-risk boundary but keep audio clearly over threshold for half
    for i in range(10):
        la = 65.0 if i % 2 == 0 else 38.0
        tlm_mod = 7.9 if i % 2 == 0 else 4.0
        minutes.append(_make_minute(i, la, tlm_mod_percent=tlm_mod))
    mp = tmp_path / "minutes_light_mix.jsonl"
    _write_minutes_jsonl(mp, minutes)

    prof = _load_default_profile()
    res = evaluate(str(mp), prof, locale="default")

    assert "noise" in res
    pct_over = res["noise"].get("pct_over")
    assert isinstance(pct_over, (int, float))
    assert pct_over > 0.0  # half the minutes (≈50%) exceed typical night guideline


def test_locale_fallback_does_not_crash(tmp_path: Path):
    """
    If an unknown locale is provided, evaluator should either
    fall back to defaults or raise a clear error (not crash).
    We accept either behavior; if it raises, it should be a ValueError.
    """
    minutes = [_make_minute(i, 50.0) for i in range(3)]
    mp = tmp_path / "minutes_locale.jsonl"
    _write_minutes_jsonl(mp, minutes)

    prof = _load_default_profile()
    try:
        res = evaluate(str(mp), prof, locale="unknown-locale")
        assert isinstance(res, dict)
        assert "noise" in res
    except ValueError:
        # Acceptable outcome: explicit error about unknown locale
        pass
