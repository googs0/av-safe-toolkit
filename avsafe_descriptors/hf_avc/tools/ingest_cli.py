from __future__ import annotations
import argparse, json, glob, os
from pydantic import ValidationError
from avsafe_descriptors.hf_avc.models import Case
from avsafe_descriptors.hf_avc.db import init_db, get_conn, ingest_case

def main():
    ap = argparse.ArgumentParser(description="Ingest HF‑AVC case JSON files into SQLite corpus DB")
    ap.add_argument("--cases", required=True, help="Glob for case JSON files, e.g., data/cases/*.json")
    ap.add_argument("--db", default=None, help="Path to corpus DB (default hf_avc_corpus.db)")
    args = ap.parse_args()

    if args.db: os.environ["HFAVC_DB"] = args.db
    init_db(); conn = get_conn()

    n_ok, n_err = 0, 0
    for path in glob.glob(args.cases):
        try:
            data = json.load(open(path)); case = Case.model_validate(data)
            ingest_case(conn, case.model_dump()); n_ok += 1
        except ValidationError as e:
            print(f"[INVALID] {path}: {e}"); n_err += 1
        except Exception as e:
            print(f"[ERROR] {path}: {e}"); n_err += 1
    conn.commit(); conn.close()
    print(f"Ingested {n_ok} case(s); {n_err} error(s).")

if __name__ == "__main__":
    main()
