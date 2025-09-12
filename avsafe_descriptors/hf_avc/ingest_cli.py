#!/usr/bin/env python3
from __future__ import annotations
"""
Ingest HF-AVC case JSON files into a SQLite corpus DB.

- Validates against hf_avc/schemas/case_schema_v1.json (can be disabled).
- Supports v2 case structure; maps legacy v1 fields when encountered.
- Normalizes key fields into columns; stores full raw JSON and a content hash.
- Idempotent: if the content hash hasn't changed, the row is skipped.
"""

import argparse, json, hashlib, sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

# Optional: JSON Schema validation
try:
    from jsonschema import Draft202012Validator
    HAVE_JSONSCHEMA = True
except Exception:
    HAVE_JSONSCHEMA = False


# ------------------------
# Utility functions
# ------------------------

def canonical_json(obj: Any) -> str:
    """Stable JSON string (sorted keys, UTF-8, no extra whitespace)."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_schema(schema_path: Path):
    if not HAVE_JSONSCHEMA:
        return None
    schema = load_json(schema_path)
    return Draft202012Validator(schema)


def validate_case(validator, obj: Dict[str, Any], file: Path) -> None:
    """Raises jsonschema.ValidationError on failure."""
    if validator is None:
        return
    validator.validate(obj)


# ------------------------
# SQLite schema & engine
# ------------------------

DDL = """
CREATE TABLE IF NOT EXISTS hf_cases (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  country_iso2 TEXT,
  place TEXT,
  period_start TEXT,
  period_end TEXT,
  modalities TEXT,
  coercion_context TEXT,
  summary TEXT,
  reported_effects TEXT,
  laeq_min REAL,
  laeq_max REAL,
  laeq_conf REAL,
  tlm_freq_min REAL,
  tlm_freq_max REAL,
  tlm_mod_min REAL,
  tlm_mod_max REAL,
  flicker_index_min REAL,
  flicker_index_max REAL,
  who_night_guideline_db REAL,
  who_likely_exceeded INTEGER,
  schema_version TEXT,
  json_hash TEXT NOT NULL,
  raw_json TEXT NOT NULL,
  ingested_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_hf_cases_country ON hf_cases(country_iso2);
CREATE INDEX IF NOT EXISTS idx_hf_cases_period_start ON hf_cases(period_start);
CREATE INDEX IF NOT EXISTS idx_hf_cases_modalities ON hf_cases(modalities);
"""

UPSERT = """
INSERT INTO hf_cases (
  id, title, country_iso2, place, period_start, period_end,
  modalities, coercion_context, summary, reported_effects,
  laeq_min, laeq_max, laeq_conf,
  tlm_freq_min, tlm_freq_max, tlm_mod_min, tlm_mod_max,
  flicker_index_min, flicker_index_max,
  who_night_guideline_db, who_likely_exceeded,
  schema_version, json_hash, raw_json
)
VALUES (
  :id, :title, :country_iso2, :place, :period_start, :period_end,
  :modalities, :coercion_context, :summary, :reported_effects,
  :laeq_min, :laeq_max, :laeq_conf,
  :tlm_freq_min, :tlm_freq_max, :tlm_mod_min, :tlm_mod_max,
  :flicker_index_min, :flicker_index_max,
  :who_night_guideline_db, :who_likely_exceeded,
  :schema_version, :json_hash, :raw_json
)
ON CONFLICT(id) DO UPDATE SET
  title=excluded.title,
  country_iso2=excluded.country_iso2,
  place=excluded.place,
  period_start=excluded.period_start,
  period_end=excluded.period_end,
  modalities=excluded.modalities,
  coercion_context=excluded.coercion_context,
  summary=excluded.summary,
  reported_effects=excluded.reported_effects,
  laeq_min=excluded.laeq_min,
  laeq_max=excluded.laeq_max,
  laeq_conf=excluded.laeq_conf,
  tlm_freq_min=excluded.tlm_freq_min,
  tlm_freq_max=excluded.tlm_freq_max,
  tlm_mod_min=excluded.tlm_mod_min,
  tlm_mod_max=excluded.tlm_mod_max,
  flicker_index_min=excluded.flicker_index_min,
  flicker_index_max=excluded.flicker_index_max,
  who_night_guideline_db=excluded.who_night_guideline_db,
  who_likely_exceeded=excluded.who_likely_exceeded,
  schema_version=excluded.schema_version,
  json_hash=excluded.json_hash,
  raw_json=excluded.raw_json,
  ingested_at=CURRENT_TIMESTAMP
WHERE hf_cases.json_hash IS DISTINCT FROM excluded.json_hash;
"""


def get_engine(db_path: Path) -> Engine:
    eng = create_engine(f"sqlite:///{db_path}")
    # Initialize WAL & schema
    with eng.begin() as cx:
        cx.execute(text("PRAGMA journal_mode=WAL"))
        for stmt in DDL.strip().split(";\n\n"):
            if stmt.strip():
                cx.execute(text(stmt))
    return eng


# ------------------------
# Mapping (v2 + legacy)
# ------------------------

def _get(obj: Dict[str, Any], path: Iterable[str], default=None):
    cur = obj
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def _parse_range_metric(metric: Any) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Accepts either:
      {"range":{"min":..,"max":..},"confidence":..}
      {"value": .., "confidence": ..}
      number
      or None
    Returns (min, max, confidence)
    """
    if metric is None:
        return (None, None, None)
    if isinstance(metric, (int, float)):
        v = float(metric)
        return (v, v, None)
    if isinstance(metric, dict):
        conf = metric.get("confidence")
        if "range" in metric and isinstance(metric["range"], dict):
            r = metric["range"]
            return (r.get("min"), r.get("max"), conf)
        if "value" in metric:
            v = metric["value"]
            return (v, v, conf)
    return (None, None, None)


def map_case(obj: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map a v2 case JSON (and tolerate legacy v1) into a flat row dict for SQLite.
    """
    # Detect legacy structure (very simple heuristic)
    legacy = "jurisdiction" not in obj and "summary" not in obj

    if legacy:
        # Minimal legacy mapping fallback
        country_iso2 = obj.get("country") or None
        place = None
        period_start = obj.get("period") or None
        period_end = obj.get("period") or None
        modalities = ",".join(obj.get("modalities", []))
        coercion_context = None
        summary = obj.get("description") or None
        reported_effects = ",".join(obj.get("reported_effects", []))
        laeq_min = laeq_max = laeq_conf = None
        tlm_f_min = tlm_f_max = tlm_mod_min = tlm_mod_max = None
        flicker_index_min = flicker_index_max = None
        who_night = None
        who_likely = None
        schema_version = obj.get("schema_version") or "legacy"
    else:
        country_iso2 = _get(obj, ["jurisdiction", "country_iso2"])
        place = _get(obj, ["jurisdiction", "place"])
        period_start = _get(obj, ["period", "start"])
        period_end = _get(obj, ["period", "end"])
        modalities = ",".join(obj.get("modalities", []))
        coercion_context = ",".join(obj.get("coercion_context", []))
        summary = obj.get("summary")
        reported_effects = ",".join(obj.get("reported_effects", []))

        # Audio LAeq
        laeq_min, laeq_max, laeq_conf = _parse_range_metric(_get(obj, ["descriptors", "audio", "laeq_db"]))
        # Light TLM metrics
        tlm_f_min, tlm_f_max, _ = _parse_range_metric(_get(obj, ["descriptors", "light", "tlm_freq_hz"]))
        tlm_mod_min, tlm_mod_max, _ = _parse_range_metric(_get(obj, ["descriptors", "light", "tlm_mod_percent"]))
        fi_min, fi_max, _ = _parse_range_metric(_get(obj, ["descriptors", "light", "flicker_index"]))
        flicker_index_min, flicker_index_max = fi_min, fi_max

        who_night = _get(obj, ["standards_mapping", "who_noise_2018", "night_guideline_db"])
        who_likely = _get(obj, ["standards_mapping", "who_noise_2018", "likely_exceeded"])
        schema_version = obj.get("schema_version") or "1.0.0"

    return {
        "id": obj.get("id"),
        "title": obj.get("title"),

        "country_iso2": country_iso2,
        "place": place,
        "period_start": period_start,
        "period_end": period_end,
        "modalities": modalities or None,
        "coercion_context": coercion_context or None,
        "summary": summary,
        "reported_effects": reported_effects or None,

        "laeq_min": laeq_min, "laeq_max": laeq_max, "laeq_conf": laeq_conf,
        "tlm_freq_min": tlm_f_min, "tlm_freq_max": tlm_f_max,
        "tlm_mod_min": tlm_mod_min, "tlm_mod_max": tlm_mod_max,
        "flicker_index_min": flicker_index_min, "flicker_index_max": flicker_index_max,

        "who_night_guideline_db": who_night,
        "who_likely_exceeded": int(bool(who_likely)) if who_likely is not None else None,

        "schema_version": schema_version,
    }


# ------------------------
# Ingest
# ------------------------

def ingest_files(
    db_path: Path,
    case_paths: Iterable[Path],
    schema_path: Optional[Path],
    strict: bool = False,
    dry_run: bool = False,
) -> Tuple[int, int, int]:
    """
    Returns (ok_count, updated_count, skipped_same_hash_count).
    """
    eng = get_engine(db_path)
    validator = load_schema(schema_path) if (schema_path and schema_path.exists()) else None

    ok = updated = same = 0

    with eng.begin() as cx:
        for p in case_paths:
            try:
                obj = load_json(p)
                # Validate (if schema present)
                validate_case(validator, obj, p)

                raw = canonical_json(obj)
                h = sha256_hex(raw)
                row = map_case(obj)
                row["json_hash"] = h
                row["raw_json"] = raw

                if dry_run:
                    print(f"[DRY] Would ingest {p} -> id={row['id']}")
                    ok += 1
                    continue

                # If row exists with same hash, skip
                existing = cx.execute(text("SELECT json_hash FROM hf_cases WHERE id = :id"), {"id": row["id"]}).fetchone()
                if existing and existing[0] == h:
                    same += 1
                    print(f"[SKIP] {p} unchanged (same hash)")
                    continue

                cx.execute(text(UPSERT), row)
                if existing:
                    updated += 1
                    print(f"[UPD ] {p} -> id={row['id']}")
                else:
                    ok += 1
                    print(f"[OK  ] {p} -> id={row['id']}")

            except Exception as e:
                msg = f"[FAIL] {p}: {e}"
                if strict:
                    raise RuntimeError(msg) from e
                print(msg, file=sys.stderr)

    return ok, updated, same


# ------------------------
# CLI
# ------------------------

def iter_globs(globs: Iterable[str]) -> Iterable[Path]:
    for g in globs:
        # Support both file and glob
        for p in Path().glob(g):
            if p.is_file() and p.suffix.lower() == ".json":
                yield p


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest HF-AVC case JSON into SQLite.")
    ap.add_argument("--db", default="hf_avc_corpus.db", help="SQLite DB path (will be created).")
    ap.add_argument("--cases", nargs="+", default=["hf_avc/cases/*.json"], help="Glob(s) to JSON case files.")
    ap.add_argument("--schema", default="hf_avc/schemas/case_schema_v1.json", help="JSON Schema path.")
    ap.add_argument("--no-validate", action="store_true", help="Skip JSON Schema validation.")
    ap.add_argument("--strict", action="store_true", help="Fail immediately on first error.")
    ap.add_argument("--dry-run", action="store_true", help="Parse/validate only; no DB writes.")
    args = ap.parse_args()

    db_path = Path(args.db)
    case_paths = list(iter_globs(args.cases))
    if not case_paths:
        print("No case files matched the provided globs.", file=sys.stderr)
        sys.exit(2)

    schema_path = None if args.no_validate else Path(args.schema)

    ok, upd, same = ingest_files(db_path, case_paths, schema_path, strict=args.strict, dry_run=args.dry_run)
    print(f"\nSummary: inserted={ok}, updated={upd}, unchanged={same}, total_seen={ok+upd+same}")


if __name__ == "__main__":
    main()
