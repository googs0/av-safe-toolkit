# AV-SAFE Toolkit — Makefile

# global config 
PY ?= python3

# video E2E config 
BUILD_DIR := build/e2e-video
ASSETS_DIR := tests/assets/video
FPS := 30
FLICKER := $(ASSETS_DIR)/avsafe_flicker_10hz_30fps_1min.mp4
CONST   := $(ASSETS_DIR)/avsafe_constant_30fps_1min.mp4
MINUTES := $(BUILD_DIR)/minutes.jsonl
FLAGS   := $(BUILD_DIR)/flags.jsonl
REPORT  := $(BUILD_DIR)/report.html
PROFILE := avsafe_descriptors/rules/profiles/who_ieee_profile.yaml

# cloud (local mode) config 
UVICORN     ?= uvicorn
BASE_URL    ?= http://127.0.0.1:8000
TOKEN       ?= devtoken
LABEL       ?= Local Test
DEVICE      ?= DEV-001

API_MODULE  ?= cloud.api_app:app
LOCAL_RUNNER?= cloud.local_runner
SIM_CLI     ?= -m avsafe_descriptors.cli.sim

# keep cloud minutes separate from video E2E outputs
C_BUILD     := build/cloud
C_MINUTES   := $(C_BUILD)/minutes.jsonl
C_MINUTES_GZ:= $(C_BUILD)/minutes.jsonl.gz
SIM_MINUTES ?= 5

# phony
.PHONY: e2e-video videos smoke-video test setup-dev clean clean-videos \
        cloud-help cloud-pip cloud-api-local cloud-api-local-bg cloud-kill-api \
        cloud-minutes cloud-upload cloud-runner cloud-e2e-local cloud-watch-local cloud-clean-local


# Video E2E: videos → minutes → flags → report
e2e-video: setup-dev videos
	@mkdir -p $(BUILD_DIR)
	@echo ">>> [1/3] Video → minute summaries"
	$(PY) -m avsafe_descriptors.cli.video_to_light \
		--in $(FLICKER) $(CONST) \
		--fps-override $(FPS) \
		--minute \
		--jsonl $(MINUTES)

	@echo ">>> [2/3] Rules (WHO/IEEE) → flags"
	@if [ -f "$(PROFILE)" ]; then \
		$(PY) -m avsafe_descriptors.cli.rules_run \
			--in $(MINUTES) \
			--profile $(PROFILE) \
			--out $(FLAGS); \
	else \
		echo "WARN: $(PROFILE) not found; writing empty flags for each minute"; \
		awk '{print "{\"idx\":0,\"flags\":[]}"}' $(MINUTES) > $(FLAGS); \
	fi

	@echo ">>> [3/3] Report → HTML"
	@set -e; \
	if $(PY) -m avsafe_descriptors.cli.report \
			--in $(MINUTES) \
			--flags $(FLAGS) \
			--out $(REPORT); then \
		echo "Report written: $(REPORT)"; \
	else \
		echo "WARN: report CLI not available; writing fallback HTML"; \
		( echo "<html><body><h1>AV-SAFE E2E (fallback)</h1><pre>"; \
		  head -n 5 $(MINUTES); \
		  echo "</pre></body></html>" ) > $(REPORT); \
	fi
	@echo ">>> Done. Outputs:"
	@echo "  - $(MINUTES)"
	@echo "  - $(FLAGS)"
	@echo "  - $(REPORT)"

videos:
	@echo ">>> Ensuring 1-minute sample videos (generated if missing)…"
	@mkdir -p $(ASSETS_DIR)
	@$(PY) - <<'PY'
import math, numpy as np
from pathlib import Path
try:
    import imageio.v3 as iio
except Exception:
    raise SystemExit("imageio not installed. Run: pip install -r requirements-dev.txt")
FPS = 30.0; SIZE = 64; SECONDS = 60
assets = Path("$(ASSETS_DIR)")
flick = assets / "avsafe_flicker_10hz_30fps_1min.mp4"
const = assets / "avsafe_constant_30fps_1min.mp4"
def make_sine(path):
    n = int(FPS*SECONDS); t = np.arange(n)/FPS; frames = []
    for ti in t:
        level = 0.5*(1 + 0.5*math.sin(2*math.pi*10.0*ti))
        frames.append(np.full((int(SIZE),int(SIZE),3), int(level*255), np.uint8))
    iio.imwrite(path, np.stack(frames), fps=int(FPS))
def make_const(path):
    n = int(FPS*SECONDS)
    frames = [np.full((int(SIZE),int(SIZE),3), 180, np.uint8) for _ in range(n)]
    iio.imwrite(path, np.stack(frames), fps=int(FPS))
if not flick.exists():
    print("  + generating", flick)
    make_sine(flick)
else:
    print("  = exists", flick)
if not const.exists():
    print("  + generating", const)
    make_const(const)
else:
    print("  = exists", const)
PY

smoke-video: videos
	@$(PY) tools/video_smoke.py $(FLICKER) --fps $(FPS)

test:
	pytest -q

setup-dev:
	@if [ -f requirements-dev.txt ]; then \
		pip install -r requirements-dev.txt; \
	else \
		echo "No requirements-dev.txt found. Skipping."; \
	fi

clean-videos:
	@echo ">>> Removing generated test videos in $(ASSETS_DIR)/"
	@find $(ASSETS_DIR) -maxdepth 1 -type f \
		\( -name 'avsafe_*.mp4' -o -name 'avsafe_*.gif' \) \
		-print -delete || true

clean: clean-videos
	@rm -rf $(BUILD_DIR)

# Cloud (LOCAL_MODE=1) one-liners — zero-cost local runs
cloud-help:
	@echo "Targets:"
	@echo "  make cloud-pip            # install cloud deps (local)"
	@echo "  make cloud-api-local      # run FastAPI locally (blocks; Ctrl+C to stop)"
	@echo "  make cloud-api-local-bg   # run FastAPI in background; writes .uvicorn.pid"
	@echo "  make cloud-kill-api       # kill background FastAPI"
	@echo "  make cloud-minutes        # generate $(SIM_MINUTES) simulated minutes → $(C_MINUTES_GZ)"
	@echo "  make cloud-upload         # create case, get URL, upload $(C_MINUTES_GZ)"
	@echo "  make cloud-runner         # run local pipeline once (verify -> rules -> report)"
	@echo "  make cloud-e2e-local      # simulate -> upload -> verify/rules -> report (one-shot)"
	@echo "  make cloud-watch-local    # watch for new uploads and process continuously"
	@echo "  make cloud-clean-local    # remove local_data/ and cloud build artifacts"

cloud-pip:
	$(PY) -m pip install -r cloud/requirements.txt

cloud-api-local:
	@echo "Starting FastAPI locally at $(BASE_URL) ..."
	@echo "ENV: LOCAL_MODE=1 AUTH_MODE=dev DEV_TOKEN=$(TOKEN)"
	LOCAL_MODE=1 AUTH_MODE=dev DEV_TOKEN=$(TOKEN) $(UVICORN) $(API_MODULE) --reload --port 8000

cloud-api-local-bg:
	@echo "Starting FastAPI in background (port 8000) ..."
	@echo "ENV: LOCAL_MODE=1 AUTH_MODE=dev DEV_TOKEN=$(TOKEN)"
	@bash -c 'LOCAL_MODE=1 AUTH_MODE=dev DEV_TOKEN="$(TOKEN)" \
		$(UVICORN) $(API_MODULE) --port 8000 --host 0.0.0.0 --reload >/dev/null 2>&1 & echo $$! > .uvicorn.pid; \
		echo "PID: $$(cat .uvicorn.pid)"'

cloud-kill-api:
	@if [ -f .uvicorn.pid ]; then kill `cat .uvicorn.pid` && rm .uvicorn.pid && echo "Stopped FastAPI."; else echo "No .uvicorn.pid."; fi

# Simulated minutes for cloud tests
$(C_BUILD):
	@mkdir -p $(C_BUILD)

$(C_MINUTES): | $(C_BUILD)
	@echo "Generating $(SIM_MINUTES) minutes to $(C_MINUTES) ..."
	$(PY) $(SIM_CLI) --minutes $(SIM_MINUTES) --outfile $(C_MINUTES)

$(C_MINUTES_GZ): $(C_MINUTES)
	@echo "Compressing $(C_MINUTES) -> $(C_MINUTES_GZ) ..."
	gzip -c $(C_MINUTES) > $(C_MINUTES_GZ)

cloud-minutes: $(C_MINUTES_GZ)
	@echo "OK: $(C_MINUTES_GZ)"

# Upload via tools/client_uploader.py
cloud-upload: cloud-minutes
	@echo "Uploading $(C_MINUTES_GZ) to $(BASE_URL) ..."
	$(PY) tools/client_uploader.py \
		--base $(BASE_URL) \
		--token $(TOKEN) \
		--label "$(LABEL)" \
		--device $(DEVICE) \
		--file $(C_MINUTES_GZ)

# Run the local pipeline once (verify -> rules -> report)
cloud-runner:
	LOCAL_MODE=1 $(PY) -m $(LOCAL_RUNNER) --once
	@echo "Open the generated HTML report(s) under local_data/avsafe-reports/reports/<CASE>/<TS>/report.html"

# One-shot end-to-end: simulate -> upload -> verify/rules -> report ---
cloud-e2e-local: cloud-minutes cloud-upload cloud-runner

# Continuous watcher (dev convenience)
cloud-watch-local:
	LOCAL_MODE=1 $(PY) -m $(LOCAL_RUNNER) --watch

# Clean local artifacts for cloud dev 
cloud-clean-local:
	rm -rf local_data/ $(C_BUILD) .uvicorn.pid || true
	@echo "Cleaned local_data and cloud build files."
