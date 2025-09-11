# API (Receiver)
- `POST /session` → `{ session_id }`
- `POST /session/{session_id}/ingest_jsonl` (multipart file)
- `POST /session/{session_id}/evaluate` (body: `{ rules_yaml }`)
- `GET /session/{session_id}/report?public_key_hex=...` → HTML report
