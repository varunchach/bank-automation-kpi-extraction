#!/usr/bin/env bash
# Quick smoke test: extract IB KPIs from data/ PDFs (~2–5 min first run).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate
export PYTHONPATH="$ROOT:$ROOT/IB:$ROOT/PNB:$ROOT/HDFC:$ROOT/combined_soln"
echo "Running IB extraction smoke test (Docling + OCR) ..."
python IB/run_extraction.py --json | head -c 2000
echo ""
echo ""
echo "Smoke test finished. If you see JSON with Business, Deposits, Net_Profit — setup works."
