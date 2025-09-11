
from __future__ import annotations
import json, statistics
from typing import Dict, Tuple
from .profile_loader import RulesProfile
from .ieee_1789 import allowed_mod_percent

def evaluate(minutes_path: str, profile: RulesProfile, locale: str | None = None) -> Dict:
    minutes = [json.loads(line) for line in open(minutes_path, 'r', encoding='utf-8') if line.strip()]
    n = len(minutes)
    out = {"n_minutes": n, "flags": [], "stats": {}, "flicker": {}, "noise": {}}
    if n == 0:
        out["flags"].append("no data")
        return out

    laeq = [m.get("audio",{}).get("laeq_db") for m in minutes if m.get("audio")]
    mean_laeq = statistics.fmean(laeq) if laeq else None
    noise_limits = profile.noise.get("laeq_limits_db", {})
    # If locale provided, use it; else use 'default'
    loc = locale if locale in noise_limits else "default"
    limit = noise_limits.get(loc, noise_limits.get("default", 55))
    pct_over = 100.0 * sum(1 for x in laeq if x is not None and x > limit) / max(len(laeq), 1)
    out["noise"] = {"limit_db": limit, "pct_over": pct_over, "mean_laeq": mean_laeq}
    if pct_over > profile.noise.get("flag_threshold_pct", 10.0):
        out["flags"].append(f"Noise: LAeq>{limit} dB in {pct_over:.1f}% of minutes")

    # Flicker evaluation
    flick = [(m.get("light",{}).get("tlm_freq_hz"), m.get("light",{}).get("tlm_mod_percent")) for m in minutes]
    violations = 0
    evaluated = 0
    for f, mod in flick:
        if f is None or mod is None: 
            continue
        evaluated += 1
        allowed = allowed_mod_percent(f, profile.flicker.get("percent_mod_vs_freq", {}))
        if mod > allowed:
            violations += 1
    pct_viol = 100.0 * violations / max(evaluated, 1)
    out["flicker"] = {"evaluated": evaluated, "violations": violations, "pct_violations": pct_viol}
    if pct_viol > profile.flicker.get("flag_threshold_pct", 0.0):
        out["flags"].append(f"Flicker: {pct_viol:.1f}% minutes exceed IEEE-1789 curve")
    return out
