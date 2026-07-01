#!/usr/bin/env bash
# Check that the environment is ready to run extractors / Streamlit.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PASS=0
FAIL=0
WARN=0

ok()   { echo "  ✓ $1"; PASS=$((PASS + 1)); }
bad()  { echo "  ✗ $1"; FAIL=$((FAIL + 1)); }
warn() { echo "  ! $1"; WARN=$((WARN + 1)); }

echo "=== Bank KPI Extraction — setup verification ==="
echo ""

# Python
echo "[1] Python"
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
  ok "Virtualenv found: .venv"
else
  PY=""
  bad "No .venv — run: make setup"
fi

if [ -n "$PY" ]; then
  VER=$("$PY" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
  if [ "$VER" = "3.11" ]; then
    ok "Python $VER"
  elif [ "$VER" = "3.12" ] || [ "$VER" = "3.13" ]; then
    warn "Python $VER (3.11 recommended)"
  else
    bad "Python $VER — use 3.11.x (3.14+ breaks Docling OCR). Run: make clean-venv && make setup"
  fi
fi
echo ""

# Packages
echo "[2] Python packages"
if [ -n "$PY" ]; then
  for pkg in torch docling streamlit pandas; do
    if "$PY" -m pip show "$pkg" >/dev/null 2>&1; then
      ver=$("$PY" -m pip show "$pkg" 2>/dev/null | awk -F': ' '/^Version:/{print $2; exit}' || true)
      ok "$pkg installed (${ver:-unknown version})"
    else
      bad "$pkg missing — run: make setup"
    fi
  done
fi
echo ""

# PDFs
echo "[3] Data files (data/)"
need_ib_pnb=true
for f in IB_investor_PPT.pdf IB_CASA_Numbers_PPT.pdf PNB_investor_PPT.pdf PNB_CASA_Numbers_PPT.pdf; do
  if [ -f "data/$f" ] && file "data/$f" | grep -qi pdf; then
    ok "data/$f"
  else
    bad "data/$f missing — run: ./scripts/download_pdfs.sh"
    need_ib_pnb=false
  fi
done
for f in HDFC_investor_PPT.pdf HDFC_Bank_CASA.pdf; do
  if [ -f "data/$f" ] && file "data/$f" | grep -qi pdf; then
    ok "data/$f (optional 3-bank)"
  else
    warn "data/$f missing (optional — needed for HDFC CLI / 3-bank report)"
  fi
done
echo ""

# Config
echo "[4] Optional chatbot config"
if [ -n "${LLM_API_KEY:-}" ] || [ -n "${TAVILY_API_KEY:-}" ]; then
  ok "LLM/Tavily env vars set"
else
  warn "No LLM/Tavily keys — KPI extraction works; chat tab needs keys (see GETTING_STARTED.md Step 5)"
fi
echo ""

echo "=== Summary: $PASS passed, $FAIL failed, $WARN warnings ==="
if [ "$FAIL" -gt 0 ]; then
  echo "Fix failures above, then re-run: ./scripts/verify_setup.sh"
  exit 1
fi
echo "Ready. Next: ./run_local.sh  →  http://localhost:8501"
exit 0
