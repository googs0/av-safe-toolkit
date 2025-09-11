from datetime import datetime, timezone, timedelta
from avsafe_descriptors.rules.engine import evaluate_rules, MinuteLike
import yaml

def toy_minutes():
    start = datetime(2025,1,1,21,0, tzinfo=timezone.utc); mins = []
    for i in range(180):
        ts = start + timedelta(minutes=i); la = 40 + (i/10) if i < 120 else 42
        mins.append(MinuteLike(timestamp_utc=ts, laeq_db=la))
    return mins

def test_noise_rule_exceedance():
    minutes = toy_minutes()
    rules = {'rules':[{'id':'night','type':'noise.laeq.exceedance','hour_range':[22,7],'threshold_db':45,'min_fraction':0.10,'severity':'AMBER','message':'Night exceedance'}]}
    res = evaluate_rules(minutes, yaml.safe_dump(rules))
    assert any(r.rule_id=='night' for r in res)

def test_light_rule_ieee():
    start = datetime(2025,1,1,12,0, tzinfo=timezone.utc); minutes = []
    for i in range(100):
        ts = start + timedelta(minutes=i)
        if i < 10: minutes.append(MinuteLike(timestamp_utc=ts, tlm_f_dom_hz=120.0, tlm_percent_mod=60.0))
        else:      minutes.append(MinuteLike(timestamp_utc=ts, tlm_f_dom_hz=120.0, tlm_percent_mod=10.0))
    rules = {'rules':[{'id':'ieee','type':'light.flicker.ieee1789','assess':'LOW_RISK','min_fraction':0.05,'severity':'AMBER','message':'Exceeds LOW_RISK','model':{'LOW_RISK':[{'f_min':0,'f_max':90,'k':0.033,'b':0},{'f_min':90,'f_max':1250,'k':0.10,'b':0}]}}]}
    import yaml; res = evaluate_rules(minutes, yaml.safe_dump(rules))
    assert any(r.rule_id=='ieee' for r in res)
