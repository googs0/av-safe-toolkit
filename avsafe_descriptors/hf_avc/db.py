from __future__ import annotations
import sqlite3, json, os
from typing import Dict, Any

DEFAULT_DB = os.environ.get("HFAVC_DB", "hf_avc_corpus.db")

SCHEMA = [
    "CREATE TABLE IF NOT EXISTS cases (id TEXT PRIMARY KEY, title TEXT, country TEXT, period TEXT, modalities TEXT, description TEXT, reported_effects TEXT, descriptors_json TEXT, legal_ethics_json TEXT);",
    "CREATE TABLE IF NOT EXISTS sources (id TEXT PRIMARY KEY, title TEXT, year INTEGER, url TEXT, publisher TEXT, doc_type TEXT, provenance TEXT);",
    "CREATE TABLE IF NOT EXISTS case_sources (case_id TEXT, source_id TEXT, PRIMARY KEY (case_id, source_id), FOREIGN KEY(case_id) REFERENCES cases(id) ON DELETE CASCADE, FOREIGN KEY(source_id) REFERENCES sources(id) ON DELETE CASCADE);"
]

def get_conn(db_path: str = DEFAULT_DB):
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys=ON;')
    return conn

def init_db(db_path: str = DEFAULT_DB):
    conn = get_conn(db_path); cur = conn.cursor()
    for stmt in SCHEMA: cur.execute(stmt)
    conn.commit(); conn.close()

def upsert_case(conn, case: Dict[str, Any]):
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO cases(id,title,country,period,modalities,description,reported_effects,descriptors_json,legal_ethics_json)
             VALUES (?,?,?,?,?,?,?,?,?)
             ON CONFLICT(id) DO UPDATE SET title=excluded.title,country=excluded.country,period=excluded.period,modalities=excluded.modalities,description=excluded.description,reported_effects=excluded.reported_effects,descriptors_json=excluded.descriptors_json,legal_ethics_json=excluded.legal_ethics_json""",
        (case['id'], case['title'], case.get('country'), case.get('period'), json.dumps(case.get('modalities', [])), case.get('description',''), json.dumps(case.get('reported_effects', [])), json.dumps(case.get('descriptors', {})), json.dumps(case.get('legal_ethics', {})))
    )

def upsert_source(conn, src: Dict[str, Any]):
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO sources(id,title,year,url,publisher,doc_type,provenance)
             VALUES (?,?,?,?,?,?,?)
             ON CONFLICT(id) DO UPDATE SET title=excluded.title,year=excluded.year,url=excluded.url,publisher=excluded.publisher,doc_type=excluded.doc_type,provenance=excluded.provenance""", 
        (src['id'], src['title'], src.get('year'), src.get('url'), src.get('publisher'), src.get('doc_type'), src.get('provenance'))
    )

def link_case_source(conn, case_id: str, source_id: str):
    conn.execute("INSERT OR IGNORE INTO case_sources(case_id, source_id) VALUES (?,?)", (case_id, source_id))

def ingest_case(conn, case: Dict[str, Any]):
    upsert_case(conn, case)
    for src in case.get('sources', []):
        upsert_source(conn, src); link_case_source(conn, case['id'], src['id'])
