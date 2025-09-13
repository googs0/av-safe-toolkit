#!/usr/bin/env bash
set -euo pipefail

echo ">>> AV-SAFE sanity smoke test"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Enforce real crypto in this run
export AVSAFE_STRICT_CRYPTO=1

SCHEMA="avsafe_descriptors/hf_avc/schemas/case_schema_v1.json"
CASES_GLOB="avsafe_descriptors/hf_avc/cases/*.json"
PROFILE="avsafe_descriptors/rules/profiles/who_ieee_profile.yaml"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

step() { echo; echo ">>> $*"; }

step "Step 1: Unit tests"
pytest -q

step "Step 2: Corpus schema validation"
# Support both module paths (with or without shim)
if python - <<'PY' 2>/dev/null; then
import importlib; importlib.import_module("avsafe_descriptors.hf_avc.validate_cases"); print("ok")
PY
then
  python -m avsafe_descriptors.hf_avc.validate_cases --schema "$SCHEMA" --cases "$CASES_GLOB"
else
  python -m avsafe_descriptors.cli.validate_cases_v1 --schema "$SCHEMA" --cases "$CASES_GLOB"
fi

step "Step 3: Simulate minutes (signed)"
avsafe-sim --minutes 30 --outfile "$TMP/minutes.jsonl" --sign

step "Step 4: Evaluate rules"
avsafe-rules-run \
  --minutes "$TMP/minutes.jsonl" \
  --profile "$PROFILE" \
  --locale "munich" \
  --out "$TMP/results.json"

step "Step 5: Generate HTML report"
avsafe-report --minutes "$TMP/minutes.jsonl" --results "$TMP/results.json" --out "$TMP/report.html"
cp "$TMP/report.html" ./report.html

step "Step 6: API smoke (openapi, create session, ingest, render report)"
uvicorn avsafe_descriptors.server.app:app --host 127.0.0.1 --port 8000 >"$TMP/uvicorn.log" 2>&1 &
UV_PID=$!
sleep 2
curl -fsS http://127.0.0.1:8000/openapi.json >/dev/null

# Create session
curl -fsS -X POST http://127.0.0.1:8000/session -F "name=smoke" -o "$TMP/sess.json"
SID="$(python - <<'PY' "$TMP/sess.json"
import json,sys; print(json.load(open(sys.argv[1]))["session_id"])
PY
)"

# Ingest minutes and request report
curl -fsS -X POST "http://127.0.0.1:8000/session/$SID/ingest_jsonl" -F "file=@$TMP/minutes.jsonl" >/dev/null
curl -fsS "http://127.0.0.1:8000/session/$SID/report" -o "$TMP/report_from_api.html" || {
  echo "Report fetch failed; see $TMP/uvicorn.log" >&2; kill $UV_PID || true; exit 1;
}
kill $UV_PID || true

echo
echo "✅ Smoke test passed. Good to go."
echo "Artifacts:"
echo "  - ./report.html (local renderer)"
echo "  - $TMP/report_from_api.html (server renderer)"
