"""
Authentication guard for Lambda FastAPI:

- DEV mode: check a static bearer token (no infra needed).
- JWT mode: validate OAuth/OIDC JWTs using JWKS (Cognito/Google/etc).
"""

import os
import time
import json
from typing import Optional, Dict, Any
from jose import jwt
import requests

AUTH_MODE = os.environ.get("AUTH_MODE", "dev").lower()           # "dev" or "jwt"
DEV_TOKEN = os.environ.get("DEV_TOKEN", "")                      # static bearer token for dev mode

JWKS_URL = os.environ.get("JWKS_URL", "")                        # e.g., https://cognito-idp.<region>.amazonaws.com/<pool_id>/.well-known/jwks.json
JWKS_AUDIENCE = os.environ.get("JWKS_AUDIENCE", "")              # optional
JWKS_ISSUER = os.environ.get("JWKS_ISSUER", "")                  # optional

_jwks_cache: Dict[str, Any] = {}
_jwks_cache_exp: float = 0.0

def _load_jwks() -> Dict[str, Any]:
    global _jwks_cache, _jwks_cache_exp
    now = time.time()
    if _jwks_cache and now < _jwks_cache_exp:
        return _jwks_cache
    if not JWKS_URL:
        raise RuntimeError("JWT auth requested but JWKS_URL is not set")
    resp = requests.get(JWKS_URL, timeout=5)
    resp.raise_for_status()
    _jwks_cache = resp.json()
    _jwks_cache_exp = now + 3600  # 1 hour cache
    return _jwks_cache

def _extract_bearer(auth_header: Optional[str]) -> Optional[str]:
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None

def require(headers: Dict[str, str]) -> Dict[str, Any]:
    """
    Return a claims dict (possibly minimal) or raise RuntimeError on failure.
    """
    token = _extract_bearer(headers.get("authorization") or headers.get("Authorization"))
    if AUTH_MODE == "dev":
        if not DEV_TOKEN:
            # dev mode, no token required (not recommended); return anonymous claims
            return {"sub": "anonymous", "mode": "dev"}
        if token == DEV_TOKEN:
            return {"sub": "dev-user", "mode": "dev"}
        raise RuntimeError("Unauthorized (dev token mismatch)")
    elif AUTH_MODE == "jwt":
        if not token:
            raise RuntimeError("Unauthorized (no bearer token)")
        jwks = _load_jwks()
        try:
            unverified = jwt.get_unverified_header(token)
            kid = unverified.get("kid")
            key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
            if not key:
                raise RuntimeError("JWT key not found in JWKS")
            options = {"verify_aud": bool(JWKS_AUDIENCE)}
            claims = jwt.decode(
                token,
                key,
                algorithms=[unverified.get("alg", "RS256")],
                audience=JWKS_AUDIENCE or None,
                issuer=JWKS_ISSUER or None,
                options=options,
            )
            claims["mode"] = "jwt"
            return claims
        except Exception as e:
            raise RuntimeError(f"Unauthorized (bad JWT): {e}")
    else:
        raise RuntimeError("Server misconfigured: unknown AUTH_MODE")
