# Threat Model (MVP)
**Assets:** minute summaries, hash chain, signatures, report integrity.  
**Adversaries:** local tamper, spoofing uploads, weak time sync.  
**Mitigations:** hash chaining, signature verification, secure time source (RTC), WAL‑mode SQLite, audit logs.
**Out of scope (MVP):** strong hardware TEEs, remote attestation, coercive deployments (see Acceptable Use).
