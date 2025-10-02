#!/usr/bin/env python3
"""
AV-SAFE: Run rules on minute summaries.

Reads minutes.jsonl, loads a WHO/IEEE profile, evaluates rules,
and writes per-minute flags to a JSONL file (default).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from avsafe_descriptors.rules.evaluator import evaluate_minutes
from avsafe_descriptors.rules.profile_loader import load_profile


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _write_json(path: Path, data: Any, indent: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        if indent and indent > 0:
            json.dump(data, f, ensure_ascii=False, indent=indent)
        else:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))


def _flatten_results_to_flags(
    results: Any,
) -> List[Dict[str, Any]]:
    """
    Normalize evaluator output into a per-minute list suitable for JSONL, e.g.:

    [{"idx": 0, "flags": [...]}, {"idx": 1, "flags": [...]}]
    """
    # Preferred shape: {"per_minute": [...], "summary": {...}, ...}
    if isinstance(results, dict) and "per_minute" in results:
        per_min = results["per_minute"]
        if isinstance(per_min, list):
            return per_min

    # If we get a list already, trust it's per-minute records
    if isinstance(results, list):
        return results

    # If we get a dict mapping idx -> flags, convert it
    if isinstance(results, dict):
        converted: List[Dict[str, Any]] = []
        for k, v in results.items():
            try:
                idx = int(k)
            except Exception:
                # Not an idx → flags mapping; give up gracefully
                break
            rec = {"idx": idx, "flags": v}
            converted.append(rec)
        if converted:
            converted.sort(key=lambda r: r["idx"])
            return converted

    # Fallback: return an empty list (better than raising)
    return []


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="avsafe-rules-run",
        description="Evaluate WHO/IEEE rules on AV-SAFE minute summaries.",
    )
    p.add_argument(
        "--in",
        dest="in_path",
        required=True,
        help="Path to minutes.jsonl",
    )
    p.add_argument(
        "--profile",
        default="avsafe_descriptors/rules/profiles/who_ieee_profile.yaml",
        help="Path to profile YAML (default: WHO/IEEE profile).",
    )
    p.add_argument(
        "--out",
        dest="out_path",
        required=True,
        help="Output path. Default format is JSONL (one record per line).",
    )
    p.add_argument(
        "--format",
        choices=["jsonl", "json"],
        default="jsonl",
        help="Output format (default: jsonl).",
    )
    p.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Pretty-print JSON when --format=json (0 for compact). Default: 2.",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    in_path = Path(args.in_path)
    if not in_path.exists():
        print(f"ERROR: input not found: {in_path}", file=sys.stderr)
        return 2

    # Load inputs
    minutes = _read_jsonl(in_path)
    profile = load_profile(args.profile)

    # Evaluate
    results = evaluate_minutes(minutes, profile)
    flags = _flatten_results_to_flags(results)

    # Write
    out_path = Path(args.out_path)
    if args.format == "jsonl":
        _write_jsonl(out_path, flags)
    else:
        payload: Dict[str, Any] = {"per_minute": flags, "profile_name": profile.get("name")}
        _write_json(out_path, payload, indent=args.indent)

    # Quiet success
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
