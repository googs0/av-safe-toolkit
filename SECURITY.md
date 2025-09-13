# Security Policy

AV-SAFE is designed to be privacy-preserving and tamper-evident. We welcome responsible disclosure of vulnerabilities that could impact privacy, integrity, or availability.

---

## Report a vulnerability

- **Email:** av-safe-info@proton.me  
- **Subject:** `[SECURITY] <short title>`
- **Encryption (optional):** If you prefer PGP, include your public key in the initial email and we’ll reply with our key/fingerprint.

> Please **do not** include raw audio/video, personally identifiable information (PII), or sensitive production data in reports. AV-SAFE processes descriptors only—reports should do the same.

---

## What to Include

Please provide a concise report that helps us reproduce and assess impact:

- **Summary:** What’s the issue and why it matters?
- **Component:** (e.g., `server/app.py`, `rules/evaluator.py`, `integrity/*`, docs site)
- **Affected versions/commit:** (tag or SHA)
- **Environment:** OS, Python version, container details (if any)
- **Steps to reproduce:** Minimal, deterministic steps
- **Proof of concept (PoC):** Repro script or HTTP trace; sanitize any sample data
- **Impact:** Privacy breach, signature/chain bypass, integrity failure, RCE, SSRF, DoS, IDOR, etc.
- **Mitigation ideas (optional):** If you have a proposed fix or guardrail

If the issue involves cryptography or signature verification, please note:
- Whether `AVSAFE_STRICT_CRYPTO=1` was set
- Whether records were signed and with what scheme
- Any keys used should be **dummy/test keys** only

---

## Scope

**In scope**
- Integrity features: **chain hashing**, **canonical JSON**, **signature verification**
- Rules parsing and evaluation (e.g., YAML profile ingestion)
- SQLite storage and ingest paths
- Docs site (if served from this repo) as it relates to information leaks or active content risks

**Out of scope**
- Social engineering, phishing, and physical attacks
- Third-party services and dependencies (please report upstream)
- Volumetric denial-of-service tests against shared infrastructure
- Findings that require raw A/V capture or PII to demonstrate
- Misconfiguration on your local hosts or forks

---

## Severity & Advisories

We prioritize issues that could:
- Bypass **signature verification** or **chain integrity**
- Cause **privacy leakage** (e.g., accidental storage/transmission of raw content)
- Enable **RCE**, **SSRF**, **path traversal**, **IDOR**, or **auth bypass**
- Corrupt or falsify reports without detection

---

## Handling Secrets & Keys

- **Never** include real secrets or production keys in a report.
- Use **dummy** Ed25519 keys for PoC signatures.  
- The project’s CI runs a secret scan; if you accidentally commit a secret, rotate it immediately and purge history (see `tools/purge_secret.sh`).

Environment variables relevant to crypto behavior:
- `AVSAFE_STRICT_CRYPTO=1` — require real Ed25519; disable demo fallback
- `AVSAFE_PRIV_HEX` — **local testing only**; do not commit or share

---

## Testing Ethically

AV-SAFE is intended to protect people. In testing:
- **Do not** generate or expose people to harmful sound/light patterns  
- **Do not** store or transmit raw recordings  
- Use **simulated minute summaries** (see `avsafe-sim`) and synthetic descriptors
Testing must use **synthetic** or **public non-sensitive** data. Do **not** attempt to elicit or replay harmful audio/visual stimuli.


See also: `ACCEPTABLE_USE.md`, `CODE_OF_CONDUCT.md`, `THREAT_MODEL.md`.

---

## After a Fix

When a fix is released AVSAFE will:
- Document upgrade steps in the release notes
- Credit researchers who wish to be named (thank you!)
- Propose additional hardening or configuration guidance

---

*Thank you for helping keep AV-SAFE and its users secure.*
