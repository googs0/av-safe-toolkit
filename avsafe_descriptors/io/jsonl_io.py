
from __future__ import annotations
import json
from typing import Iterable, Dict, Iterator

def write_jsonl(path: str, records: Iterable[dict]) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

def read_jsonl(path: str) -> Iterator[dict]:
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                yield json.loads(line)
