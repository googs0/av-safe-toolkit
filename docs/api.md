# AV-SAFE Receiver API (v1)

This API ingests **privacy-preserving minute summaries** (no raw audio/video), evaluates them against rules aligned with **WHO Environmental Noise** and **IEEE-1789** (flicker) practice, and renders **tamper-evident** reports.

- **No raw content:** only descriptors (LAeq/LCpeak/1⁄3-octave, TLM frequency & modulation, flicker index).
- **Integrity by design:** per-minute chain hashes and optional Ed25519 signatures.
- **Privacy by default:** no speech, no images, no PII.

> **Base URL examples**  
> Local dev: `http://127.0.0.1:8000`  
> Cloud: your service origin (TBD)

---

## Versioning & Formats

- **API version:** `v1` (additive, backwards compatible where possible)
- **Content types:** `application/json`, `text/html`, `multipart/form-data`
- **Time:** ISO-8601 UTC with `Z`, e.g. `2025-09-12T10:04:00Z`

## Auth (optional but recommended)

Include a bearer token if your deployment requires authentication.

~~~
Authorization: Bearer <token>
~~~

## Idempotency (recommended)

Prevent accidental replays for uploads/evaluations by sending a unique key per request.

~~~
Idempotency-Key: <uuid-v4>
~~~

---

## Endpoints

### 1) Create a session

`POST /session` → **201 Created**

Create a new ingestion/evaluation session.

**Request**
~~~http
POST /session HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json
Authorization: Bearer <token>     # include if your deployment requires auth
~~~

**Response 201**
~~~json
{
  "session_id": "5e2a8f7c-2d0b-4b9f-9a69-4b9eb7bb2c3e",
  "expires_at": "2025-09-13T00:00:00Z",
  "upload_limits": { "max_bytes": 52428800 }
}
~~~

**Errors:** `401 Unauthorized`, `429 Too Many Requests`, `500`

---

### 2) Ingest JSONL (minute summaries)

`POST /session/{session_id}/ingest_jsonl` → **202 Accepted**

Upload newline-delimited JSON records (one minute per line).

**Request**
~~~http
POST /session/5e2a8f7c-.../ingest_jsonl HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: multipart/form-data; boundary=X-BOUNDARY-123456
Authorization: Bearer <token>
Idempotency-Key: 4c07c4f7-5f5e-4bb5-8f8c-0b6d9c0f2b5a

--X-BOUNDARY-123456
Content-Disposition: form-data; name="file"; filename="minutes.jsonl"
Content-Type: application/octet-stream

{"idx":0,"ts":"2025-09-12T10:04:00Z","audio":{"laeq_db":52.1,"lcpeak_db":64.0,"third_octave_db":{"125":58.0,"250":56.5,"500":54.0,"1000":52.0,"2000":51.2}},"light":{"tlm_freq_hz":120.0,"tlm_mod_percent":7.5,"flicker_index":0.06},"chain":{"hash":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}
{"idx":1,"ts":"2025-09-12T10:05:00Z","audio":{"laeq_db":53.0,"lcpeak_db":65.1,"third_octave_db":{"125":58.3,"250":56.7,"500":54.2,"1000":52.2,"2000":51.5}},"light":{"tlm_freq_hz":120.0,"tlm_mod_percent":7.6,"flicker_index":0.06},"chain":{"hash":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}}

--X-BOUNDARY-123456--
~~~

**Response 202**
~~~json
{
  "session_id": "5e2a8f7c-2d0b-4b9f-9a69-4b9eb7bb2c3e",
  "accepted_records": 480,
  "rejected_records": 0,
  "checks": {
    "schema": "ok",
    "chain_hash": "ok",
    "signatures": "ok" 
  }
}
~~~

**Errors:** `400 Bad Request` (malformed), `404 Not Found` (session), `409 Conflict` (idempotency mismatch), `413 Payload Too Large`, `422 Unprocessable Entity` (schema/signature), `500`

**Minute record (JSON) — required fields**
~~~json
{
  "idx": 0,
  "ts": "2025-09-12T10:04:00Z",
  "audio": {
    "laeq_db": 52.1,
    "lcpeak_db": 64.0,
    "third_octave_db": { "125": 58.0, "250": 56.5, "500": 54.0, "1000": 52.0, "2000": 51.2 }
  },
  "light": {
    "tlm_freq_hz": 120.0,
    "tlm_mod_percent": 7.5,
    "flicker_index": 0.06
  },
  "chain": {
    "hash": "<hex sha256 of (prev_hash || canonical_json(payload))>",
    "scheme": "ed25519",
    "signature_hex": "<hex>",
    "public_key_hex": "<64-hex raw pubkey>"
  }
}
~~~

- `idx`: 0-based minute index (monotonic).  
- `third_octave_db`: band-center Hz → level dB (keys as strings).  
- `chain.hash`: computed over payload **without** `chain` using canonical JSON. For `idx=0`, `prev_hash` is empty.  
- `scheme/signature`: optional but recommended. If absent, `signatures: "missing"`.

---

### 3) Evaluate against rules

`POST /session/{session_id}/evaluate` → **200 OK**

Submit a YAML rule set (WHO/IEEE thresholds, flags, rubric). Returns a results JSON.

**Request**
~~~http
POST /session/5e2a8f7c-.../evaluate HTTP/1.1
Host: 127.0.0.1:8000
Content-Type: application/json
Authorization: Bearer <token>     # optional
Idempotency-Key: 54f6b9b2-2b1c-4f1c-9ff0-7c2a13a9a7a2
~~~

**Body**
~~~json
{
  "rules_yaml": "profile: default\nwho_noise:\n  night_dba: 40\n  exceedance_pct: 10\nieee_1789:\n  low_risk_mod_percent_max: 8\n..."
}
~~~

**Response 200 (example)**
~~~json
{
  "session_id": "5e2a8f7c-2d0b-4b9f-9a69-4b9eb7bb2c3e",
  "summary": {
    "minutes_total": 480,
    "audio_flags": { "night_LAeq_exceed_10pct": true },
    "light_flags": { "tlm_above_low_risk": false }
  },
  "metrics": {
    "laeq_percentiles": { "p50": 51.8, "p90": 57.3 },
    "tlm_mod_percentiles": { "p50": 4.2, "p90": 7.9 }
  },
  "trace": {
    "profile_id": "inline@sha256:5b0e...",
    "rules_version": "v1.0.0"
  }
}
~~~

**Errors:** `400` (bad YAML), `404` (session), `422` (no minutes ingested), `500`

---

### 4) Fetch report (HTML or JSON)

`GET /session/{session_id}/report?public_key_hex=…` → **200 OK**

Render a tamper-evident audit report. If uploads were signed, pass the public key to display verification results inline.

**Request**
~~~http
GET /session/5e2a8f7c-.../report?public_key_hex=1a2b... HTTP/1.1
Host: 127.0.0.1:8000
Accept: text/html
~~~

**Response 200**
- `text/html` (default): human-readable report with plots, thresholds, flags, signature/chain summary.  
- `application/json`: JSON report (use `Accept: application/json`).

**Errors:** `404` (session), `406` (unsupported `Accept`), `500`

---

## JSONL Minute Schema (formal)

~~~json
{
  "type": "object",
  "required": ["idx", "ts", "audio", "light", "chain"],
  "properties": {
    "idx": { "type": "integer", "minimum": 0 },
    "ts":  { "type": "string", "format": "date-time" },
    "audio": {
      "type": "object",
      "required": ["laeq_db", "lcpeak_db", "third_octave_db"],
      "properties": {
        "laeq_db": { "type": "number" },
        "lcpeak_db": { "type": "number" },
        "third_octave_db": {
          "type": "object",
          "additionalProperties": { "type": "number" }
        }
      }
    },
    "light": {
      "type": "object",
      "required": ["tlm_freq_hz", "tlm_mod_percent", "flicker_index"],
      "properties": {
        "tlm_freq_hz": { "type": "number", "minimum": 0 },
        "tlm_mod_percent": { "type": "number", "minimum": 0 },
        "flicker_index": { "type": "number", "minimum": 0 }
      }
    },
    "chain": {
      "type": "object",
      "required": ["hash"],
      "properties": {
        "hash": { "type": "string", "pattern": "^[0-9a-f]{64}$" },
        "scheme": { "type": "string", "enum": ["ed25519", "sha256-demo"] },
        "signature_hex": { "type": "string" },
        "public_key_hex": { "type": "string" }
      }
    }
  },
  "additionalProperties": false
}
~~~

---

## Integrity & Verification

- **Chain hash:** For each minute *i*, compute `sha256(prev_hash || canonical_json(payload_without_chain))`. For minute 0, `prev_hash` is empty.  
- **Signatures:** Sign the domain-separated message  
  `b"avsafe:sign:v1" + canonical_json(payload_without_chain).encode("utf-8")` (Ed25519).  
  Include `scheme`, `signature_hex`, `public_key_hex` in `chain`.  
- The server verifies chain & signatures on ingest; results appear under `checks`.

**Python client snippet**
~~~python
from integrity.hash_chain import chain_hash, canonical_json
from integrity.signing import sign_payload

prev = None
payload = { "idx": 0, "ts": "2025-09-12T10:04:00Z", "audio": {...}, "light": {...} }
h = chain_hash(prev, payload)
sig = sign_payload(payload)
record = payload | {"chain": {"hash": h, **sig}}
~~~

---

## Examples (curl)

**Create session**
~~~bash
curl -s -X POST http://127.0.0.1:8000/session \
  -H 'Content-Type: application/json'
~~~

**Ingest JSONL**
~~~bash
curl -s -X POST \
  http://127.0.0.1:8000/session/5e2a8f7c-.../ingest_jsonl \
  -H 'Idempotency-Key: 4c07c4f7-...' \
  -F 'file=@minutes.jsonl'
~~~

**Evaluate**
~~~bash
curl -s -X POST \
  http://127.0.0.1:8000/session/5e2a8f7c-.../evaluate \
  -H 'Content-Type: application/json' \
  -d '{"rules_yaml":"profile: default\nwho_noise:\n  night_dba: 40\n..."}'
~~~

**Get report (HTML)**
~~~bash
curl -s -H 'Accept: text/html' \
  "http://127.0.0.1:8000/session/5e2a8f7c-.../report?public_key_hex=1a2b..."
~~~

---

## Error Envelope

All non-2xx responses return:
~~~json
{ "error": { "code": "string", "message": "human readable", "details": {} } }
~~~
Common codes: `bad_request`, `not_found`, `conflict`, `too_large`, `unprocessable`, `rate_limited`, `server_error`.

---

## Limits & Retention

- **Upload size:** default 50 MB (configurable)
- **Session TTL:** 24 h (configurable)
- **Storage:** descriptors & results only; **no raw audio/video** ever stored

---

## Security & Privacy

- **No PII** in minute summaries  
- **No raw content**; descriptors only  
- **Chain of custody:** chain hashes + optional Ed25519  
- **Threat model & Acceptable Use:** see `SECURITY.md` and `ACCEPTABLE_USE.md`

> **Last updated:** 2025-09-12
