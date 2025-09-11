# Contributing to AV‑SAFE

Thanks for your interest in improving AV‑SAFE! This project advances **privacy‑preserving audiovisual metrology** and **rights‑aware forensics**.

## Ground rules
- **Be kind**. Follow our [Code of Conduct](CODE_OF_CONDUCT.md)
- **Do no harm**. No harmful stimuli or exposure protocols
- **Privacy by design.** No raw audio/video; descriptors only
- **Respect**. Anti-surveillance and anti-discipline [Acceptable Use](ACCEPTABLE_USE.md)
- **Security & disclosure:** Do not post private keys; see [Security](SECURITY.md) and [Disclaimer](DISCLAIMER.md)

<br>

## How to contribute
1. Open an Issue to discuss significant changes
2. Fork and branch
   ```bash
   git checkout -b feat/short-name  # or fix/..., docs/..., rules/..., corpus/...
   ```
3. Add tests
4. Style:
   ```bash
   pre-commit install
   pre-commit run -a      # format/lint before you push (optional if you dislike auto-lint)
   ```
7. Conventional commits: `feat: ...`, `fix: ...`, `docs: ...`, `rules: ...`, `corpus: ...`, `ci: ...`
8. Open a PR and fill the checklist
   
<br>

## Dev setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt
pre-commit install
pytest -q
```
<br>

## Adding an HF-AVC case
This project accepts historico-forensic cases as JSON files that validate against our schema and avoid sensational detail
1. Copy template
   ```bash
   cp avsafe_descriptors/hf_avc/data/cases/CASE_TEMPLATE.json \
   avsafe_descriptors/hf_avc/data/cases/<your_case_id>.json
   ```
2. Fill fields carefully
- Keep descriptors neutral; include provenance and year
- Map narrative intensity to descriptor buckets (e.g laeq_bucket_db: '65-80')
- Add sources (URLs, publisher) that others can audit

3. Validate against schema: ` avsafe_descriptors/hf_avc/schemas/case.schema.json `
4. Ingest locally
   ```bash
   hf-avc-ingest --cases avsafe_descriptors/hf_avc/data/cases/<your_case_id>.json
   sqlite3 hf_avc_corpus.db 'SELECT id,title,period FROM hf_cases LIMIT 5;'
   ```
5. Open a PR with new case file
- Justify descriptor buckets & uncertainties
- Note any legal/ethical tags
- Confirm **no raw recordings** were added

<br>

## Changing rules/thresholds
- WHO noise limits by locale: add new keys under noise.` laeq_limits_db ` (e.g., `Stockholm: 55`).
- IEEE-1789 mapping: adjust ` flicker.percent_mod_vs_freq.segments ` (piecewise ` a + b/f `).
- Provide a short rationale in the PR and, if possible, cite a primary source

<br>

## Tests & quality
- Use ` pytest `; aim for meaningful coverage of new logic.
- Prefer deterministic tests (fixed seeds, stable thresholds).
- For rules changes, add a tiny JSONL fixture to demonstrate the flag/threshold behavior.
- **No real-world recordings** in tests or fixtures—only synthetic, safe descriptors

<br>

## Privacy & security checklist (before you push)
✅ No raw audio/video/images anywhere in the repo or examples \
✅ No private keys or credentials (the simulator prints test keys—do not commit them) \
✅ If you touched integrity/signing, include a brief note in the PR about hash-chain continuity

<br>


**Questions / Concerns:** [av-safe-info@proton.me](av-safe-info@proton.me)

<br>

** **By contributing, you agree your contributions are MIT-licensed (see [License](LICENSE.md))** **
