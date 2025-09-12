#!/usr/bin/env python3
"""
AV-SAFE: Report generator CLI

Generates a standards-aligned HTML report from:
  - minute summaries (privacy-preserving descriptors), and
  - analysis/rubric results.

Examples
--------
  avsafe-report --minutes data/minutes.jsonl --results out/results.json --out reports/room-101.html
  avsafe-report --minutes data/minutes.jsonl --results out/results.json --stdout
  avsafe-report --minutes m.jsonl --results r.json --out report.html --open

Notes
-----
This CLI calls `render()` from `report.render_html`. The current expected signature is:
    render(minutes_path, results_path, out_path)

If that function grows optional features later (e.g., title, base_url), this CLI remains compatible.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path
from typing import Optional
import webbrowser

# Import the renderer (keep relative import as you had it)
try:
    from ..report.render_html import render  # type: ignore
except Exception as e:  # pragma: no cover
    print("FATAL: cannot import report renderer '..report.render_html.render'.", file=sys.stderr)
    raise


EXIT_OK = 0
EXIT_BAD_ARGS = 2
EXIT_RUNTIME = 1


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="avsafe-report",
        description="Generate an AV-SAFE HTML report from minute summaries and analysis results.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  avsafe-report --minutes data/minutes.jsonl --results out/results.json --out reports/room-101.html\n"
            "  avsafe-report --minutes data/minutes.jsonl --results out/results.json --stdout\n"
            "  avsafe-report --minutes m.jsonl --results r.json --out report.html --open\n"
        ),
    )
    p.add_argument(
        "--minutes",
        required=True,
        help="Path to minute summaries file (e.g., JSONL with per-minute descriptors).",
    )
    p.add_argument(
        "--results",
        required=True,
        help="Path to analysis/rubric results (JSON/JSONL your renderer expects).",
    )
    out_group = p.add_mutually_exclusive_group()
    out_group.add_argument(
        "--out",
        default="report.html",
        help="Output HTML path (default: report.html). Ignored if --stdout is set.",
    )
    out_group.add_argument(
        "--stdout",
        action="store_true",
        help="Write HTML to stdout instead of a file.",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting an existing output file.",
    )
    p.add_argument(
        "--open",
        action="store_true",
        help="Open the generated report in the default browser.",
    )
    p.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose errors (print full tracebacks).",
    )
    return p.parse_args(argv)


def ensure_readable(path: Path, what: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{what} not found: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{what} is not a file: {path}")
    # Optionally check readability (on most systems, existence is enough)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    minutes_path = Path(args.minutes).expanduser().resolve()
    results_path = Path(args.results).expanduser().resolve()

    try:
        ensure_readable(minutes_path, "Minutes")
        ensure_readable(results_path, "Results")
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: {e}", file=sys.stderr)
        return EXIT_BAD_ARGS

    # Handle stdout mode early
    if args.stdout:
        try:
            # Render to a temp file, then print its contents to stdout to keep renderer API simple
            # If your render() can accept '-' for stdout in the future, switch to that.
            from tempfile import NamedTemporaryFile

            with NamedTemporaryFile(prefix="avsafe_", suffix=".html", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                render(str(minutes_path), str(results_path), str(tmp_path))
                sys.stdout.write(tmp_path.read_text(encoding="utf-8"))
                sys.stdout.flush()
            finally:
                # Best-effort cleanup
                try:
                    tmp_path.unlink(missing_ok=True)
                except Exception:
                    pass
            return EXIT_OK
        except Exception as e:
            if args.verbose:
                traceback.print_exc()
            print(f"ERROR: failed to generate report to stdout: {e}", file=sys.stderr)
            return EXIT_RUNTIME

    # File output mode
    out_path = Path(args.out).expanduser()
    # If relative, keep relative (nice for CI artifacts), but ensure parent exists
    try:
        out_parent = (Path.cwd() / out_path).parent if not out_path.is_absolute() else out_path.parent
        out_parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: cannot create output directory for {out_path}: {e}", file=sys.stderr)
        return EXIT_RUNTIME

    # Prevent accidental overwrite unless --overwrite
    if out_path.exists() and not args.overwrite:
        print(f"ERROR: output exists: {out_path}. Use --overwrite to replace.", file=sys.stderr)
        return EXIT_BAD_ARGS

    try:
        render(str(minutes_path), str(results_path), str(out_path))
    except Exception as e:
        if args.verbose:
            traceback.print_exc()
        print(f"ERROR: rendering failed: {e}", file=sys.stderr)
        return EXIT_RUNTIME

    print(f"Wrote {out_path}")

    if args.open:
        try:
            webbrowser.open_new_tab(out_path.resolve().as_uri())
        except Exception:
            # Non-fatal: just inform
            print("Note: could not open in browser automatically.", file=sys.stderr)

    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
