# AV-SAFE Toolkit
**Privacy-preserving audiovisual metrology** (WHO noise / IEEE-1789 flicker–aligned) + a **historico-forensic (HF-AVC) corpus** that turns testimony and archives into measurable descriptors and rules. Encode history into standard engineering language, then measure real rooms with a privacy-first workflow that never stores intelligible content—producing tamper-evident, standards-aligned audit reports.

---

## Highlights

- **Descriptors, not recordings:** LAeq, LCpeak, A-weighted 1/3-octaves; TLM frequency, % modulation, flicker index.  
- **Integrity by design:** per-minute hash chaining + optional **Ed25519** signatures.  
- **WHO/IEEE-aligned rules:** transparent thresholds (no black-box ML).  
- **HF-AVC corpus:** JSON-LD cases linking modalities → descriptors → legal/ethical tags.  
- **Batteries included:** SQLite-backed **FastAPI** receiver + HTML report with integrity summary.

---

## What’s inside

av-safe-toolkit/
└─ avsafe_descriptors/
├─ audio/ # A-weighting, 1/3-octave utilities
├─ cli/ # Command-line tools (sim, rules_run, report, validate_cases)
├─ hf_avc/ # Historico-forensic corpus (cases, schema, CLIs)
│ ├─ cases/ # Case JSON (one per file)
│ ├─ schemas/ # JSON Schema + JSON-LD context
│ ├─ ingest_cli.py # -> hf-avc-ingest (JSON → SQLite)
│ └─ query_cli.py # -> hf-avc-query (list/filter/export)
│ └─ models.py # -> hf-avc-query (list/filter/export)
├─ integrity/ # Hash chain + signing (Ed25519)
├─ report/ # HTML report renderer
├─ rules/ # WHO/IEEE profiles + evaluator
└─ server/ # FastAPI receiver (ingest/evaluate/report)
docs/
└─ index.md, API.md, CORPUS.md, quickstart.md # Project docs

Privacy-preserving audiovisual metrology (WHO/IEEE-aligned) and a historico‑forensic (HF‑AVC) corpus.

## Features
- Descriptors, not recordings (LAeq, LCpeak, A‑weighted 1/3‑octaves; TLM freq, % modulation, flicker index).
- Tamper-evident: hash-chained minutes + optional Ed25519 signatures.
- SQLite‑backed FastAPI receiver; HTML report with integrity summary.
- JSON‑LD corpus model for cases mapped to legal/ethical categories.

  
**Docs:** see [api.md](./api.md), [CORPUS.md](./corpus.md), and [quickstart.md](./quickstart.md) for details.

---

## Quickstart (local)

> Requires Python 3.10+ (recommended: 3.11+)

```bash
# 1) Create and activate a venv
python -m venv .venv && source .venv/bin/activate

# 2) Install
pip install -e .
pip install -r requirements-dev.txt  # optional (lint/tests)

# 3) Generate signed demo minutes (no raw audio/video)
python -m avsafe_descriptors.cli.sim \
  --minutes 120 \
  --outfile minutes.jsonl \
  --sign

# 4) Evaluate against a WHO/IEEE profile
python -m avsafe_descriptors.cli.rules_run \
  --minutes minutes.jsonl \
  --profile avsafe_descriptors/rules/profiles/default.yml \
  --out results.json

# 5) Render an HTML report with integrity summary
python -m avsafe_descriptors.cli.report \
  --minutes minutes.jsonl \
  --results results.json \
  --out report.html
```
Open `report.html` in your browser.

## Run the receiver (API)
```bash
uvicorn avsafe_descriptors.server.app:app --reload --port 8000
```
Then visit:
- `POST /session` → create session
- `POST /session/{id}/ingest_jsonl` → upload minutes.jsonl
- `POST /session/{id}/evaluate` → send rules YAML
- `GET /session/{id}/report?public_key_hex=…` → render report

Reference [api.md](./api.md)

## HF-AVC corpus (history → standards)
- Template, schema, and JSON-LD context: `avsafe_descriptors/hf_avc/`
- Validate, ingest, and query the corpus:
```bash
# Validate all cases against the schema
python -m avsafe_descriptors.hf_avc.validate_cases \
  --schema avsafe_descriptors/hf_avc/schemas/case_schema_v1.json \
  --cases  "avsafe_descriptors/hf_avc/cases/*.json"

# Ingest → SQLite
hf-avc-ingest --db hf_avc_corpus.db --cases "avsafe_descriptors/hf_avc/cases/*.json"

# List / filter / export
hf-avc-query --db hf_avc_corpus.db ls --limit 10
hf-avc-query --db hf_avc_corpus.db by-country US
hf-avc-query --db hf_avc_corpus.db export-csv corpus.csv
```
Reference [corpus.md](./corpus.md)

## Privacy, ethics, and acceptable use
- No raw content: Only descriptors are ingested/stored.
- Do-no-harm: No harmful stimuli generation; no sleep-loss protocols.
- Use restrictions: See ACCEPTABLE_USE.md.
- Conduct & security: See CODE_OF_CONDUCT.md and SECURITY.md.

### Integrity env vars (optional):
`AVSAFE_PRIV_HEX` (dev-only) for stable local signatures;
`AVSAFE_STRICT_CRYPTO=1` to fail if strong crypto isn’t available.

## Contribute
We welcome issues and pull requests!
- Start with `CONTRIBUTING.md` and `GOVERNANCE.md`
- Run `pre-commit install && pre-commit run -a` before PRs
- Use conventional commits (`feat:`, `fix:,` …)

If you’re proposing new rules or a new case type, please open an issue first so we can align on schema and vocabulary.

## Cite
Add a lightweight `CITATION.cff` (optional) or cite the repo URL / release DOI if you mint one

**AV-SAFE turns history and testimony into measurable, privacy-preserving evidence—so engineers, auditors, and rights monitors can fix spaces responsibly.**
```makefile
::contentReference[oaicite:0]{index=0}
```
