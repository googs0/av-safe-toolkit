import numpy as np
from avsafe_descriptors.light import tlm_metrics, window_metrics, MinuteAggregator

def test_basic_sine_120hz_pm():
    fs = 2000.0
    t = np.arange(0, 1.0, 1/fs)
    # DC 1.0 with 20% modulation at 120 Hz
    x = 1.0 + 0.2 * np.sin(2*np.pi*120.0*t)
    m = tlm_metrics(x, fs, mains_hint=60.0)
    assert 100.0 < m["f_flicker_Hz"] < 140.0
    assert 15.0 < m["pct_mod"] < 25.0
    assert 0.0 <= m["flicker_index"] <= 1.0

def test_minute_aggregate_shape():
    fs = 2000.0
    x = np.ones(int(fs*2))  # 2 seconds of steady light
    agg = MinuteAggregator()
    for w in window_metrics(x, fs, window_s=1.0, step_s=1.0, mains_hint=50.0):
        agg.add(w)
    s = agg.summary()
    assert set(s.keys()) == {"f_flicker_Hz", "pct_mod_p95", "flicker_index_p95"}
