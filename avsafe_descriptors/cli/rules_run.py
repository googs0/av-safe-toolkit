#!/usr/bin/env python3
"""
AV-SAFE: Rules evaluation CLI

Runs the rules engine on a minutes file using a WHO/IEEE (and locale-aware) profile,
and writes a JSON results artifact (or prints to stdout).

Examples
--------
  avsafe-rules --minutes data/minutes.jsonl --profile rules/profiles/who_ieee.json --out out/results.json
  avsafe-rules --minutes m.jsonl --profile profiles/de.json --stdout --pretty
  avsafe-rules --minutes m.jsonl --profile profiles/us.json --out out/results.json --overwrite --print-summary

Notes
-----
This CLI calls:
  - load_profile(profile_path) from rules.profile_loader
  - evaluate(minutes_path, profile, locale=None) from rules.evaluator

Both functions are expected to be pure and file-path based, keeping this CLI dependency-light.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Optional

EXIT_OK = 0
EXIT_BAD_ARGS = 2
EXIT_RUNTIME = 1

try:
    from ..rules.profile_loader import load_profile  # type: ignore
    from ..rules.evaluator import evaluate  # type: ignore
except Exception as e:  # pragma: no cover
    print("FATAL: cannot import rules modules ('..rules.profile_loader', '..rules.evaluator').", file=sys.stderr)
    raise


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="avsafe-rules",
        description="Evaluate AV-SAFE rules on minute summaries with a selected profile.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  avsafe-rules --minutes data/minutes.jsonl --profile rules/profiles/who_ieee.json --out out/results.json\n"
            "  avsafe-rules --minutes m.jsonl --profile profiles/de.json --stdout --pretty\n"
            "  avsafe-rules --minutes m.jsonl --profile profiles/us.json --out out/results.json --overwrite --print-summary\n"
        ),
    )
    p.add_argument(
        "--minutes",
        required=True,
        help="Path to minute summaries (e.g., JSONL with per-minute descriptors).",
    )
    p.add_argument(
        "--profile",
        required=True,
        help="Path to a rules profile JSON (WHO/IEEE thresholds, rubric, locale defaults).",
    )
    p.add_argument(
        "--locale",
        default=None,
        help="Locale code (e.g., 'de-DE', 'en-GB'). If omitted, evaluator/profile defaults are used.",
    )
    out_group = p.add_mutually_exclusive_group()
    out_group.add_argument(
        "--out",
        default="results.json",
        help="Output JSON path (default: results.json). Ignored if --stdout is set.",
    )
    out_group.add_argument(
        "--stdout",
        action="store_true",
        help="Write JSON to stdout instead of a file.",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing output file.",
    )
    fmt = p.add_mutually_exclusive_group()
    fmt.add_argument(
        "--pretty",
        action="true",
        help=argparse.SUPPRESS,  # keep CLI clean; use --indent instead (preferred)
    )
    p.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Pretty-print JSON with this indent (set 0 for compact). Default: 2.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Load inputs and evaluate, but do not write the output artifact.",
    )
    p.add_argument(
        "--print-summary",
        action="store_true",
        help="After evaluation, print a brief summary to stderr (keys, lengths).",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose errors (print full tracebacks).",
    )
    return p.parse_args(argv)


def ensure_file(path: Path, what: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{what} not found: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{what} is not a file: {path}")


def _json_summary(obj: Any) -> str:
    """Tiny, defensive summary for heterogeneous results."""
    try:
        if isinstance(obj, dict):
            keys = list(obj.keys())
            preview = ", ".join(keys[:5]) + ("…" if len(keys) > 5 else "")
            return f"dict(keys={len(keys)}: {preview})"
        if isinstance(obj, list):
            return f"list(len={len(obj)})"
        return f"{type(obj).__name__}"
    except Exception:
        return "unknown"


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    minutes_path = Path(args.minutes).expanduser().resolve()
    profile_path = Path(args.profile).expanduser().resolve()

    # Checks
    try:
        ensure_file(minutes_path, "Minutes")
        ensure_file(profile_path, "Profile")
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_BAD_ARGS

    # Load profile
    try:
        profile = load_profile(str(profile_path))
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: failed to load profile {profile_path}: {e}", file=sys.stderr)
        return EXIT_RUNTIME

    # Evaluate
    try:
        results = evaluate(str(minutes_path), profile, locale=args.locale)
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: evaluation failed: {e}", file=sys.stderr)
        return EXIT_RUNTIME

    if args.print_summary:
        print(f"[summary] results = {_json_summary(results)}", file=sys.stderr)

    # No write mode
    if args.dry_run or args.stdout:
        try:
            indent = None if args.indent == 0 else args.indent
            json.dump(results, sys.stdout, ensure_ascii=False, indent=indent)
            if indent is not None:
                sys.stdout.write("\n")
            sys.stdout.flush()
        except Exception as e:
            if args.verbose:
                traceback.print_exc()
            print(f"ERROR: failed to write JSON to stdout: {e}", file=sys.stderr)
            return EXIT_RUNTIME
        return EXIT_OK

    # File write
    out_path = Path(args.out).expanduser()
    try:
        # Keep relative paths relative to CWD; ensure parent exists
        parent = (Path.cwd() / out_path).parent if not out_path.is_absolute() else out_path.parent
        parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: cannot create output directory for {out_path}: {e}", file=sys.stderr)
        return EXIT_RUNTIME

    if out_path.exists() and not args.overwrite:
        print(f"ERROR: output exists: {out_path}. Use --overwrite to replace.", file=sys.stderr)
        return EXIT_BAD_ARGS

    try:
        indent = None if args.indent == 0 else args.indent
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=indent)
            if indent is not None:
                f.write("\n")
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: failed to write {out_path}: {e}", file=sys.stderr)
        return EXIT_RUNTIME

    print(f"Wrote results to {out_path}")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
