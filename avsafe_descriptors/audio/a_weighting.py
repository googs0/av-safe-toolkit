
import math
from typing import Iterable, Dict

# IEC 61672 A-weighting (amplitude) transfer function constants
# Converted to dB correction as function of frequency.
# Source formula: standard approximation.
_A = 12200.0**2

def a_weight_db(f_hz: float) -> float:
    """Return A-weighting correction (dB) at frequency f_hz."""
    f2 = f_hz * f_hz
    num = (_A * f2 * f2)
    den = (f2 + 20.6**2) * math.sqrt((f2 + 107.7**2) * (f2 + 737.9**2)) * (f2 + _A)
    ra = num / den
    return 20.0 * math.log10(ra) + 2.0  # +2.0 for normalization to 1 kHz ≈ 0 dB

# ISO 1/3-octave band centers (25 bands from 20 Hz to 20 kHz typical)
ISO_THIRD_OCTAVE_CENTERS = [
    20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160,
    200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600,
    2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000
]

def a_weight_table() -> Dict[float, float]:
    return {float(c): a_weight_db(float(c)) for c in ISO_THIRD_OCTAVE_CENTERS}
