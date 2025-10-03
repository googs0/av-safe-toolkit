# AV-SAFE Toolkit

AV-SAFE measures and documents audiovisual environments **without recording intelligible content**.

Privacy-preserving **minute summaries** for audio & light, a **rules engine** aligned with **WHO Environmental Noise** and **IEEE-1789** practice, **hash-chain + optional Ed25519** integrity, a **SQLite-backed API** receiver, **HTML reports**, and a **HF-AVC corpus**.

- **Descriptors, not recordings:** LAeq, LCpeak, A-weighted 1/3-octaves; TLM frequency, percent modulation, flicker index  
- **Standards-aligned:** thresholds/rules reflecting WHO noise + IEEE-1789 flicker (piecewise curves)  
- **Evidence you can trust:** per-minute hash chaining, optional Ed25519 signatures; SQLite; HTML audit reports  
- **Research-grade corpus:** JSON-LD HF-AVC module (taxonomy + threat model) mapping cases to engineering descriptors and legal/ethics tags

---

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt

# 1) Simulate minutes (~6h). If --sign is set the simulator prints a demo key; DO NOT COMMIT IT.
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

---

## Server
```bash
uvicorn avsafe_descriptors.server.app:app --reload --port 8000
# POST /session -> {session_id}
# POST /session/{session_id}/ingest_jsonl  (file=@minutes.jsonl)
# POST /session/{session_id}/evaluate      (body: {"rules_yaml":"<yaml>", "locale":"munich"})
# GET  /session/{session_id}/report?public_key_hex=<hex>
```

---

## Backend pipeline
Full serverless stack that lets you run locally or deploy later on AWS
- Fast API
- Authentication via `dev` (static bearer token) or `jwt`
- Pipeline steps:
  - `verify_lambda.py` on upload, **verify hash-chain and signatures**, copy to `verified/`, update case status
  - `rules_lambda.py` on verified minutes, **run WHO/IEEE rules** and **render HTML**
- Local runner (`local_runner.py`) runs same **verify** -> **rules** --> **report** flow offline
 
**devices** compute + sign minutes; **the backend** verifies --> evaluates --> produces a report

---

## HF-AVC corpus (taxonomy & threat model)
Define and ingest historical-forensic cases into a local SQLite corpus. JSON files validate against a JSON Schema and can be published with a JSON-LD context for interop.
```bash
# Validate + ingest sample cases into hf_avc_corpus.db
hf-avc-ingest --cases "avsafe_descriptors/hf_avc/cases/*.json"

# Inspect (SQLite)
sqlite3 hf_avc_corpus.db '.tables'
sqlite3 hf_avc_corpus.db 'SELECT id,title,period FROM hf_cases LIMIT 10;'
```
- JSON Schema: `avsafe_descriptors/hf_avc/schemas/case_schema_v1.json`
- JSON-LD context: `avsafe_descriptors/hf_avc/schemas/context.jsonld`
- Pydantic models: `avsafe_descriptors/hf_avc/models.py`

---

## Integrity & Signing
AV-SAFE supports tamper-evident reports via per-minute hash chaining and optional Ed25519 signatures.

### Environment variables
  - AVSAFE_PRIV_HEX — optional Ed25519 seed (64 hex chars = 32 bytes) for stable local signatures
  - AVSAFE_STRICT_CRYPTO=1 — require real crypto in CI/prod (disable demo fallback)

```bash
# placeholder example — replace locally with your own key; DO NOT COMMIT REAL KEYS
export AVSAFE_PRIV_HEX="<64-hex-private-key>"
export AVSAFE_STRICT_CRYPTO="1"
```

### Security hygiene
  - CI scans for secrets (Gitleaks) on each push/PR
  - Local pre-commit uses detect-secrets with a baseline
  - If something leaks: rotate at the provider, then run tools/purge_secret.sh "<pattern>" main and force-push

---

## Ethics & Governance (quick overview)

- **Ethics & privacy by design:** descriptors only, no raw audio/video; per‑minute hash chaining; optional signatures. See [Privacy](PRIVACY.md)
- **Threat model:** assets/adversaries/mitigations. See [Threat Model](THREAT_MODEL.md)
- **Acceptable use:** anti‑surveillance licensing intent; deployment guidance. See [Acceptable Use](ACCEPTABLE_USE.md)
- **Community:** [Code of Conduct](CODE_OF_CONDUCT.md), [Governance](GOVERNANCE.md), [Contributing](CONTRIBUTING.md)
- **Use cases:** architecture/ombuds audits, human-rights documentation, and reproducible metrology for AV environments—strictly anti-surveillance and ethics-forward
- **Disclaimer:** [Disclaimer](DISCLAIMER.md)

---

## Why this matters?

From medieval “bell” punishments to modern “no-touch” programs, archives and testimony show how sound and light (loudness, frequency, repetition, flicker) have been weaponized in detention, siege, and other coercive settings. Harmful audiovisual patterns can erode sleep, cognition, and well-being, yet most spaces lack objective, privacy-respecting ways to detect and document them. **AV-SAFE toolkit** closes that gap by:

* Encoding historical-forensic record into measurable descriptors and a machine-readable decision rubric
* Converting ambient signals into WHO noise / IEEE-1789 flicker–aligned metrics and tamper-evident reports—without recording or storing intelligible content

The corpus, rules, and privacy-preserving sensor workflow translate history and testimony into actionable reports and engineering language for auditors, architects, ombuds, rights monitors, and many more professionals in a multitude of fields--enabling practical prevention and accountability that respects ethics and privacy.

---

## Location Data Policy
AV-SAFE records **coarse** location only. Use a room/site code (e.g., “Bedrm-2A”) or a geohash truncated to **5–7 characters**. Do **not** record precise coordinates or addresses in minute summaries. Enforcement occurs at ingest via schema validation and the policy tool.

---

## License
Released under the **MIT License** (see [License](LICENSE)).
