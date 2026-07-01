#!/bin/bash
# Run the KPI Streamlit app locally (Mac/Linux). Uses full Docling + OCR.
# For fast mode (tables only): use streamlit_app_openshift.py — see RUNBOOK.md.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/combined_soln:$SCRIPT_DIR/IB:$SCRIPT_DIR/PNB:$SCRIPT_DIR/HDFC"
if [[ -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  PYTHON="$SCRIPT_DIR/.venv/bin/python"
else
  PYTHON="python3"
fi
cd combined_soln
exec "$PYTHON" -m streamlit run streamlit_app.py --server.headless=false
