# Quickstart
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
pip install -r requirements-dev.txt

# simulate minutes
avsafe-sim --minutes 120 --outfile minutes.jsonl --sign

# evaluate rules
avsafe-rules-run --minutes minutes.jsonl   --profile avsafe_descriptors/rules/profiles/who_ieee_profile.yaml   --locale munich --out results.json

# report
avsafe-report --minutes minutes.jsonl --results results.json --out report.html
```

## Server
```bash
uvicorn avsafe_descriptors.server.app:app --reload --port 8000
```
