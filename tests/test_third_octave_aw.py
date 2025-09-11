import numpy as np
from avsafe_descriptors.audio.third_octave import third_octave_levels_db_spl

def test_a_weighted_band_reduces_low_freq():
    fs = 48_000; t = np.arange(0, fs)/fs
    sig = np.sqrt(2)*1.0*np.sin(2*np.pi*100*t)  # 100 Hz tone
    res_unw = third_octave_levels_db_spl(sig, fs, a_weighted=False)
    res_aw  = third_octave_levels_db_spl(sig, fs, a_weighted=True)
    centers = res_unw["centers_hz"]
    idx = int(np.argmin(np.abs(centers - 100.0)))
    assert res_aw["levels_db"][idx] < res_unw["levels_db"][idx] - 2.0
