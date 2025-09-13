# Changelog
All notable changes to this project will be documented here.


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
