"""
Auth guard for FastAPI:

- DEV mode: static bearer token (no infra).
- JWT mode: validate OAuth/OIDC JWTs using JWKS (Cognito/Google/etc).
"""

import os, time
from typing import Optional, Dict, Any
from jose import jwt
import requests

AUTH_MODE = os.environ.get("AUTH_MODE", "dev").lower()   # "dev" | "jwt"
DEV_TOKEN = os.environ.get("DEV_TOKEN", "")              # used in dev mode (if blank, allow anonymous)

JWKS_URL      = os.environ.get("JWKS_URL", "")
JWKS_AUDIENCE = os.environ.get("JWKS_AUDIENCE", "")
JWKS_ISSUER   = os.environ.get("JWKS_ISSUER", "")

_jwks_cache: Dict[str, Any] = {}
_jwks_exp = 0.0

def _bearer(h: Optional[str]) -> Optional[str]:
    if not h: return None
    p = h.split()
    return p[1] if len(p)==2 and p[0].lower()=="bearer" else None

def _load_jwks() -> Dict[str, Any]:
    global _jwks_cache, _jwks_exp
    now = time.time()
    if _jwks_cache and now < _jwks_exp: return _jwks_cache
    if not JWKS_URL: raise RuntimeError("JWT mode but JWKS_URL unset")
    r = requests.get(JWKS_URL, timeout=5); r.raise_for_status()
    _jwks_cache, _jwks_exp = r.json(), now + 3600
    return _jwks_cache

def require(headers: Dict[str,str]) -> Dict[str,Any]:
    tok = _bearer(headers.get("authorization") or headers.get("Authorization"))
    if AUTH_MODE == "dev":
        if not DEV_TOKEN:
            return {"sub":"anonymous","mode":"dev"}
        if tok == DEV_TOKEN:
            return {"sub":"dev-user","mode":"dev"}
        raise RuntimeError("Unauthorized (dev token mismatch)")
    if AUTH_MODE == "jwt":
        if not tok: raise RuntimeError("Unauthorized (no bearer token)")
        jwks = _load_jwks()
        unv = jwt.get_unverified_header(tok)
        kid = unv.get("kid"); key = next((k for k in jwks.get("keys",[]) if k.get("kid")==kid), None)
        if not key: raise RuntimeError("JWT key not found in JWKS")
        opts = {"verify_aud": bool(JWKS_AUDIENCE)}
        claims = jwt.decode(tok, key, algorithms=[unv.get("alg","RS256")],
                            audience=JWKS_AUDIENCE or None, issuer=JWKS_ISSUER or None, options=opts)
        claims["mode"]="jwt"; return claims
    raise RuntimeError("Unknown AUTH_MODE")
