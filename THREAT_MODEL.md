# AV-SAFE Threat Model (MVP)

**Scope:** Privacy-preserving audiovisual metrology pipeline (sim → rules → report), optional FastAPI receiver, and HF-AVC corpus tooling. This is an MVP technical threat model focused on integrity, misuse prevention, and privacy.

---

## 1) Assets & Trust Boundaries

### Primary assets
- **Minute summaries** (JSONL): LAeq/LCpeak/⅓-octave; TLM freq/mod%; flicker index.
- **Integrity metadata**: per-minute **chain hash** (SHA-256 over canonical JSON) and optional **Ed25519 signatures**.
- **Results & reports**: rules evaluation JSON + rendered HTML reports.
- **Corpus data** (HF-AVC): case files, schema, and SQLite corpus.

### Stores / interfaces
- **Local filesystem**: JSONL minutes, results, HTML reports, SQLite DB.
- **SQLite** (`AVSAFE_DB`): minute descriptors and integrity fields only.
- **CLI tools**: `avsafe-sim`, `avsafe-rules-run`, `avsafe-report`, `hf-avc-*`.
- **Optional API**: `/session/*` endpoints for ingest/evaluate/report.
- **CI**: secrets scanning, schema validation, crypto-enforcement test.

### Trust boundaries
- **Uploader → Receiver** (if API is enabled).
- **CLI user → Local DB/filesystem**.
- **Contributors → Corpus** (PRs to HF-AVC cases & schemas).

---

## 2) Assumptions (MVP)
- **No raw audio/video/PII** is ever stored or transmitted—descriptors only.
- **System time** is NTP-synchronized; minute `ts` is monotonic enough for chaining.
- **Signing keys** are managed off-repo (never committed); environment variable may be used for local testing: `AVSAFE_PRIV_HEX`.
- **Crypto libraries available** in production; CI enforces real Ed25519 (no demo fallback).

---

## 3) Adversaries
- **A1: Local tamperer** (same machine/container) tries to edit minutes or results.
- **A2: Network adversary** (if API): replaying, spoofing, or flooding uploads.
- **A3: Malicious contributor** submits poisoned corpus cases or malformed JSON.
- **A4: Curious admin/operator** attempts to reconstruct content or infer PII.
- **A5: Build/CI attacker** attempts to exfiltrate secrets or sneak in weak crypto.

---

## 4) Threats (STRIDE + LINDDUN)

| Category | Example |
|---|---|
| **Spoofing** | Forge minute files; impersonate signer; fake session IDs. |
| **Tampering** | Edit JSONL lines; truncate chain; tweak results JSON; alter DB rows. |
| **Repudiation** | Lack of trace of who ingested/when; unverifiable reports. |
| **Info disclosure** | Accidental storage of raw audio/video/PII; sensitive keys committed. |
| **Denial of service** | Huge uploads, pathological JSON, or excessive API calls (if enabled). |
| **Elevation of privilege** | Abusing API params, file paths, or DB to gain broader access. |
| **Linkability/Inferences** | Cross-link minutes to individuals or events (privacy risk). |
| **Data quality / poisoning** | Adversarial corpus cases; misleading descriptors. |

---

## 5) Mitigations (MVP)

### Integrity & authenticity
- **Hash chaining**: `hash_i = SHA256(hash_{i-1} || canonical_json(payload_i))`. Detects insertion, deletion, reordering, editing.
- **Ed25519 signatures**: sign canonical payloads (domain-separated). **CI enforces real crypto** via `AVSAFE_STRICT_CRYPTO=1` test.
- **Tamper-evident reports**: show chain and signature status inline (ok/missing/invalid).
- **Read-only canonicalization**: `canonical_json()` normalizes before hashing/signing.

### Input hardening
- **Strict JSON schema** for minutes (receiver) and **HF-AVC case schema**.
- **Type/limit checks**: non-negative frequencies, bounded modulation, bounded dB, max upload sizes (if API).
- **Idempotency keys** (API): mitigate replays for ingest/evaluate.
- **Content limits**: reject raw audio/video fields; descriptors only.

### Storage & runtime
- **SQLite in WAL mode**, local volume; no network DB exposure.
- **Least storage**: only descriptors + integrity fields; no raw content.
- **Logs** capture validation failures (schema, chain, signatures) with minimal metadata.

### Supply chain & CI
- **Secrets scanning (Gitleaks)**: allowlist only doc placeholders, fail on real leaks.
- **.gitignore** excludes dumps and keys; **no keys in repo** policy.
- **Pinned deps** (ranges) and **editable install** for dev; reproducible CI.

### Privacy by design
- **No PII fields**; no raw content by policy and code.
- **Acceptable Use** prohibitions; privacy signage/opt-out guidance in docs.

---

## 6) Residual Risk (Known, documented)
- **Clock skew** can reduce evidentiary value of timestamps (chain still detects edits).
- **Unsigned minutes**: integrity is chaining only; advise signing in production.
- **Descriptors leakage**: extreme values could still hint at context; mitigated by policy & minimization.
- **Corpus subjectivity**: despite schema, narrative mapping has judgment; mitigated via double-coding & review.

---

## 7) Operations & Key Management

- **Signing keys**  
  - Dev: `AVSAFE_PRIV_HEX` for local repeatability (never commit).  
  - Prod: use KMS/HSM or Docker secrets; rotate quarterly or on suspicion.
- **Fallback prevention**  
  - Set `AVSAFE_STRICT_CRYPTO=1` in prod; CI test fails if Ed25519 unavailable.
- **Secrets hygiene**  
  - Pre-commit hook (detect-secrets) + Gitleaks in CI.  
  - If exposure occurs: rotate, purge history (`tools/purge_secret.sh`), force-push.

---

## 8) Monitoring & Audit (MVP)
- **Receiver (if enabled)** logs: request ID, idempotency key, record counts, validation results (schema/chain/signature).
- **DB**: keep append-only minute rows per session; no destructive mutations.
- **Report**: embed verification summary + counts for transparency.

---

## 9) Abuse & Misuse Prevention
- **Acceptable Use**: bans surveillance/coercion; mandates signage and opt-out where applicable.
- **No reenactment**: test data via simulator only.  
- **Corpus ethics**: neutral tone, uncertainty ranges, provenance required.

---

## 10) Roadmap (Hardening)
- **Time**: signed timestamps (Roughtime/TSAs) or GNSS-backed RTC.
- **Keys**: hardware-backed signing (YubiHSM/KMS) and per-site key IDs in reports.
- **API**: OAuth2/JWT, mTLS, per-org rate limits, content-length caps, structured error envelope everywhere.
- **SBOM**: generate & publish; pin/lockfile approach for deployments.
- **Attestation**: TEEs or measured boot (out of MVP scope).
- **Corpus QA**: automated diff-lint for case narrative → descriptor consistency.

---

## 11) Out of Scope (MVP)
- Hardware TEEs / remote attestation
- Forensic time authorities / notarization services
- Coercive deployment scenarios (see **[Acceptable Use](ACCEPTABLE_USE.md)**)
- End-to-end secure telemetry transport across untrusted networks (beyond HTTPS)

---

## 12) Quick Checklist (Go/No-Go)

- [ ] No raw AV/PII; descriptors only  
- [ ] Chain hash verifies end-to-end  
- [ ] Ed25519 signatures present & valid (prod)  
- [ ] Minutes & cases pass schema validation  
- [ ] CI secrets scan green; no keys in repo  
- [ ] Acceptable Use acknowledged for deployment  
- [ ] Clock sync (NTP) verified on hosts
