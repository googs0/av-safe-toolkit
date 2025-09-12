#!/usr/bin/env python3
"""
Validate all HF-AVC case files against the JSON Schema.

Usage:
  python cli/validate_cases.py
  python cli/validate_cases.py --dir hf_avc/data/cases --schema schemas/case_schema_v1.json
"""

from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from jsonschema import Draft202012Validator, exceptions as jse  # pip install jsonschema

def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="hf_avc/data/cases",
                    help="Directory with case JSON files.")
    ap.add_argument("--schema", default="schemas/case_schema_v1.json",
                    help="JSON Schema path.")
    return ap.parse_args()

def main() -> int:
    args = parse_args()
    schema_path = Path(args.schema)
    cases_dir = Path(args.dir)

    if not schema_path.is_file():
        print(f"FATAL: schema not found: {schema_path}", file=sys.stderr)
        return 2
    if not cases_dir.is_dir():
        print(f"FATAL: cases directory not found: {cases_dir}", file=sys.stderr)
        return 2

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    errors = 0
    for p in sorted(cases_dir.glob("*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            validator.validate(data)
            print(f"OK   {p}")
        except jse.ValidationError as e:
            errors += 1
            path = "/".join(map(str, e.path)) or "(root)"
            print(f"FAIL {p}\n  -> {e.message}\n  at {path}\n", file=sys.stderr)
        except Exception as e:
            errors += 1
            print(f"FAIL {p}\n  -> {e}\n", file=sys.stderr)

    if errors:
        print(f"{errors} file(s) failed validation.", file=sys.stderr)
        return 1
    print("All case files valid.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
