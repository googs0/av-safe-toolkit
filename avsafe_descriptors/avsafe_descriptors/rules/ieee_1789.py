
from __future__ import annotations
from typing import Dict

def allowed_mod_percent(f_hz: float, params: Dict) -> float:
    """Piecewise mapping: allowed percent modulation vs frequency.
    params expects: {'segments': [{'f_min':..,'f_max':..,'a':..,'b':..}, ...]}
    rule: for given f, pick matching segment and compute a + b/f.
    """
    segs = params.get("segments", [])
    for s in segs:
        if s["f_min"] <= f_hz <= s["f_max"]:
            return s["a"] + s["b"]/max(f_hz, 1e-6)
    # default fallback (very conservative)
    return params.get("default", 1.0)
