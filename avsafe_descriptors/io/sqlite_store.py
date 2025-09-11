
from __future__ import annotations
from sqlalchemy import create_engine, text
from typing import Iterable, Optional

def ensure_schema(db_path: str) -> None:
    eng = create_engine(f"sqlite:///{db_path}")
    with eng.begin() as cx:
        cx.execute(text('PRAGMA journal_mode=WAL'))
        cx.execute(text('''
        CREATE TABLE IF NOT EXISTS minutes (
            session TEXT,
            idx INTEGER,
            ts TEXT,
            laeq REAL,
            lcpeak REAL,
            tlm_freq_hz REAL,
            tlm_mod_percent REAL,
            flicker_index REAL,
            third_oct JSON,
            chain_hash TEXT,
            signature_hex TEXT,
            scheme TEXT,
            public_key_hex TEXT
        )'''))

def ingest(db_path: str, session: str, records: Iterable[dict]) -> int:
    eng = create_engine(f"sqlite:///{db_path}")
    rows = 0
    with eng.begin() as cx:
        for r in records:
            cx.execute(text('''INSERT INTO minutes
            (session, idx, ts, laeq, lcpeak, tlm_freq_hz, tlm_mod_percent, flicker_index, third_oct, chain_hash, signature_hex, scheme, public_key_hex)
            VALUES (:session, :idx, :ts, :laeq, :lcpeak, :tlm_freq_hz, :tlm_mod_percent, :flicker_index, :third_oct, :chain_hash, :signature_hex, :scheme, :public_key_hex)
            '''), dict(
                session=session,
                idx=r.get("idx"),
                ts=r.get("ts"),
                laeq=r.get("audio",{}).get("laeq_db"),
                lcpeak=r.get("audio",{}).get("lcpeak_db"),
                tlm_freq_hz=r.get("light",{}).get("tlm_freq_hz"),
                tlm_mod_percent=r.get("light",{}).get("tlm_mod_percent"),
                flicker_index=r.get("light",{}).get("flicker_index"),
                third_oct=json.dumps(r.get("audio",{}).get("third_octave_db", {})),
                chain_hash=r.get("chain",{}).get("hash"),
                signature_hex=r.get("chain",{}).get("signature_hex"),
                scheme=r.get("chain",{}).get("scheme"),
                public_key_hex=r.get("chain",{}).get("public_key_hex"),
            ))
            rows += 1
    return rows
