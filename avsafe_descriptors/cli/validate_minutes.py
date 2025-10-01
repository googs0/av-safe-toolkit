#!/usr/bin/env python3
"""
Validate minute JSONL against the v1 schema.
Usage:
  python -m avsafe_descriptors.cli.validate_minutes --in minutes.jsonl \
    --schema avsafe_descriptors/hf_avc/schemas/avsafe-minute-summary.schema.json
"""
import argparse, json
from jsonschema import Draft202012Validator

def load_schema(path):
    with open(path,"r",encoding="utf-8") as f: return json.load(f)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True)
    ap.add_argument("--schema", required=True)
    args=ap.parse_args()
    schema=load_schema(args.schema)
    val=Draft202012Validator(schema)
    errs=0; n=0
    with open(args.inp,"r",encoding="utf-8") as f:
        for i,line in enumerate(f,1):
            line=line.strip()
            if not line: continue
            n+=1
            rec=json.loads(line)
            for e in val.iter_errors(rec):
                print(f"Line {i}: {e.message}")
                errs+=1
    if errs:
        raise SystemExit(f"Validation failed: {errs} error(s) across {n} records.")
    print(f"Validation OK: {n} records")

if __name__=="__main__":
    main()
