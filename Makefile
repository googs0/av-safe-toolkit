# ---------- config ----------
PY ?= python3
BUILD_DIR := build/e2e-video
ASSETS_DIR := tests/assets/video
FPS := 30
FLICKER := $(ASSETS_DIR)/avsafe_flicker_10hz_30fps_1min.mp4
CONST   := $(ASSETS_DIR)/avsafe_constant_30fps_1min.mp4
MINUTES := $(BUILD_DIR)/minutes.jsonl
FLAGS   := $(BUILD_DIR)/flags.jsonl
REPORT  := $(BUILD_DIR)/report.html
PROFILE := avsafe_descriptors/rules/profiles/who_ieee_profile.yaml

# ---------- phony ----------
.PHONY: e2e-video videos smoke-video test setup-dev clean clean-videos

# End-to-end: videos -> minutes.jsonl -> flags.jsonl -> report.html
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

# Create 1-minute sample videos if missing (10 Hz flicker + constant control)
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

# Quick manual smoke using your helper script
smoke-video: videos
	@$(PY) tools/video_smoke.py $(FLICKER) --fps $(FPS)

# Run the full pytest suite (includes e2e video pipeline test)
test:
	pytest -q

# Install dev deps (imageio, imageio-ffmpeg, pytest, etc.)
setup-dev:
	@if [ -f requirements-dev.txt ]; then \
		pip install -r requirements-dev.txt; \
	else \
		echo "No requirements-dev.txt found. Skipping."; \
	fi

# Remove generated test videos (safe; only files we generate)
clean-videos:
	@echo ">>> Removing generated test videos in $(ASSETS_DIR)/"
	@find $(ASSETS_DIR) -maxdepth 1 -type f \
		\( -name 'avsafe_*.mp4' -o -name 'avsafe_*.gif' \) \
		-print -delete || true

# Clean build artifacts (and generated videos)
clean: clean-videos
	@rm -rf $(BUILD_DIR)
