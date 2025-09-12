# HF‑AVC Corpus

A **machine-readable, citable corpus** that maps *cases → modalities → engineering descriptors → legal/ethical tags*.  
It powers the historico-forensic side of AV-SAFE and interoperates with the sensor workflow via a shared vocabulary (JSON-LD).

---

## Layout
**av-safe-toolkit/**
└─ **avsafe_descriptors/**
└─ **hf_avc/**
├─ cases/ # JSON case records (one file per case)
│ ├─ case_template_v1.json # Start here for new cases
│ └─ example_waco_v1.json # Example record (v1 schema)
├─ **schemas/**
│ ├─ case_schema_v1.json # Strict JSON Schema for validation
│ └─ context.jsonld # JSON-LD context for semantic tags
├─ ingest_cli.py # CLI: ingest JSON → SQLite
├─ query_cli.py # CLI: list/filter/export from SQLite
└─ models.py # Pydantic models (Case/Source/etc.)

```bash
- **Schema version:** `1.0.0`  
- **JSON-LD context:** `hf_avc/schemas/context.jsonld`

> **$schema hint (recommended):** Put this at the top of every case file:  
> `"${schema}": "../schemas/case_schema_v1.json"`
```
---

## Add a new case (quick start)

**1) Copy the template**  
   `hf_avc/cases/case_template_v1.json` → `hf_avc/cases/<your_case_id>.json`

**2) Keep the header consistent** (inside the outer `{ ... }`):
```json
"$schema": "../schemas/case_schema_v1.json",
"schema_version": "1.0.0",
"@context": "hf_avc/schemas/context.jsonld",
"@type": "HFAVC:Case",
```

**3) Fill required fields (minimal viable record)**
- `id`: `"case:country_year_slug"`
- `title`: short, neutral
- `jurisdiction.country_iso2`: e.g., `"US"`, `"DE"`
- `period.start` / `period.end`: `"YYYY[-MM]"`
- `modalities`: `["audio"]`, `["light"]`, or both
- `summary`: calm, non-sensational, sourced
- `reported_effects`: controlled list (e.g., `"sleep disruption"`)
- `descriptors`: proxies with uncertainty (`ranges` + `confidence`)
- `sources`: at least one with `title`, `year`, `url` (or archive ref), `provenance`

**4) Validate locally**
```bash
# Validate one file
python -m avsafe_descriptors.hf_avc.validate_cases \
  --schema avsafe_descriptors/hf_avc/schemas/case_schema_v1.json \
  --cases  avsafe_descriptors/hf_avc/cases/your_case.json

# Validate all cases
python -m avsafe_descriptors.hf_avc.validate_cases \
  --schema avsafe_descriptors/hf_avc/schemas/case_schema_v1.json \
  --cases  "avsafe_descriptors/hf_avc/cases/*.json"
```

**5) Ingest into SQLite (optional)**
```bash
hf-avc-ingest \
  --db hf_avc_corpus.db \
  --cases "avsafe_descriptors/hf_avc/cases/*.json"
```

**6) Query and export (optional)**
```bash
hf-avc-query --db hf_avc_corpus.db ls --limit 10
hf-avc-query --db hf_avc_corpus.db by-country US
hf-avc-query --db hf_avc_corpus.db by-period 1990 2000
hf-avc-query --db hf_avc_corpus.db timeline
hf-avc-query --db hf_avc_corpus.db export-csv corpus.csv
```

### Example (concise case)
```json
{
  "$schema": "../schemas/case_schema_v1.json",
  "schema_version": "1.0.0",
  "@context": "../schemas/context.jsonld",
  "@type": "HFAVC:Case",

  "id": "case:us_1993_waco_summary",
  "title": "Siege loudspeaker operations (summary)",

  "jurisdiction": {
    "country_iso2": "US",
    "place": "Waco, Texas",
    "coordinates": { "lat": null, "lon": null }
  },

  "period": { "start": "1993-02", "end": "1993-04" },
  "coercion_context": ["siege", "law-enforcement"],
  "modalities": ["audio"],

  "summary": "Neutral, sourced summary. Contemporary reporting and official accounts describe loudspeaker use with music and announcements during night hours.",

  "exposure_pattern": {
    "continuity": "intermittent",
    "duty_cycle_percent": 50,
    "time_of_day": ["night"]
  },

  "reported_effects": ["sleep disruption", "distress"],

  "descriptors": {
    "audio": {
      "laeq_db": { "range": { "min": 55, "max": 70 }, "confidence": 0.6 },
      "third_octave_db": { "125": 60.0, "250": 58.5, "500": 57.0 }
    },
    "notes": "Proxies with uncertainty; triangulated from sources."
  },

  "standards_mapping": {
    "who_noise_2018": { "night_guideline_db": 40, "likely_exceeded": true }
  },

  "legal_ethics": {
    "uncat": "ill-treatment (context-dependent)",
    "echr_article_3": "potential relevance",
    "istanbul_protocol_refs": ["2022: Ch.5"]
  },

  "sources": [
    {
      "id": "src:press_1993_lat",
      "title": "Contemporary reporting (placeholder)",
      "year": 1993,
      "url": "https://example.org/article",
      "publisher": "Press",
      "doc_type": "news",
      "provenance": "press"
    }
  ],

  "provenance": {
    "coded_by": ["user:ab"],
    "double_coded_by": ["user:cd"],
    "adjudicator": "user:ef",
    "coding_date": "2025-09-10",
    "review_status": "external_pending",
    "interrater_kappa": 0.78
  }
}
```

## Field notes & conventions
- **Neutral tone**: describe, don’t dramatize.
- **Uncertainty first**: narrative → proxy with ranges + `confidence` (0–1), explain in `descriptors.notes`.
- **Modalities**: `audio`, `light` (others may be mentioned in text but aren’t measured here).
- **Descriptors (audio)**: `laeq_db`, optional `lcpeak_db`, `third_octave_db` (band centers as string keys).
- **Descriptors (light)**: `tlm_freq_hz`, `tlm_mod_percent`, `flicker_index` (prefer ranges when uncertain).
- **Standards mapping**: conservative, explanatory (`who_noise_2018`, `ieee_1789_2015`).
- **Legal/ethics**: UNCAT, ECHR Art. 3, Istanbul Protocol refs; keep labels cautious unless jurisprudence is explicit.
- **Sources**: stable links (DOI/official archives) or clear archive notes; include `provenance`, `pages`, short neutral `quote` (≤300 chars) when appropriate.
- **No PII or raw content**; no sensational detail.

## JSON-LD (semantics)
The corpus is JSON first, JSON-LD enabled. `@context` maps core fields to stable IRIs (Schema.org, PROV-O, project namespace), enabling:
- Graph merges across versions/projects
- SPARQL-like queries when exported
- Stronger interoperability with standards vocabularies
Most contributors *do not need* to edit the context file.

## Quality gates (reviewers check)
- Schema valid (no extra properties; correct types)
- Sources credible; URLs resolve or have archive notes
- Neutral summary; uncertainty explicit in proxies
- Standards mapping cautious and justified
- `$schema` path and `schema_version` correct
- No PII / raw recordings

## Ethics & acceptable use
This corpus documents history and context to support privacy-preserving, standards-aligned auditing.
See `ACCEPTABLE_USE.md`, `CODE_OF_CONDUCT.md`, and `SECURITY.md`.
**No reenactment; no harmful stimuli.**

## Commands reference
```bash
# Validate
python -m avsafe_descriptors.hf_avc.validate_cases \
  --schema avsafe_descriptors/hf_avc/schemas/case_schema_v1.json \
  --cases  "avsafe_descriptors/hf_avc/cases/*.json"

# Ingest to SQLite
hf-avc-ingest \
  --db hf_avc_corpus.db \
  --cases "avsafe_descriptors/hf_avc/cases/*.json"

# Query / export
hf-avc-query --db hf_avc_corpus.db ls --limit 20
hf-avc-query --db hf_avc_corpus.db by-country DE
hf-avc-query --db hf_avc_corpus.db by-period 1990 2000
hf-avc-query --db hf_avc_corpus.db export-csv corpus.csv
```

Need a new query **(e.g., by effect, by modality, CSV slice)**?
Open an issue and we’ll extend `hf-avc-query`.
