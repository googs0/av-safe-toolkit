# Privacy 

AV-SAFE is built to **measure environments without recording people**. It converts ambient audio/light into **privacy-preserving descriptors** (e.g., LAeq, 1/3-octaves, TLM frequency, modulation depth, flicker index) and produces **tamper-evident** reports. No raw speech, images, or video are retained or transmitted by design.

---

## What's here

This document describes how the open-source AV-SAFE receiver, CLI tools, and example workflows are intended to handle data **when configured as documented**. Deployers are responsible for using ethical, lawful configurations in their jurisdiction.

More information: [Acceptable Use](ACCEPTABLE_USE.md), [Security](SECURITY.md), [Threat Model](THREAT_MODEL.md), [API](api.md).

---

## What's processed (by design)

- **Minute summaries (JSONL):**  
  - Audio: `laeq_db`, `lcpeak_db`, optional `third_octave_db{band->dB}`  
  - Light: `tlm_freq_hz`, `tlm_mod_percent`, `flicker_index`  
  - Integrity: hash chain + optional Ed25519 signature metadata  
- **Session metadata:** pseudonymous `session_id`, ingest timestamps, evaluation profile ID.

**We do not process:** raw audio, raw video/imagery, or direct identifiers (PII).

---

## What isn't collected

- Raw microphone or camera recordings  
- Content that can re-identify individuals (names, emails, device IDs)  
- Location traces or precise geolocation unless you add them

> If a deployer modifies code to capture raw content, that is **out of scope** and violates `Acceptable Use`.

---

## On-Device & server behavior

- **On-device:** Sensors should compute descriptors locally and **discard raw signals immediately**.  
- **Transport:** Send only minute summaries (no raw content). Use TLS where applicable.  
- **Server storage:** Defaults to a local SQLite file at `AVSAFE_DB`.  
- **Logs:** Should be configured not to include payload bodies; only minimal operational metadata.

Configuration knobs:
- `AVSAFE_DB` — path to SQLite DB (e.g., `/data/avsafe.db`)  
- `AVSAFE_STRICT_CRYPTO=1` — require Ed25519 signatures; disable demo fallback  
- `AVSAFE_PRIV_HEX` — **local testing only** (never commit or share)

---

## Retention & minimization

- **Session TTL:** default **24 hours** (recommended).  
- **Reports & results:** keep only what’s necessary for auditing; avoid long-term storage unless policy requires it.  
- **Backups:** If you back up the DB, treat it as sensitive; it still contains descriptors and integrity data.

Suggested practice:
- Rotate/expire sessions on a schedule (e.g., daily).  
- Purge old DB rows routinely (e.g., cron or ops job).  
- Keep only hash-chained summaries & derived results needed for accountability.

---

## Integrity & security

- **Tamper evidence:** Per-minute chain hashes; optional Ed25519 signatures
- **Canonicalization:** Chain computed over canonical JSON to prevent ambiguity  
- **Hardening hints:**  
  - Run the receiver behind TLS & auth (bearer tokens, mTLS, or reverse proxy) 
  - Least-privilege file access to `AVSAFE_DB` 
  - WAL-mode SQLite with regular vacuum/backup
  - Use `AVSAFE_STRICT_CRYPTO=1` in production
  - Secret scanning in CI and pre-commit; never commit private keys.

More info in [Security](SECURITY.md)

---

## Transparency & consent

Deployers must:
- Provide **signage** and/or notice that environmental descriptors are being measured
- Offer a clear **opt-out** path where applicable
- Avoid deployments in coercive contexts
- Keep a record of purpose, lawful basis (if required), retention, and contacts

---

## Access & sharing

- **Default:** No external sharing 
- If you publish reports, ensure they contain only **aggregated descriptors** and **no PII**
- Limit access to operational logs/DB to authorized staff

---

## Research & analytics

- Use **synthetic** or **public non-sensitive** data for examples/tests 
- If you conduct studies with human participants, obtain appropriate **consent/ethics review**

---

## Responsibilities (Deployers)

- Follow [Acceptable Use](ACCEPTABLE_USE.md) (no surveillance, no coercion) 
- Configure privacy-preserving ingestion (descriptors only) 
- Keep software updated; apply security patches
- Audit your configuration regularly (tokens, TLS, retention) 
- Document and honor opt-out mechanisms

---

## Contact

Questions about privacy or ethics, or to raise a concern:

**av-safe-info@proton.me**

---

## Changes

Updates to this document may happen as the project evolves. Material changes will be noted in the repository changelog and release notes.
