#!/usr/bin/env bash
# Run ONNX export on remote server (ovh). Usage:
#   ./scripts/run_export_on_ovh.sh
# Requires: SSH config "ovh", rsync, and project at PROJECT_ROOT.
# Uses uv on the server for fast dependency install (no long pip backtracking).
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REMOTE_DIR="~/auto_chess_export"

echo "[export] Syncing project to ovh:$REMOTE_DIR ..."
rsync -az --delete \
  --exclude '.venv' --exclude '__pycache__' --exclude '.git' \
  --exclude 'onnx_models' --exclude '_chesscog_src' \
  "$PROJECT_ROOT/" "ovh:$REMOTE_DIR/"

echo "[export] Running export on ovh (using uv) ..."
ssh ovh 'export PATH="$HOME/.local/bin:$PATH"; \
  command -v uv >/dev/null 2>&1 || (curl -LsSf https://astral.sh/uv/install.sh | sh); \
  cd '"$REMOTE_DIR"' && \
  uv venv .venv --python 3.10 2>/dev/null || uv venv .venv --python python3; \
  uv pip install --python .venv/bin/python torch torchvision; \
  uv pip install --python .venv/bin/python "chesscog @ git+https://github.com/georg-wolflein/chesscog.git" --no-deps; \
  uv pip install --python .venv/bin/python recap tqdm requests opencv-python-headless python-chess scikit-learn matplotlib pandas onnxscript "googledrivedownloader==0.4"; \
  (rm -rf _chesscog_src; git clone --depth 1 https://github.com/georg-wolflein/chesscog.git _chesscog_src) && cp -r _chesscog_src/config .venv/lib/python3.10/site-packages/; \
  .venv/bin/python -m chesscog.occupancy_classifier.download_model; \
  .venv/bin/python -m chesscog.piece_classifier.download_model; \
  .venv/bin/python scripts/export_chesscog_to_onnx.py'

echo "[export] Syncing onnx_models/ back to $PROJECT_ROOT/onnx_models ..."
mkdir -p "$PROJECT_ROOT/onnx_models"
rsync -az "ovh:$REMOTE_DIR/onnx_models/" "$PROJECT_ROOT/onnx_models/"

echo "[export] Done. You can run setup locally (will use ONNX and skip PyTorch)."
