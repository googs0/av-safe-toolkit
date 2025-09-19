import json
import math
import numpy as np
import imageio.v3 as iio
from pathlib import Path

from avsafe_descriptors.video.luma import read_video_luma
from avsafe_descriptors.light import window_metrics, MinuteAggregator

ASSETS = Path(__file__).parent / "assets" / "video"
ASSETS.mkdir(parents=True, exist_ok=True)

def _make_sine_flicker(path: Path, fps=60, seconds=5, freq_hz=10.0, size=128, amplitude=0.4):
    n = int(fps * seconds)
    t = np.arange(n) / fps
    frames = []
    for ti in t:
        level = 0.5 * (1 + amplitude * math.sin(2 * math.pi * freq_hz * ti))  # 0..1
        frames.append(np.full((size, size, 3), int(level * 255), np.uint8))
    iio.imwrite(path, np.stack(frames), fps=fps)

def _make_pwm_alias(path: Path, fps=30, seconds=5, pwm_hz=100.0, size=128, duty=0.5, lo=60, hi=255):
    n = int(fps * seconds)
    t = np.arange(n) / fps
    frames = []
    for ti in t:
        phase = (ti * pwm_hz) % 1.0
        level = hi if phase < duty else lo
        frames.append(np.full((size, size, 3), level, np.uint8))
    iio.imwrite(path, np.stack(frames), fps=fps)

def _make_constant(path: Path, fps=60, seconds=5, size=128, level=180):
    n = int(fps * seconds)
    frames = [np.full((size, size, 3), level, np.uint8) for _ in range(n)]
    iio.imwrite(path, np.stack(frames), fps=fps)

def ensure_assets():
    a = ASSETS / "avsafe_flicker_10hz_60fps.mp4"
    b = ASSETS / "avsafe_pwm_100hz_30fps_alias10hz.mp4"
    c = ASSETS / "avsafe_constant_60fps.mp4"
    if not a.exists(): _make_sine_flicker(a)
    if not b.exists(): _make_pwm_alias(b)
    if not c.exists(): _make_constant(c)
    return a, b, c

def _minute_summary(y: np.ndarray, fs: float, mains_hint: float | None):
    agg = MinuteAggregator()
    for m in window_metrics(y, fs=fs, window_s=1.0, step_s=1.0, mains_hint=mains_hint):
        agg.add(m)
    return agg.summary()

def test_flicker_sine_10hz_detected():
    a, _, _ = ensure_assets()
    y, fs = read_video_luma(str(a))
    s = _minute_summary(y, fs, mains_hint=None)
    assert 8.5 <= s["f_flicker_Hz"] <= 11.5, s  # within ±1.5 Hz
    assert s["pct_mod_p95"] > 5.0, s  # clearly >0

def test_pwm_100hz_aliases_to_10hz_at_30fps():
    _, b, _ = ensure_assets()
    y, fs = read_video_luma(str(b))
    s = _minute_summary(y, fs, mains_hint=None)
    assert 8.0 <= s["f_flicker_Hz"] <= 12.0, s  # alias ~10 Hz
    assert s["pct_mod_p95"] > 5.0, s

def test_constant_low_modulation():
    _, _, c = ensure_assets()
    y, fs = read_video_luma(str(c))
    s = _minute_summary(y, fs, mains_hint=None)
    assert s["pct_mod_p95"] < 0.5, s
    assert s["flicker_index_p95"] < 0.01, s
