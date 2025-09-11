# Contributing to AV‑SAFE

Thanks for your interest in improving AV‑SAFE! This project advances **privacy‑preserving audiovisual metrology** and **rights‑aware forensics**.

## Ground rules
- Be kind. Follow our [Code of Conduct](CODE_OF_CONDUCT.md).
- No harmful stimuli or exposure protocols.
- Privacy by design. No raw audio/video; descriptors only.
- Respect [Acceptable Use](ACCEPTABLE_USE.md).

## How to contribute
1. Open an Issue to discuss significant changes.
2. Fork; create a branch: `git checkout -b feat/short-name`.
3. Add tests.
4. `pre-commit install && pre-commit run -a`.
5. Conventional commits: `feat: ...`, `fix: ...`.
6. Open a PR and fill the checklist.

## Dev setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt
pre-commit install
pytest -q
```
