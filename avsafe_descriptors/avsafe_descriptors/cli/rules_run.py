
from __future__ import annotations
import argparse, json
from ..rules.profile_loader import load_profile
from ..rules.evaluator import evaluate

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", required=True)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--locale", default=None)
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()

    prof = load_profile(args.profile)
    res = evaluate(args.minutes, prof, locale=args.locale)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"Wrote results to {args.out}")

if __name__ == "__main__":
    main()
