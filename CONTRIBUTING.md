# Contributing to AV‑SAFE

Thanks for your interest in improving AV‑SAFE! This project advances **privacy‑preserving audiovisual metrology** and **rights‑aware forensics**.

## Ground rules
- **Be kind**. Follow our [Code of Conduct](CODE_OF_CONDUCT.md)
- **Do no harm**. No harmful stimuli or exposure protocols
- **Privacy by design.** No raw audio/video; descriptors only
- **Respect**. Anti-surveillance and anti-discipline [Acceptable Use](ACCEPTABLE_USE.md)
- **Security & disclosure:** Do not post private keys; see [Security](SECURITY.md) and [Disclaimer](DISCLAIMER.md)

---

## How to contribute
### 1. Open an Issue to discuss significant changes
### 2. Fork and branch 
   ```bash
   git checkout -b feat/short-name  # or fix/..., docs/..., rules/..., corpus/...
   ```
### 3. Dev Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt
pre-commit install
```
### 4. Add tests
### 5. Style
   ```bash
   pre-commit install
   pre-commit run -a      # format/lint before you push (optional if you dislike auto-lint)
   ```
### 6. Conventional commits
```vbnet
feat: add IEEE-1789 segment 1–2 kHz
fix: correct noise percentiles
docs: expand corpus submission
rules: raise night guideline to 45 dB
corpus: add case:us_1993_waco_summary
ci: tighten secret-scan allowlist
```
### 7. Open a PR and fill the checklist
   
---

## Adding an HF-AVC case
This project accepts historico-forensic cases as JSON files that validate against our schema and avoid sensational detail
- **Template:** `avsafe_descriptors/hf_avc/cases/case_template_v1.json`
- **Schema:** `avsafe_descriptors/hf_avc/schemas/case_schema_v1.json`
- **JSON-LD context:** `avsafe_descriptors/hf_avc/schemas/context.jsonld`

### 1. Copy template
   ```bash
   cp avsafe_descriptors/hf_avc/data/cases/CASE_TEMPLATE.json \
   avsafe_descriptors/hf_avc/data/cases/<your_case_id>.json
   ```
### 2. Keep the header (inside the outer { ... })
```json
"$schema": "../schemas/case_schema_v1.json",
"schema_version": "1.0.0",
"@context": "../schemas/context.jsonld",
"@type": "HFAVC:Case",
```

### 3. Fill required fields
Keep descriptors neutral \
Map narrative intensity to descriptor buckets (e.g laeq_bucket_db: '65-80') \
Add sources (URLs, publisher) that others can audit
- `id`: `"case:country_year_slug"`
- `title`: short, neutral
- `jurisdiction.country_iso2`: e.g., `"US"`, `"DE"`
- `period.start / period.end`: `"YYYY[-MM]"`
- `modalities`: `["audio"]`, `["light"]`, or both
- `summary`: calm, non-sensational, sourced
- `reported_effects`: controlled list (e.g., `"sleep disruption"`)
- `descriptors`: proxies with ranges + `confidence` (0–1); explain in `descriptors.notes`
- `sources`: at least one with `title`, `year`, `url` (or archive ref), `provenance`

### 4. Validate
` avsafe_descriptors/hf_avc/schemas/case.schema.json `
```python
python -m avsafe_descriptors.hf_avc.validate_cases \
  --schema avsafe_descriptors/hf_avc/schemas/case_schema_v1.json \
  --cases  "avsafe_descriptors/hf_avc/cases/*.json"
```

### 5. Ingest
   ```bash
   hf-avc-ingest --cases avsafe_descriptors/hf_avc/data/cases/<your_case_id>.json
   sqlite3 hf_avc_corpus.db 'SELECT id,title,period FROM hf_cases LIMIT 5;'
   ```
### 6. Open a PR with new case file
- Justify descriptor buckets & uncertainties
- Note any legal/ethical tags
- Confirm **no raw recordings** were added

## Changing rules/thresholds
**WHO noise:** edit `noise.laeq_limits_db` in \
`avsafe_descriptors/rules/profiles/who_ieee_profile.yaml`

**IEEE-1789 mapping:** adjust
`flicker.percent_mod_vs_freq.segments` (piecewise `a + b/f` curve)
- Provide a brief rationale and, when possible, cite a primary source
- Add/update tests showing the flag/threshold behavior

## Tests & quality
- Use `pytest`; aim for meaningful coverage of new logic
- Prefer deterministic tests (fixed seeds, stable thresholds)
- Keep outputs stable across platforms (avoid locale-dependent formatting)

## Secrets & pre-commit (important)
- Do not commit private keys, seeds, or tokens
- A minimal allowlist ignores only doc placeholders; real leaks still fail CI

Local scan (optional):

## Privacy & security checklist (before you push)
  ⃝ No raw audio/video/images anywhere in the repo or examples \
  ⃝ No private keys or credentials (the simulator prints test keys, do not commit them) \
  ⃝ If you touched integrity/signing, include a brief note in the PR about hash-chain continuity

<br>


**Questions / Concerns:** [av-safe-info@proton.me](av-safe-info@proton.me)

*** **By contributing, you agree your contributions are MIT-licensed (see [License](LICENSE.md))** ***
