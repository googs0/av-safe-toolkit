from __future__ import annotations
import yaml

def load_profile_yaml(path: str, locale: str | None = None) -> str:
    with open(path, 'r') as f:
        cfg = yaml.safe_load(f)
    if locale and 'locales' in cfg:
        loc = cfg['locales'].get(locale.lower())
        if loc:
            for r in cfg.get('rules', []):
                if r.get('type') == 'noise.laeq.exceedance':
                    if 'night' in r.get('id','').lower() or r.get('hour_range') == [22,7]:
                        r['threshold_db'] = loc.get('night_threshold_db', r.get('threshold_db'))
                        r['hour_range'] = loc.get('quiet_hours', r.get('hour_range'))
                    elif 'day' in r.get('id','').lower() or r.get('hour_range') == [7,22]:
                        r['threshold_db'] = loc.get('day_threshold_db', r.get('threshold_db'))
    return yaml.safe_dump(cfg)
