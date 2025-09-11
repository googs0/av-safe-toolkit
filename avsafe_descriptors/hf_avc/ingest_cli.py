
from __future__ import annotations
import argparse, json, glob
from sqlalchemy import create_engine, text
from .models import Case

def ensure_schema(db_path: str):
    eng = create_engine(f"sqlite:///{db_path}")
    with eng.begin() as cx:
        cx.execute(text('PRAGMA journal_mode=WAL'))
        cx.execute(text('''CREATE TABLE IF NOT EXISTS hf_cases (
            id TEXT PRIMARY KEY,
            title TEXT,
            country TEXT,
            period TEXT,
            modalities TEXT,
            description TEXT,
            reported_effects TEXT,
            descriptors JSON,
            legal_ethics JSON,
            sources JSON
        )'''))

def ingest_files(db_path: str, patterns: list[str]) -> int:
    eng = create_engine(f"sqlite:///{db_path}")
    count = 0
    with eng.begin() as cx:
        for pat in patterns:
            for path in glob.glob(pat):
                obj = json.load(open(path, 'r', encoding='utf-8'))
                case = Case(**obj)
                cx.execute(text('''
                    INSERT OR REPLACE INTO hf_cases
                    (id,title,country,period,modalities,description,reported_effects,descriptors,legal_ethics,sources)
                    VALUES (:id,:title,:country,:period,:modalities,:description,:reported_effects,:descriptors,:legal_ethics,:sources)
                '''), dict(
                    id=case.id,
                    title=case.title,
                    country=case.country,
                    period=case.period,
                    modalities=",".join(case.modalities),
                    description=case.description,
                    reported_effects=",".join(case.reported_effects),
                    descriptors=json.dumps(case.descriptors.model_dump()),
                    legal_ethics=json.dumps(case.legal_ethics.model_dump()),
                    sources=json.dumps([s.model_dump() for s in case.sources])
                ))
                count += 1
    return count

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="hf_avc_corpus.db")
    ap.add_argument("--cases", nargs="+", required=True, help="Glob(s) to JSON case files")
    args = ap.parse_args()
    ensure_schema(args.db)
    n = ingest_files(args.db, args.cases)
    print(f"Ingested {n} case(s) into {args.db}")

if __name__ == "__main__":
    main()
