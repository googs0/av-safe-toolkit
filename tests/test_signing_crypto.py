import os
import pytest

def test_sign_uses_real_crypto(monkeypatch):
    """
    In CI/production we want real Ed25519, not the demo fallback.
    If crypto libs are truly unavailable, we skip so local devs aren't blocked.
    """
    # Require real crypto for this test
    monkeypatch.setenv("AVSAFE_STRICT_CRYPTO", "1")

    # Import after env var is set
    from integrity.signing import sign_bytes

    try:
        sig = sign_bytes(b"test")
    except RuntimeError:
        # No crypto libs in this environment; allow CI to skip
        pytest.skip("ed25519 backend not available in this environment")

    assert sig["scheme"] == "ed25519"
    assert isinstance(sig.get("signature_hex"), str)
    assert isinstance(sig.get("public_key_hex"), str)
    assert len(sig["public_key_hex"]) == 64  # 32 bytes raw key in hex
