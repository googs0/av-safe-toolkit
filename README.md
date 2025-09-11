# AV-SAFE (Descriptors + Rules + Integrity + Reports) + HF‑AVC Corpus (WP1)

Privacy-preserving **minute summaries** for audio & light, **rules engine** (WHO/IEEE-aware), **hash-chain + Ed25519** integrity, **SQLite-backed FastAPI** server, **HTML reports**, and **HF‑AVC corpus (taxonomy & threat model)**.

## Quickstart

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .

# 1) Simulate minutes for 6h (prints keys if --sign)
avsafe-sim --minutes 360 --outfile minutes.jsonl --sign

# 2) Evaluate rules with a WHO/IEEE profile and locale thresholds
avsafe-rules-run   --minutes minutes.jsonl   --profile avsafe_descriptors/rules/profiles/who_ieee_profile.yaml   --locale munich   --out results.json

# 3) Generate HTML report
avsafe-report --minutes minutes.jsonl --results results.json --out report.html
```

## Server

```bash
uvicorn avsafe_descriptors.server.app:app --reload --port 8000
# POST /session -> {session_id}
# POST /session/{session_id}/ingest_jsonl  (file=@minutes.jsonl)
# POST /session/{session_id}/evaluate      (body: {"rules_yaml":"<yaml>"})
# GET  /session/{session_id}/report?public_key_hex=<hex>
```

## WP1 — HF‑AVC corpus (taxonomy & threat model)
Define and ingest **historico‑forensic cases** into a local SQLite corpus with JSON‑LD friendly fields.

```bash
# Validate + ingest sample cases into hf_avc_corpus.db
hf-avc-ingest --cases avsafe_descriptors/hf_avc/data/cases/*.json

# Inspect (SQLite)
sqlite3 hf_avc_corpus.db '.tables'  # cases, sources, case_sources
sqlite3 hf_avc_corpus.db 'SELECT id,title,period FROM cases;'
```

- Schema: `avsafe_descriptors/hf_avc/schemas/case.schema.json`  
- JSON‑LD context: `avsafe_descriptors/hf_avc/schemas/context.jsonld`  
- Python models: `avsafe_descriptors/hf_avc/models.py`

---

## Roadmap (illustrative Gantt, 36 months)

| Phase | Months | Milestones |
|---|---|---|
| Setup & Ethics | 0–3 | IRB/DPIA, data plan, prereg |
| O1 Corpus/Codebook | 1–9 | v1 schema; κ ≥ .75; 600 docs |
| O3 Sensor v1 & Bench | 4–12 | PCB/firmware; ±1 dB LAeq; ±1 Hz / ±5% Mod% |
| O2 KG & Reconstructions | 6–15 | KG online; DSP notebooks |
| O4 Privacy/Integrity | 7–14 | red-team AUC ≤ .55; signed minute hashes |
| O5 Cases & Rubric | 12–24 | 6–8 cases; ≥4 external reviews |
| O6 Field & Audits | 12–30 | 30 devices/12 rooms; r ≥ .90; ICC ≥ .85; κ ≥ .80 |
| O7 Papers & Release | 24–36 | 3 papers; open artifacts; thesis |

**Milestone badges** (tick ✓ when achieved):  
- 🟩 **Corpus v1** — ☐  
- 🟩 **Sensor v1 bench** — ☐  
- 🟩 **Privacy red-team** — ☐  
- 🟩 **Field ICC ≥ .85** — ☐  
- 🟩 **Checklist κ ≥ .80** — ☐  
- 🟩 **Open releases** — ☐  


![Lint](https://github.com/<YOURUSER>/av-safe-toolkit/actions/workflows/lint.yml/badge.svg)

## License
Released under the **MIT License** (see [LICENSE](LICENSE)).
