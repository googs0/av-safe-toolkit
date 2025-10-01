#!/usr/bin/env python3
"""
Enforce privacy defaults on minute JSONL:
- set default retention_days if missing
- truncate geohash length to a max (default 7)
Usage:
  python -m avsafe_descriptors.cli.policy_enforce --in minutes.jsonl --out minutes_sanitized.jsonl
"""
import argparse, json, sys

def run(inp, outp, retention=365, max_geohash=7):
    n=0
    for line in inp:
        line=line.strip()
        if not line: continue
        rec=json.loads(line)
        rec.setdefault("retention_days", retention)
        loc=rec.get("location") or {}
        gh=loc.get("geohash")
        if isinstance(gh,str) and len(gh)>max_geohash:
            loc["geohash"]=gh[:max_geohash]
            rec["location"]=loc
        outp.write(json.dumps(rec, ensure_ascii=False)+"\n"); n+=1
    return n

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--out", dest="out", required=True)
    ap.add_argument("--retention", type=int, default=365)
    ap.add_argument("--max-geohash", type=int, default=7)
    args=ap.parse_args()
    with open(args.inp,"r",encoding="utf-8") as f, open(args.out,"w",encoding="utf-8") as g:
        n=run(f,g,args.retention,args.max_geohash)
    print(f"Sanitized {n} minutes → {args.out}")

if __name__=="__main__":
    main()
