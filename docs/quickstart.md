# Quickstart

Run the **AV-SAFE Toolkit** locally, generate signed demo minutes (no raw audio/video), evaluate against WHO/IEEE rules, and render a tamper-evident report.

---

## 1) Prerequisites

- Python **3.10+** (3.11+ recommended)
- macOS / Linux / WSL (Windows PowerShell notes below)

> **Do not commit secrets.** If you set a dev signing key (`AVSAFE_PRIV_HEX`), keep it local and untracked.

---

## 2) Create a virtual env & install

```bash
python -m venv .venv
source .venv/bin/activate           # on Windows PowerShell: .\.venv\Scripts\Activate.ps1

pip install -e .
pip install -r requirements-dev.txt   # optional (lint, tests)
```
If your platform lacks Ed25519 libraries and you want CI to fail instead of using the demo fallback:
```bash
export AVSAFE_STRICT_CRYPTO=1    # PowerShell: $env:AVSAFE_STRICT_CRYPTO="1"
```

## 3) Simulate minutes (descriptors only)
Use CLI wrapper (installed entry point):
```bash
avsafe-sim --minutes 120 --outfile minutes.jsonl --sign
```

Equivalent module form:
```bash
python -m avsafe_descriptors.cli.sim --minutes 120 --outfile minutes.jsonl --sign
```

This writes newline-delimited JSON (`minutes.jsonl`) with:

- **audio**: LAeq, LCpeak, A-weighted 1/3-octaves
- **light**: TLM frequency, % modulation, flicker index
- **chain**: per-minute hash + optional Ed25519 signature (no raw audio/video)

Optional (dev only): deterministic signing for local tests
`export AVSAFE_PRIV_HEX="0123456789abcdeffedcba98765432100123456789abcdeffedcba9876543210"`

## 4) Evaluate rules (WHO/IEEE profile)
```bash
avsafe-rules-run \
  --minutes minutes.jsonl \
  --profile avsafe_descriptors/rules/profiles/who_ieee_profile.yaml \
  --locale munich \
  --out results.json
```
Equivalent module form:
```bash
python -m avsafe_descriptors.cli.rules_run \
  --minutes minutes.jsonl \
  --profile avsafe_descriptors/rules/profiles/who_ieee_profile.yaml \
  --locale munich \
  --out results.json
```
Outputs `results.json` with flags (e.g., `% time over night LAeq guideline`, `flicker risk zone`), metrics, and a trace of the ruleset.

## 5) Render a tamper-evident report (HTML)
```bash
avsafe-report --minutes minutes.jsonl --results results.json --out report.html
```
Equivalent module form:
```bash
python -m avsafe_descriptors.cli.report \
  --minutes minutes.jsonl \
  --results results.json \
  --out report.html
```
Open `report.html` in your browser.
It includes integrity summaries (hash chain, signatures), WHO/IEEE flags, and plots.

## 6) Run the API server (optional)
```bash
uvicorn avsafe_descriptors.server.app:app --reload --port 8000
```
**Endpoints:**
- `POST /session` → create session
- `POST /session/{id}/ingest_jsonl` → upload `minutes.jsonl`
- `POST /session/{id}/evaluate` → send rules YAML
- `GET /session/{id}/report?public_key_hex=…` → HTML/JSON report
See [api.md](/api.md)

## 7) Work with the HF-AVC corpus (optional)
Validate, ingest, and query the historico-forensic case records:
```bash
# Validate cases against the JSON Schema
python -m avsafe_descriptors.hf_avc.validate_cases \
  --schema avsafe_descriptors/hf_avc/schemas/case_schema_v1.json \
  --cases  "avsafe_descriptors/hf_avc/cases/*.json"

# Ingest → SQLite
hf-avc-ingest --db hf_avc_corpus.db --cases "avsafe_descriptors/hf_avc/cases/*.json"

# Query / export
hf-avc-query --db hf_avc_corpus.db ls --limit 10
hf-avc-query --db hf_avc_corpus.db by-country US
hf-avc-query --db hf_avc_corpus.db export-csv corpus.csv
```
See [corpus.md](/corpus.md)

## Troubleshooting
- **Ed25519 not available:** install pynacl (already in `requirements.txt`).
To fail if unavailable, set `AVSAFE_STRICT_CRYPTO=1`.
- **Windows PowerShell:** replace export `NAME=value` with `$env:NAME="value"`.
- **Nothing renders in `report.html`:** check that `results.json` path is correct and not empty.
- **Schema errors on corpus files:** run the validator (above) and fix the reported field paths.

## Next steps
- Configure CI (lint, tests, schema checks).
- Add real WHO/IEEE regional profiles (see avsafe_descriptors/rules/profiles/).
- Draft a new HF-AVC case from the template and open a PR.

You now have a local, end-to-end AV-SAFE workflow: simulate → evaluate → report, without recording intelligible content.
