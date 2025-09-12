#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Query CLI for the HF-AVC corpus SQLite database.

Features:
- list: tabular listing with filters (country, period overlap, modalities, context, WHO flag, full-text-ish match)
- export: write CSV or JSON with selected columns
- show/get: show a single row (flattened columns) or the raw JSON document
- stats: quick counts by country, modality, WHO exceedance
- sql: (advanced) run read-only SELECT statements (guarded)

Usage examples:
  python -m hf_avc.query_cli list --db hf_avc_corpus.db --country US --modalities audio
  python -m hf_avc.query_cli list --period 1993-01:1993-04 --search "loudspeaker"
  python -m hf_avc.query_cli export --format csv --out cases.csv --columns id,title,country_iso2,period_start,period_end
  python -m hf_avc.query_cli show --id case:waco_1993
  python -m hf_avc.query_cli get --id case:waco_1993 --raw
  python -m hf_avc.query_cli stats
  python -m hf_avc.query_cli sql "SELECT id,title FROM hf_cases LIMIT 5;"
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Row


# ----------------------------
# Engine & helpers
# ----------------------------

DEFAULT_DB = "hf_avc_corpus.db"

SELECTABLE_COLUMNS = [
    "id", "title", "country_iso2", "place",
    "period_start", "period_end",
    "modalities", "coercion_context",
    "summary", "reported_effects",
    "laeq_min", "laeq_max", "laeq_conf",
    "tlm_freq_min", "tlm_freq_max",
    "tlm_mod_min", "tlm_mod_max",
    "flicker_index_min", "flicker_index_max",
    "who_night_guideline_db", "who_likely_exceeded",
    "schema_version", "ingested_at",
]

def get_engine(db_path: Path) -> Engine:
    if not db_path.exists():
        print(f"Error: DB not found: {db_path}", file=sys.stderr)
        sys.exit(2)
    eng = create_engine(f"sqlite:///{db_path}")
    return eng


def comma_list(s: Optional[str]) -> List[str]:
    if not s:
        return []
    return [x.strip() for x in s.split(",") if x.strip()]


def normalize_period_token(tok: str) -> str:
    """
    Accept 'YYYY' or 'YYYY-MM' or 'YYYY-MM-DD'. Return as-is if valid-ish.
    We rely on lexicographic comparisons in SQLite (strings), so pad month/day.
    """
    tok = tok.strip()
    if re.fullmatch(r"\d{4}$", tok):
        return tok  # '1993'
    if re.fullmatch(r"\d{4}-\d{2}$", tok):
        return tok  # '1993-04'
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}$", tok):
        return tok  # '1993-04-12'
    raise argparse.ArgumentTypeError(f"Invalid period token: '{tok}' (expected YYYY or YYYY-MM or YYYY-MM-DD)")


def parse_period_range(s: str) -> Tuple[str, str]:
    """
    Parse 'START:END' where each side is YYYY, YYYY-MM, or YYYY-MM-DD.
    """
    try:
        start, end = s.split(":", 1)
    except ValueError:
        raise argparse.ArgumentTypeError("Period must be 'START:END' (e.g., 1993-01:1993-04)")
    return normalize_period_token(start), normalize_period_token(end)


def build_where_and_params(
    country: Optional[str],
    modalities: List[str],
    context: List[str],
    period: Optional[Tuple[str, str]],
    search: Optional[str],
    who_exceeded: Optional[bool],
) -> Tuple[str, Dict[str, Any]]:
    """
    Build a WHERE clause string and bound parameters for SQLite.
    """
    where = []
    params: Dict[str, Any] = {}

    if country:
        where.append("LOWER(country_iso2) = LOWER(:country)")
        params["country"] = country

    # Comma-separated storage: guard with delimiters for exact token match
    def delimited_contains(col: str, token_param: str) -> str:
        return f"((',' || LOWER({col}) || ',') LIKE '%,' || LOWER(:{token_param}) || ',%')"

    for i, m in enumerate(modalities):
        key = f"mod{i}"
        where.append(delimited_contains("modalities", key))
        params[key] = m

    for i, c in enumerate(context):
        key = f"ctx{i}"
        where.append(delimited_contains("coercion_context", key))
        params[key] = c

    if period:
        start, end = period
        # Overlap test: case_end >= q_start AND case_start <= q_end
        where.append("(COALESCE(period_end, period_start) >= :q_start AND COALESCE(period_start, period_end) <= :q_end)")
        params["q_start"] = start
        params["q_end"] = end

    if search:
        # Basic LIKE match across a few columns
        where.append("(LOWER(title) LIKE :q OR LOWER(summary) LIKE :q OR LOWER(place) LIKE :q)")
        params["q"] = f"%{search.lower()}%"

    if who_exceeded is not None:
        where.append("who_likely_exceeded = :who_flag")
        params["who_flag"] = 1 if who_exceeded else 0

    if not where:
        return "", {}

    return "WHERE " + " AND ".join(where), params


def run_select(
    eng: Engine,
    columns: Sequence[str],
    where_sql: str,
    params: Dict[str, Any],
    order: str = "id",
    limit: Optional[int] = None,
) -> List[Row]:
    cols_sql = ", ".join(columns)
    sql = f"SELECT {cols_sql} FROM hf_cases {where_sql} ORDER BY {order}"
    if limit:
        sql += " LIMIT :_limit"
        params = dict(params or {})
        params["_limit"] = limit
    with eng.begin() as cx:
        res = cx.execute(text(sql), params)
        return list(res.fetchall())


def print_table(rows: List[Row], columns: Sequence[str]) -> None:
    # Simple fixed-width table to stdout
    if not rows:
        print("(no rows)")
        return
    widths = [max(len(col), *(len(str(r[i])) if r[i] is not None else 0 for r in rows)) for i, col in enumerate(columns)]
    fmt = " | ".join("{:" + str(w) + "}" for w in widths)
    sep = "-+-".join("-" * w for w in widths)
    print(fmt.format(*columns))
    print(sep)
    for r in rows:
        print(fmt.format(*(("" if r[i] is None else str(r[i])) for i in range(len(columns)))))


# ----------------------------
# Subcommands
# ----------------------------

def cmd_list(args: argparse.Namespace) -> None:
    eng = get_engine(Path(args.db))

    cols = SELECTABLE_COLUMNS if args.columns is None else [c.strip() for c in args.columns.split(",") if c.strip()]
    unknown = [c for c in cols if c not in SELECTABLE_COLUMNS]
    if unknown:
        print(f"Unknown columns: {', '.join(unknown)}", file=sys.stderr)
        sys.exit(2)

    where, params = build_where_and_params(
        country=args.country,
        modalities=comma_list(args.modalities),
        context=comma_list(args.context),
        period=parse_period_range(args.period) if args.period else None,
        search=args.search,
        who_exceeded=args.who_exceeded,
    )
    rows = run_select(eng, cols, where, params, order=args.order, limit=args.limit)
    print_table(rows, cols)


def cmd_export(args: argparse.Namespace) -> None:
    eng = get_engine(Path(args.db))

    cols = SELECTABLE_COLUMNS if args.columns is None else [c.strip() for c in args.columns.split(",") if c.strip()]
    unknown = [c for c in cols if c not in SELECTABLE_COLUMNS]
    if unknown:
        print(f"Unknown columns: {', '.join(unknown)}", file=sys.stderr)
        sys.exit(2)

    where, params = build_where_and_params(
        country=args.country,
        modalities=comma_list(args.modalities),
        context=comma_list(args.context),
        period=parse_period_range(args.period) if args.period else None,
        search=args.search,
        who_exceeded=args.who_exceeded,
    )
    rows = run_select(eng, cols, where, params, order=args.order, limit=args.limit)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "csv":
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            for r in rows:
                w.writerow([r[i] for i in range(len(cols))])
        print(f"Wrote {len(rows)} row(s) to {out}")
    else:
        # JSON array of objects
        objs = [{col: r[i] for i, col in enumerate(cols)} for r in rows]
        with out.open("w", encoding="utf-8") as f:
            json.dump(objs, f, ensure_ascii=False, indent=2)
        print(f"Wrote {len(rows)} row(s) to {out}")


def cmd_show(args: argparse.Namespace) -> None:
    eng = get_engine(Path(args.db))
    cols = SELECTABLE_COLUMNS
    with eng.begin() as cx:
        row = cx.execute(text("SELECT " + ", ".join(cols) + " FROM hf_cases WHERE id = :id"), {"id": args.id}).fetchone()
    if not row:
        print(f"No such id: {args.id}", file=sys.stderr)
        sys.exit(1)
    # pretty print columns
    maxw = max(len(c) for c in cols)
    for i, col in enumerate(cols):
        val = row[i]
        print(f"{col.rjust(maxw)} : {'' if val is None else val}")


def cmd_get(args: argparse.Namespace) -> None:
    eng = get_engine(Path(args.db))
    with eng.begin() as cx:
        if args.raw:
            sql = "SELECT raw_json FROM hf_cases WHERE id = :id"
            row = cx.execute(text(sql), {"id": args.id}).fetchone()
            if not row:
                print(f"No such id: {args.id}", file=sys.stderr)
                sys.exit(1)
            obj = json.loads(row[0])
            print(json.dumps(obj, ensure_ascii=False, indent=2))
        else:
            row = cx.execute(text("SELECT * FROM hf_cases WHERE id = :id"), {"id": args.id}).fetchone()
            if not row:
                print(f"No such id: {args.id}", file=sys.stderr)
                sys.exit(1)
            # print the dict form
            keys = row.keys()
            print(json.dumps({k: row[k] for k in keys}, ensure_ascii=False, indent=2))


def cmd_stats(args: argparse.Namespace) -> None:
    eng = get_engine(Path(args.db))
    with eng.begin() as cx:
        total = cx.execute(text("SELECT COUNT(*) FROM hf_cases")).scalar_one()
        by_country = cx.execute(text("""
            SELECT COALESCE(country_iso2, '??') AS country, COUNT(*) AS n
            FROM hf_cases GROUP BY country ORDER BY n DESC, country
        """))
        by_who = cx.execute(text("""
            SELECT COALESCE(who_likely_exceeded, -1) AS flag, COUNT(*) AS n
            FROM hf_cases GROUP BY flag ORDER BY flag DESC
        """))
        # explode modalities: we store CSV; count tokens
        rows = cx.execute(text("SELECT modalities FROM hf_cases WHERE modalities IS NOT NULL")).fetchall()

    mod_counts: Dict[str, int] = {}
    for (mods,) in rows:
        for m in comma_list(mods.lower()):
            mod_counts[m] = mod_counts.get(m, 0) + 1

    print(f"Total cases: {total}")
    print("\nBy country:")
    for r in by_country:
        print(f"  {r.country}: {r.n}")
    print("\nBy WHO likely exceeded (1=yes, 0=no, -1=unknown):")
    for r in by_who:
        print(f"  {r.flag}: {r.n}")
    print("\nBy modality (approx):")
    for m, n in sorted(mod_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {m}: {n}")


def cmd_sql(args: argparse.Namespace) -> None:
    q = args.query.strip().lower()
    if not q.startswith("select"):
        print("Only read-only SELECT statements are allowed.", file=sys.stderr)
        sys.exit(2)
    eng = get_engine(Path(args.db))
    with eng.begin() as cx:
        res = cx.execute(text(args.query))
        rows = res.fetchall()
        cols = res.keys()
    print_table(rows, cols)


# ----------------------------
# CLI
# ----------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Query HF-AVC SQLite corpus.")
    ap.add_argument("--db", default=DEFAULT_DB, help="Path to SQLite DB (default: hf_avc_corpus.db)")

    sub = ap.add_subparsers(dest="cmd", required=True)

    # list
    ap_list = sub.add_parser("list", help="List cases with filters")
    ap_list.add_argument("--columns", help="Comma-separated columns to show")
    ap_list.add_argument("--country", help="ISO-3166 alpha-2 (e.g., US)")
    ap_list.add_argument("--modalities", help="Comma-separated (e.g., audio,light)")
    ap_list.add_argument("--context", help="Comma-separated coercion contexts (e.g., siege,detention)")
    ap_list.add_argument("--period", help="Period overlap 'START:END' (YYYY or YYYY-MM or YYYY-MM-DD)")
    ap_list.add_argument("--search", help="Substring match in title/summary/place")
    ap_list.add_argument("--who-exceeded", action="store_true", help="Filter cases where WHO night likely exceeded")
    ap_list.add_argument("--order", default="id", help="Order by column (default: id)")
    ap_list.add_argument("--limit", type=int, help="Limit rows")
    ap_list.set_defaults(func=cmd_list)

    # export
    ap_exp = sub.add_parser("export", help="Export cases to CSV or JSON")
    ap_exp.add_argument("--format", choices=["csv", "json"], default="csv")
    ap_exp.add_argument("--out", required=True, help="Output path")
    ap_exp.add_argument("--columns", help="Comma-separated columns to include")
    ap_exp.add_argument("--country", help="ISO-3166 alpha-2")
    ap_exp.add_argument("--modalities", help="Comma-separated (e.g., audio,light)")
    ap_exp.add_argument("--context", help="Comma-separated coercion contexts")
    ap_exp.add_argument("--period", help="Period overlap 'START:END'")
    ap_exp.add_argument("--search", help="Substring match in title/summary/place")
    ap_exp.add_argument("--who-exceeded", action="store_true", help="Filter WHO night likely exceeded")
    ap_exp.add_argument("--order", default="id", help="Order by column")
    ap_exp.add_argument("--limit", type=int, help="Limit rows")
    ap_exp.set_defaults(func=cmd_export)

    # show
    ap_show = sub.add_parser("show", help="Show a single case (flattened)")
    ap_show.add_argument("--id", required=True, help="Case id")
    ap_show.set_defaults(func=cmd_show)

    # get
    ap_get = sub.add_parser("get", help="Get a single case JSON (raw or row)")
    ap_get.add_argument("--id", required=True)
    ap_get.add_argument("--raw", action="store_true", help="Print raw_json instead of flat row")
    ap_get.set_defaults(func=cmd_get)

    # stats
    ap_stats = sub.add_parser("stats", help="Summary counts")
    ap_stats.set_defaults(func=cmd_stats)

    # sql
    ap_sql = sub.add_parser("sql", help="Run a read-only SELECT (advanced)")
    ap_sql.add_argument("query", help="SELECT ...")
    ap_sql.set_defaults(func=cmd_sql)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
