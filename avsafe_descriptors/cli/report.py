
from __future__ import annotations
import argparse
from ..report.render_html import render

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", default="report.html")
    args = ap.parse_args()

    render(args.minutes, args.results, args.out)
    print(f"Wrote {args.out}")

if __name__ == "__main__":
    main()
