from __future__ import annotations
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from pydantic import BaseModel
import yaml

class RuleResult(BaseModel):
    rule_id: str
    severity: str
    message: str
    details: Dict[str, Any]

@dataclass
class MinuteLike:
    timestamp_utc: datetime
    laeq_db: float | None = None
    lcpeak_db: float | None = None
    tlm_f_dom_hz: float | None = None
    tlm_percent_mod: float | None = None
    tlm_flicker_index: float | None = None

def _in_hour_range(ts: datetime, start: int, end: int) -> bool:
    h = ts.hour
    if start <= end: return start <= h < end
    return (h >= start) or (h < end)

def _proportion_over(values: List[float], threshold: float) -> float:
    vals = [v for v in values if v is not None]
    return (sum(1 for v in vals if v > threshold) / len(vals)) if vals else 0.0

def _ieee_limit(model: dict, f_hz: float, zone: str) -> float:
    segs = model.get(zone, [])
    for seg in segs:
        if seg['f_min'] <= f_hz < seg['f_max']:
            return seg['k']*f_hz + seg.get('b',0.0)
    if segs:
        last = segs[-1]
        f_clamped = min(max(f_hz,last['f_min']), last['f_max'])
        return last['k']*f_clamped + last.get('b',0.0)
    return float('inf')

def evaluate_rules(minutes: List[MinuteLike], rules_yaml: str) -> List[RuleResult]:
    cfg = yaml.safe_load(rules_yaml)
    results: List[RuleResult] = []

    laeq_series = [(m.timestamp_utc, m.laeq_db) for m in minutes if m.laeq_db is not None]
    lcpeak_series = [(m.timestamp_utc, m.lcpeak_db) for m in minutes if m.lcpeak_db is not None]
    fmod_pairs = [(m.tlm_f_dom_hz, m.tlm_percent_mod) for m in minutes if (m.tlm_f_dom_hz is not None and m.tlm_percent_mod is not None)]

    for rule in cfg.get("rules", []):
        rid = rule.get("id","unknown"); rtype = rule.get("type"); severity = rule.get("severity","INFO"); message = rule.get("message","")

        if rtype == "noise.laeq.exceedance":
            start, end = rule["hour_range"]; thr = float(rule["threshold_db"]); min_frac = float(rule.get("min_fraction", 0.1))
            vals = [v for (ts, v) in laeq_series if _in_hour_range(ts, start, end)]
            frac = _proportion_over(vals, thr)
            if frac >= min_frac:
                results.append(RuleResult(rule_id=rid, severity=severity, message=message, details={"fraction_over": frac, "threshold_db": thr, "hour_range":[start,end]}))

        elif rtype == "noise.lcpeak.max":
            thr = float(rule["threshold_db"])
            exc = [(ts, v) for (ts, v) in lcpeak_series if v is not None and v > thr]
            if exc:
                results.append(RuleResult(rule_id=rid, severity=severity, message=message, details={"count_exceedances": len(exc), "threshold_db": thr}))

        elif rtype == "light.flicker.ieee1789":
            model = rule.get("model", {}); assess_zone = rule.get("assess","LOW_RISK"); min_frac = float(rule.get("min_fraction",0.05))
            n_viol = 0
            for f, pm in fmod_pairs:
                if pm > _ieee_limit(model, float(f), assess_zone):
                    n_viol += 1
            frac = n_viol/len(fmod_pairs) if fmod_pairs else 0.0
            if frac >= min_frac:
                results.append(RuleResult(rule_id=rid, severity=severity, message=message, details={"fraction_over": frac, "zone": assess_zone}))

        elif rtype == "light.flicker.zone":
            f_cut = float(rule.get("f_cut_hz", 200.0)); amber_pm = float(rule.get("amber_pm_percent", 20.0)); red_pm = float(rule.get("red_pm_percent", 50.0))
            amber_min_frac = float(rule.get("amber_min_fraction", 0.10)); red_min_frac = float(rule.get("red_min_fraction", 0.05))
            total = max(1, len(fmod_pairs))
            amber = sum(1 for f, pm in fmod_pairs if (f <= f_cut and pm >= amber_pm))
            red = sum(1 for f, pm in fmod_pairs if (f <= f_cut and pm >= red_pm))
            if (red/total) >= red_min_frac:
                results.append(RuleResult(rule_id=rid, severity="RED", message=message + " (red)", details={"fraction": red/total, "f_cut_hz": f_cut, "pm_percent": red_pm}))
            elif (amber/total) >= amber_min_frac:
                results.append(RuleResult(rule_id=rid, severity=severity, message=message + " (amber)", details={"fraction": amber/total, "f_cut_hz": f_cut, "pm_percent": amber_pm}))

    return results
