# Project Governance — AV-SAFE Toolkit

This document defines how the AV-SAFE project is supervised: roles, decision-making, releases, security, and contributor expectations. It aims to keep the project open, ethical, and sustainable.

---

## 1) Values

- **Scope:** Privacy-preserving audiovisual metrology (WHO/IEEE-aligned), historico-forensic corpus (HF-AVC), receiver API, and report tooling
- **Values:** Privacy by design, safety first, scientific rigor, transparency, and respectful collaboration
- **Ethics:** All work must comply with our [Code of Conduct](CODE_OF_CONDUCT.md) and [Acceptable Use](ACCEPTABLE_USE.md)

---

## 2) Roles

- **Maintainers**  
  - Listed in [MAINTAINERS.md](MAINTAINERS.md)  
  - Own release engineering, triage, and final arbitration
  - May merge PRs, label issues, and manage CI/CD and security processes
- **Reviewers**  
  - Can approve changes but cannot cut releases unless they are also maintainers
- **Contributors**  
  - Anyone submitting issues/PRs

**If conflict of interest, disclose material conflicts on issues/PRs; recuse from decisions where appropriate.**

---

## 3) Decision Model

**Lazy consensus by default**  

---

## 4) Prior Discussion / RFC

Open an issue first for changes that are:
- Public API changes (CLI flags, endpoints, on-disk formats)
- Security model or cryptographic changes
- Schema changes to HF-AVC (`case_schema_v1.json`)  
- Backward-incompatible behavior  
- New external dependencies or service integrations

For larger proposals, open a design note (`docs/rfcs/YYYY-MM-short-slug.md`) and link it in the tracking issue.

---

## 5) Branching & Merging

- **Default branch:** `main` (always green)  
- **Branches:** feature branches from `main` → PR 
- **CI required:** tests must pass; lint/format must be clean  
- **Reviews:** at least **maintainer and reviewers** must approve non-trivial PRs  
- **Rebases:** the PR author rebases if conflicts occur

---

## 6) Release Process

- **Versioning:** Semantic Versioning (SemVer): `MAJOR.MINOR.PATCH`
- **Criteria:** CI green, changelog updated, docs synced, migrations noted
- **Cut:**  
  1. Tag: `vX.Y.Z` from `main`  
  2. Create GitHub Release with highlights and checksums  
  3. Publish artifacts and updated docs site
- **Backports:**  
  - Security and critical bug fixes may be backported to the latest `X.Y` via `release/X.Y` branches
  - Backport PRs cherry-pick the minimal change; bump patch version

---

## 7) Security & Privacy

- **Reporting:** See [SECURITY.md](SECURITY.md) (contact: **av-safe-info@proton.me**)  
- **Crypto posture:** Production must use real Ed25519 (`AVSAFE_STRICT_CRYPTO=1`); demo fallbacks are forbidden in prod  
- **Secrets hygiene:**  
  - No private keys or tokens in the repo
  - CI runs a “non-pertinent validation check” (secret scan) and fails on likely leaks  
  - If a secret lands, rotate promptly and purge with `tools/purge_secret.sh`

---

## 8) Data & Ethics

- **No raw content:** Only descriptors (no speech, images, video) 
- **HF-AVC corpus:** Neutral tone, uncertainty ranges, credible sources; schema-valid and JSON-LD consistent  
- **Deployments:** Require signage/notice and opt-out where applicable; coercive contexts are out of scope per [Acceptable Use](ACCEPTABLE_USE.md)

---

## 9) Issue & PR Workflow

1. **Open an issue** describing the problem or proposal; link to any RFC if needed 
2. **Discuss scope**; maintainers help shape an implementation plan
3. **Submit PR** following [CONTRIBUTING.md](CONTRIBUTING.md): tests, docs, changelog  
4. **Review & CI**: required checks must pass; maintainers merge 
5. **Follow-ups**: file issues for deferred items or improvements

---

## 10) User Documentation

- **User docs:** `docs/` (mkdocs)
  - **API:** `docs/api.md`
  - **Corpus guide:** `docs/corpus.md`
  - **Index:** `docs/index.md`
  - **Quickstart:** `docs/quickstart.md`
  
All user-visible changes should be reflected in the docs as part of the PR.

---

## 12) Licensing

- **License:** MIT (see `LICENSE`).  
- **Contributor IP:** By contributing, you affirm you have the right to contribute your changes under MIT 
- **Third-party code:** Include license notices where required

---

## 13) CI/CD & Quality Gates

- **Must pass:** unit tests, type/lint, schema validation (HF-AVC), and secret scan
- **Docs build:** PRs changing user-facing behavior should update docs; doc build must succeed

---

## 14) Deprecation Policy

- Announce deprecations in release notes and docs  
- Provide warnings for at least **one minor release** before removal.  

---

## 15) Operations Notes

- **Environments:**  
  - Dev: `docker-compose` service `avsafe-dev`
  - Prod: `avsafe` 
- **Config knobs:** `AVSAFE_DB`, `AVSAFE_STRICT_CRYPTO`, `PYTHONUNBUFFERED`.  
- **Backups:** Treat the SQLite database as sensitive; rotate and prune per `PRIVACY.md`.


---

## 17) Amendments

This document evolves. Substantive changes follow the same decision model.
