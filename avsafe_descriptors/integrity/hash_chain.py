
from __future__ import annotations
import hashlib, json
from typing import Optional

def canonical_json(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def chain_hash(prev_hex: Optional[str], payload: dict) -> str:
    h = hashlib.sha256()
    if prev_hex:
        h.update(bytes.fromhex(prev_hex))
    h.update(canonical_json(payload).encode('utf-8'))
    return h.hexdigest()
