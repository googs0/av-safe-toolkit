# Changelog
All notable changes to this project will be documented here.

---

## [0.9.1] - 2025-30-SEP
### Added
Cloud stack (local + AWS-ready)
- `cloud/api_app.py` - fastAPI with endpoints:
  - `GET /health`
  - `POST /cases` (create case)
  - `GET /cases/{case_id}` (status)
  - `POST /ingest/start` (pre-signed upload URL)
- `cloud/auth.py` - pluggable authentication:
  - **DEV mode** via static bearer token (`AUTH_MODE=dev`, `DEV_TOKEN`
  - **JWT mode** with JWKS/OIDC validation (`AUTH_MODE=jwt`, `JWKS_URL`
  - Optional: `JWKS_AUDIENCE`, `JWKS_ISSUER`)
- `cloud/common.py` - shared helpers
  - when `LOCAL_MODE=1`, S3/DynamoDB emulate `./local_data/` + SQLite (`cases.db`)
  - when not local: users real S3/DynamoDB (AWS) and utilities are as follows: signed URL helpers, JSONL IO (gz aware), device pubkey load, case registry, chain/signature verification, rules, and HTML rendering
- `cloud/verify_lambda.py` - verifies hash-chain + signatures and writes `verified/` and updates case status
- `cloud/rules_lambda.py` - offline pipeline runner (raw to verified to report for LOCAL_MODE:
  - `python -m cloud.local_runner --once`
  - `python -m cloud.local_runner --watch`
- `cloud/requirements.txt` - app deps (fastAPI, Mangum, jose, requests, uvicorn
- `cloud/template.yaml` - AWS SAM template (function URL for API); s3 triggers; DynamoDB)
- `cloud/__init__.py` - marks package for `-m` execution

### Updated
- Makefile (merged with cloud targets. Cloud artifacts go to `build/cloud/` to not clash with `build/e2e-video/`
- `template.yaml` SAM to function URL

---

## [0.9.1] - 2025-29-SEP
### Added
- Cloud folder
- `cloud/requirements.txt`
- `cloud/template.yaml` very minimal AWS serverless application model (SAM)

### Updated
- `rules_run.py` bug fix (L88-91)

---

## [0.9.1] - 2025-19-SEP
### Added
- Video luminance helper (video → luma): `avsafe_descriptors/video/__init__.py`,
`avsafe_descriptors/video/luma.py`: reads video via `imageio` returns `(y, fs)` where y = luma/frame and fs = FPS
- CLI to turn video to TLM metrics: `avsafe_descriptors/cli/video_to_light.py` — `avsafe-video-to-light --in clip.mp4 --minute --jsonl minutes.jsonl` reduces video to luminance and computes flicker metrics per window or as a minute summary.
- Smoke Test for Video: `tools/video_smoke.py` - quick manual check (video → minute summary), prints JSON to stdout.
- End-to-end test pipeline (video → summaries → rules → report): `tests/test_e2e_video_pipeline.py` — synthesizes two 1-minute 64×64 clips (10 Hz flicker @30 fps and constant control), runs `avsafe-video-to-light` to produce `minutes.jsonl`, then runs rules/report CLIs if present (fallbacks included). Produces an HTML report in a temp dir and asserts presence/size.
- Integration tests for short clips: `tests/test_video_to_tlm.py` — synthesizes small 5 s clips (10 Hz flicker @60 fps, 100 Hz PWM @30 fps which aliases ≈10 Hz, and constant control) and verifies dominant frequency/modulation within tolerances.
- **Makefile** for one-command E2E run:
`make setup-dev`: installs dev deps
`make videos`: generates 1-minute sample videos if missing
`make e2e-video`: video → minute summaries → WHO/IEEE rules → HTML report (outputs in `build/e2e-video/`)
`make smoke-video`: quick smoke using your helper script
`make test`: runs pytest suite
`make clean` — removes build/e2e-video/

### Updated
- .gitignore 
  
---

## [0.9.1] - 2025-13-SEP
### Added
- WHO/IEEE rules profile, including a piecewise IEEE-1789 mapping (`a + b/f`) and locale-selectable WHO LAeq limits
- Audio DSP utilities: A-weighting and **A-weighted 1/3-octave** band handling (10 Hz–40 kHz grid)
- Integrity pipeline: **per-minute hash chaining** + optional **Ed25519** signatures (domain-separated)
- HTML audit report with flags, chain continuity, noise/flicker summaries, and table view
- **HF-AVC corpus** module: JSON-LD context, strict JSON Schema, Pydantic models, and SQLite ingest
- CLI tools: `avsafe-sim`, `avsafe-rules-run`, `avsafe-report`, `hf-avc-ingest`, `hf-avc-query`
- Containerization: production Dockerfile and docker-compose for dev/prod/docs profiles
- MkDocs site configuration for project docs

### Changed
- Simplified corpus layout to `hf_avc/cases/` and `hf_avc/schemas/`; updated `$schema` hints accordingly.
- Hardened report rendering (template safety, defensive null handling, summary coercion).

### Fixed
- CI test to enforce real Ed25519 when `AVSAFE_STRICT_CRYPTO=1`; skip if no backend available locally.

---

## [0.9.1] - 2025-10-SEP
### Added
- WHO/IEEE rules profile with piecewise IEEE-1789 mapping (MVP).
- A-weighted 1/3-octave band levels & integrity (hash/sign).
- FastAPI+SQLite receiver; HTML report with hash-chain continuity.
- WP1 HF-AVC corpus module (JSON-LD context, JSON Schema, ingest CLI).

### Security
- .gitignore hardened to block private keys and local DB artifacts.

### Docs
- CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, GOVERNANCE, ACCEPTABLE_USE.
