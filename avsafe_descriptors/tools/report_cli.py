from __future__ import annotations
import argparse, json
from avsafe_descriptors.server.report_core import html_from

def main():
    ap = argparse.ArgumentParser(description="Render HTML report from minutes + rule results")
    ap.add_argument("--minutes", required=True)
    ap.add_argument("--results", required=False, default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    minutes = [json.loads(l) for l in open(args.minutes) if l.strip()]
    results = json.load(open(args.results)) if args.results else []
    html = html_from(minutes, results, integrity_summary=None)
    open(args.out,"w").write(html)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
