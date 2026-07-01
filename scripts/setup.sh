#!/usr/bin/env bash
# One-shot local setup: venv + PyTorch + requirements + sample PDFs.
# Usage (from repo root):  make setup   OR   ./scripts/setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== Bank KPI Extraction — setup ==="
echo "Repo: $ROOT"
echo ""

PY=$("$ROOT/scripts/find_python311.sh")
echo "Using: $PY ($($PY --version))"

# Recreate venv if it was built with the wrong Python minor version
if [ -d ".venv" ]; then
  existing=$(".venv/bin/python" -c "import sys; print(sys.version_info.minor)" 2>/dev/null || echo "?")
  if [ "$existing" != "11" ]; then
    echo ""
    echo "Removing .venv (Python 3.$existing detected — need 3.11 for Docling OCR)"
    rm -rf .venv
  fi
fi

if [ ! -d ".venv" ]; then
  echo ""
  echo "[1/4] Creating virtualenv .venv ..."
  "$PY" -m venv .venv
else
  echo ""
  echo "[1/4] Virtualenv .venv already exists (Python 3.11)"
fi
source .venv/bin/activate

echo "[2/4] Upgrading pip ..."
python -m pip install --upgrade pip -q

echo "[3/4] Installing PyTorch (CPU) then requirements (5–15 min first time) ..."
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu -q
pip install -r requirements.txt -q

echo "[4/4] Downloading IB + PNB sample PDFs ..."
chmod +x scripts/download_pdfs.sh scripts/verify_setup.sh scripts/smoke_test.sh scripts/find_python311.sh 2>/dev/null || true
./scripts/download_pdfs.sh

echo ""
echo "=== Setup complete ==="
echo ""
./scripts/verify_setup.sh
