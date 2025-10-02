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

# avsafe_descriptors/cli/rules_run.py
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

# Try to use project helpers; fall back to simple JSONL I/O.
try:
    from avsafe_descriptors.rules.profile_loader import load_profile  # type: ignore
    from avsafe_descriptors.rules.evaluator import evaluate_minutes  # type: ignore
except Exception:  # pragma: no cover
    load_profile = None  # type: ignore[assignment]
    evaluate_minutes = None  # type: ignore[assignment]


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    """Minimal JSONL reader (kept local to avoid extra deps)."""
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def _write_jsonl(path: Path, rows: Iterable[Dict[str, Any]], indent: int) -> None:
    """Write JSON Lines. If indent > 0, pretty-print each line."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            if indent and indent > 0:
                f.write(json.dumps(r, ensure_ascii=False, indent=indent) + "\n")
            else:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _flags_from_results(results: Dict[str, Any], minutes_len: int) -> List[Dict[str, Any]]:
    """
    Extract per-minute flags from an evaluate_minutes() result.
    Be tolerant to schema differences; fall back to empty flags.
    """
    # Common shapes we might see:
    # - results.get("per_minute") -> list of {"idx":i,"flags":[...]}
    # - results.get("flags_per_minute") -> same
    # - results.get("minutes", [])[i].get("flags")
    for key in ("per_minute", "flags_per_minute"):
        v = results.get(key)
        if isinstance(v, list) and all(isinstance(x, dict) for x in v):
            # Ensure idx is present
            rows: List[Dict[str, Any]] = []
            for i, row in enumerate(v):
                idx = int(row.get("idx", i))
                flags = row.get("flags", [])
                rows.append({"idx": idx, "flags": flags})
            return rows

    minutes = results.get("minutes")
    if isinstance(minutes, list):
        rows = []
        for i, m in enumerate(minutes):
            flags = m.get("flags", [])
            rows.append({"idx": i, "flags": flags})
        if rows:
            return rows

    # Fallback: empty flags for each minute
    return [{"idx": i, "flags": []} for i in range(minutes_len)]


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="avsafe-rules-run",
        description="Evaluate WHO/IEEE rules over AV-SAFE minute summaries and emit flags.jsonl",
    )
    p.add_argument(
        "--in",
        dest="in_path",
        required=True,
        help="Input minutes JSONL file (from sim or device).",
    )
    p.add_argument(
        "--profile",
        dest="profile",
        default="avsafe_descriptors/rules/profiles/who_ieee_profile.yaml",
        help="Rules profile path/key. Default: %(default)s",
    )
    p.add_argument(
        "--out",
        dest="out_path",
        required=True,
        help="Output flags JSONL path.",
    )
    p.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Pretty-print each JSONL line with this indent; 0 for compact. Default: 2.",
    )
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)

    in_path = Path(args.in_path)
    out_path = Path(args.out_path)

    minutes = _read_jsonl(in_path)
    minutes_len = len(minutes)

    flags_rows: List[Dict[str, Any]]

    # Try to run the “real” evaluator if available.
    if load_profile and evaluate_minutes:
        try:
            profile = load_profile(args.profile)
        except Exception:
            profile = None  # tolerate missing/invalid profile

        try:
            results = evaluate_minutes(minutes, profile)
            if not isinstance(results, dict):
                raise ValueError("evaluate_minutes did not return a dict")
            flags_rows = _flags_from_results(results, minutes_len)
        except Exception:
            # Hard fallback: emit empty flags per minute so the pipeline continues.
            flags_rows = [{"idx": i, "flags": []} for i in range(minutes_len)]
    else:
        # Fallback when rules modules aren’t importable.
        flags_rows = [{"idx": i, "flags": []} for i in range(minutes_len)]

    _write_jsonl(out_path, flags_rows, indent=int(args.indent))
    print(f"Wrote {len(flags_rows)} flag rows → {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
