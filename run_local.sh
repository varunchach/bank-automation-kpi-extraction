#!/bin/bash
# Run the KPI Streamlit app locally (Mac/Linux). Uses full Docling + OCR.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
export PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/combined_soln:$SCRIPT_DIR/IB:$SCRIPT_DIR/PNB:$SCRIPT_DIR/HDFC"
if [[ ! -x "$SCRIPT_DIR/.venv/bin/python" ]]; then
  echo "ERROR: No .venv found. Run: make setup"
  exit 1
fi
PYTHON="$SCRIPT_DIR/.venv/bin/python"
minor=$("$PYTHON" -c "import sys; print(sys.version_info.minor)")
if [[ "$minor" != "11" ]]; then
  echo "ERROR: .venv uses Python 3.$minor — need 3.11 for Docling OCR."
  echo "Fix: make clean-venv && make setup"
  exit 1
fi
cd combined_soln
exec "$PYTHON" -m streamlit run streamlit_app.py --server.headless=false
