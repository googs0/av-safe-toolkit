
# AV‑SAFE Toolkit

Privacy‑preserving **minute summaries** for audio & light, **rules engine**, **hash‑chain + optional Ed25519** integrity, **SQLite‑backed FastAPI** receiver, **HTML reports**, and a **HF‑AVC corpus**.

---
AV-SAFE is a privacy-by-design framework for measuring and documenting audiovisual environments without recording intelligible content.

* **Descriptors, not recordings:** LAeq, LCpeak, A-weighted 1/3-octaves; flicker frequency, percent modulation, flicker index.

* **Standards aligned:** thresholds/rules reflecting **WHO Environmental Noise and IEEE-1789 practice** (piecewise curves).

* **Evidence you can trust:** per-minute hash chaining and optional Ed25519 signatures; SQLite-backed FastAPI receiver; HTML audit reports.

* **Research-grade corpus:** a JSON-LD HF-AVC module (taxonomy + threat model) for historico-forensic cases mapped to engineering descriptors and UNCAT/ECHR/Istanbul categories.


## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt

# 1) Simulate minutes for ~6h (prints keys if --sign)
avsafe-sim --minutes 360 --outfile minutes.jsonl --sign

# 2) Evaluate rules with a WHO/IEEE profile and locale thresholds
avsafe-rules-run \
  --minutes minutes.jsonl \
  --profile avsafe_descriptors/rules/profiles/who_ieee_profile.yaml \
  --locale munich \
  --out results.json

# 3) Generate HTML report
avsafe-report --minutes minutes.jsonl --results results.json --out report.html
```

## Server

```bash
uvicorn avsafe_descriptors.server.app:app --reload --port 8000
# POST /session -> {session_id}
# POST /session/{session_id}/ingest_jsonl  (file=@minutes.jsonl)
# POST /session/{session_id}/evaluate      (body: {"rules_yaml":"<yaml>", "locale":"munich"})
# GET  /session/{session_id}/report?public_key_hex=<hex>
```

## HF‑AVC corpus (taxonomy & threat model)

Define and ingest **historico‑forensic cases** into a local SQLite corpus. JSON files validate against a JSON Schema and can be published with a JSON‑LD context for interop.

```bash
# Validate + ingest sample cases into hf_avc_corpus.db
hf-avc-ingest --cases avsafe_descriptors/hf_avc/data/cases/*.json

# Inspect (SQLite)
sqlite3 hf_avc_corpus.db '.tables'
sqlite3 hf_avc_corpus.db 'SELECT id,title,period FROM hf_cases LIMIT 10;'
```

- JSON Schema: `avsafe_descriptors/hf_avc/schemas/case.schema.json`  
- JSON‑LD context: `avsafe_descriptors/hf_avc/schemas/context.jsonld`  
- Pydantic models: `avsafe_descriptors/hf_avc/models.py`

## Architecture

```
[Edge/Sim] → minute JSONL (LAeq, 1/3‑oct, TLM)
    ↓  hash‑chain + (optional) Ed25519
[FastAPI+SQLite] → rules (WHO/IEEE) → flags → HTML report
```

## Integrity & Signing
AV-SAFE signs records to support tamper-evident reports.

- `AVSAFE_PRIV_HEX` — Optional **Ed25519 seed** (64 hex chars = 32 bytes).  
  Use this locally if you want **stable signatures across runs**.
  ```bash
  # Example placeholder - replace locally
  export AVSAFE_PRIV_HEX="0123456789abcdeffedcba98765432100123456789abcdeffedcba9876543210"
  ```

  ### Security hygiene (secrets)
  - CI scans for secrets via Gitleaks on every push/PR.
  - Local pre-commit uses `detect-secrets` with a baseline.
  - If a secret leaks: rotate at the provider, then run `tools/purge_secret.sh "<pattern>" main` and force-push.

**Integrity & Signing env vars**
- `AVSAFE_PRIV_HEX` — optional Ed25519 seed (64 hex). For stable local signatures.
- `AVSAFE_STRICT_CRYPTO=1` — require real crypto in CI/prod (no demo fallback).


## Ethics & Governance (quick overview)

- **Ethics & privacy by design:** descriptors only, no raw audio/video; per‑minute hash chaining; optional signatures. See [Privacy](PRIVACY.md)
- **Threat model:** assets/adversaries/mitigations. See [Threat Model](THREAT_MODEL.md)
- **Acceptable use:** anti‑surveillance licensing intent; deployment guidance. See [Acceptable Use](ACCEPTABLE_USE.md)
- **Community:** [Code of Conduct](CODE_OF_CONDUCT.md), [Governance](GOVERNANCE.md), [Contributing](CONTRIBUTING.md)
- **Use cases:** architecture/ombuds audits, human-rights documentation, and reproducible metrology for AV environments—strictly anti-surveillance and ethics-forward
- **Disclaimer:** [Disclaimer](DISCLAIMER.md)


## Why this matters?

From medieval “bell” punishments to modern “no-touch” programs, archives and testimony show how sound and light (loudness, frequency, repetition, flicker) have been weaponized in detention, siege, and other coercive settings. Harmful audiovisual patterns can erode sleep, cognition, and well-being, yet most spaces lack objective, privacy-respecting ways to detect and document them. **AV-SAFE toolkit** closes that gap by:

* Encoding historical-forensic record into measurable descriptors and a machine-readable decision rubric
* Converting ambient signals into WHO noise / IEEE-1789 flicker–aligned metrics and tamper-evident reports—without recording or storing intelligible content

The corpus, rules, and privacy-preserving sensor workflow translate history and testimony into actionable reports and engineering language for auditors, architects, ombuds, and rights monitors--enabling practical prevention and accountability that respects ethics and privacy.

## License
Released under the **MIT License** (see [License](LICENSE)).
