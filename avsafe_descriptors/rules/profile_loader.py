
from __future__ import annotations
import yaml, json
from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass
class RulesProfile:
    name: str
    noise: Dict[str, Any]
    flicker: Dict[str, Any]

def load_profile(path: str) -> RulesProfile:
    with open(path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)
    return RulesProfile(
        name=cfg.get("name","profile"),
        noise=cfg.get("noise",{}),
        flicker=cfg.get("flicker",{}),
    )
