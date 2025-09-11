
import json, tempfile, os
from avsafe_descriptors.rules.profile_loader import load_profile
from avsafe_descriptors.rules.evaluator import evaluate

def test_rules_flag_when_over_limit(tmp_path):
    minutes = []
    for i in range(10):
        minutes.append({
            "idx": i, "ts": f"2020-01-01T00:{i:02d}:00Z",
            "audio":{"laeq_db": 70.0 if i<5 else 50.0, "lcpeak_db": 80.0, "third_octave_db":{}},
            "light":{"tlm_freq_hz": 100.0, "tlm_mod_percent": 10.0, "flicker_index": 0.1},
            "chain":{"hash":"00"}
        })
    mp = tmp_path/"m.jsonl"
    with open(mp,"w") as f:
        for m in minutes: f.write(json.dumps(m)+"\n")
    prof = load_profile("avsafe_descriptors/rules/profiles/who_ieee_profile.yaml")
    res = evaluate(str(mp), prof, locale="default")
    assert res["noise"]["pct_over"] > 0
