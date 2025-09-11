from __future__ import annotations
import numpy as np
from typing import Optional, Dict
from scipy.signal import welch

def third_octave_centers_hz() -> np.ndarray:
    return np.array([25.0,31.5,40.0,50.0,63.0,80.0,100.0,125.0,160.0,200.0,
                     250.0,315.0,400.0,500.0,630.0,800.0,1000.0,1250.0,1600.0,
                     2000.0,2500.0,3150.0,4000.0,5000.0,6300.0,8000.0,10000.0,
                     12500.0,16000.0,20000.0])

def third_octave_band_edges(centers_hz: np.ndarray) -> np.ndarray:
    k = 2**(1/6)  # bandwidth factor
    return np.stack([centers_hz/k, centers_hz*k], axis=1)

def a_weighting_db(f_hz: np.ndarray) -> np.ndarray:
    f = np.asarray(f_hz, dtype=float)
    f = np.where(f<=0, 1e-20, f)
    w = 2*np.pi*f
    f1, f2c, f3, f4 = 20.598997, 107.65265, 737.86223, 12194.217
    w1, w2c, w3, w4 = 2*np.pi*np.array([f1, f2c, f3, f4])
    num = (w4**2)*(w**4)
    den = (w**2 + w1**2) * (w**2 + w2c**2) * (w**2 + w3**2) * (w**2 + w4**2)
    A = num/den
    A_db = 20*np.log10(np.sqrt(A))
    # normalize to 0 dB at 1 kHz
    w1k = 2*np.pi*1000.0
    num1k = (w4**2)*(w1k**4)
    den1k = (w1k**2 + w1**2) * (w1k**2 + w2c**2) * (w1k**2 + w3**2) * (w1k**2 + w4**2)
    A1k_db = 20*np.log10(np.sqrt(num1k/den1k))
    return A_db - A1k_db

def third_octave_levels_db_spl(x: np.ndarray, fs: int, p_ref: float = 20e-6, nperseg: Optional[int] = None, a_weighted: bool = False) -> Dict[str, np.ndarray]:
    x = np.asarray(x, dtype=float)
    centers = third_octave_centers_hz()
    edges = third_octave_band_edges(centers)
    if nperseg is None:
        nperseg = min(len(x), max(4096, int(fs/64)))
    f, Pxx = welch(x, fs=fs, window="hann", nperseg=nperseg, noverlap=nperseg//2, detrend="constant", scaling="density")
    if a_weighted:
        A_db = a_weighting_db(f)
        Pxx = Pxx * (10**(A_db/10.0))
    levels_db = np.empty(len(centers), dtype=float)
    for i, (f_low, f_high) in enumerate(edges):
        m = (f >= f_low) & (f <= f_high)
        if not np.any(m):
            levels_db[i] = -np.inf; continue
        p2 = np.trapz(Pxx[m], f[m])
        levels_db[i] = -np.inf if p2 <= 0 else 10.0*np.log10(p2/(p_ref**2))
    return {"centers_hz": centers, "levels_db": levels_db}
