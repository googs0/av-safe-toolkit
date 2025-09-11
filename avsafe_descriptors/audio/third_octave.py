
from __future__ import annotations
import math
from typing import Dict, Iterable, Tuple, List

# Helper to compute band edges for ISO 1/3-octave bands
def third_octave_edges(center_hz: float) -> Tuple[float, float]:
    k = 2 ** (1/6)  # band ratio for 1/3-octave edges
    return (center_hz / k, center_hz * k)

def centers_20_20k() -> List[float]:
    centers = [20.0]
    # grow by factor 2^(1/3) per band until ~20kHz
    f = 20.0
    while f < 20000 * (2 ** (-1/6)):
        f *= 2 ** (1/3)
        centers.append(round(f, 1))
    # snap to common rounded centers
    # (for simplicity we rely on the known list in a_weighting for display)
    return centers
