from avsafe_descriptors.integrity.integrity import canonical_json, sha256_hex, generate_keypair, sign_payload, verify_signature

def test_hash_stability():
    a = {"a":1,"b":None,"c":2}; b = {"c":2,"a":1,"b":None}
    assert sha256_hex(a) == sha256_hex(b)

def test_sign_verify():
    try:
        kp = generate_keypair()
    except RuntimeError:
        return
    payload = {"x":1,"y":"z"}; sig = sign_payload(payload, kp["private_key_hex"])
    assert verify_signature(payload, sig, kp["public_key_hex"])
