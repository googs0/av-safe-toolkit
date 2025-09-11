from __future__ import annotations
import argparse, json, sys, yaml
from datetime import datetime
from typing import List
from avsafe_descriptors.rules.engine import evaluate_rules, MinuteLike
from avsafe_descriptors.rules.profiles import load_profile_yaml

def load_minutes(jsonl_path: str) -> List[MinuteLike]:
    out = []
    for line in open(jsonl_path, "r"):
        if not line.strip(): continue
        j = json.loads(line)
        ts = datetime.fromisoformat(j["timestamp_utc"].replace("Z","+00:00"))
        out.append(MinuteLike(timestamp_utc=ts, laeq_db=j.get("laeq_db"), lcpeak_db=j.get("lcpeak_db"),
                              tlm_f_dom_hz=j.get("tlm_f_dom_hz"), tlm_percent_mod=j.get("tlm_percent_mod"),
                              tlm_flicker_index=j.get("tlm_flicker_index")))
    return out

def main():
    ap = argparse.ArgumentParser(description="Evaluate AV-SAFE rules on minute summaries")
    ap.add_argument("--minutes", required=True)
    ap.add_argument("--rules", required=False)
    ap.add_argument("--profile", required=False)
    ap.add_argument("--locale", required=False)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.profile:
        ryaml = load_profile_yaml(args.profile, locale=args.locale)
    elif args.rules:
        ryaml = open(args.rules, "r").read()
    else:
        raise SystemExit("Provide --rules or --profile")

    minutes = load_minutes(args.minutes)
    results = evaluate_rules(minutes, ryaml)
    out = [r.model_dump() for r in results]
    if args.out:
        json.dump(out, open(args.out,"w"), indent=2); print(f"Wrote rule results to {args.out}")
    else:
        json.dump(out, sys.stdout, indent=2); print()

if __name__ == "__main__":
    main()
