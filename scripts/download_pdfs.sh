#!/usr/bin/env bash
# Download IB + PNB sample PDFs from BSE into data/
# Uses browser-like headers (same as Streamlit) to reduce 403 errors.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA="$ROOT/data"
mkdir -p "$DATA"

UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HDR=(-H "User-Agent: $UA" -H "Accept: application/pdf,*/*" -H "Referer: https://www.bseindia.com/" -H "Origin: https://www.bseindia.com")

download_one() {
  local url="$1"
  local dest="$2"
  local label="$3"
  echo "→ Downloading $label ..."
  curl -fsSL "${HDR[@]}" -o "$dest" "$url"
  if ! file "$dest" | grep -qi pdf; then
    echo "ERROR: $dest is not a PDF (BSE may have returned HTML). Delete it and try again or copy PDF manually."
    file "$dest"
    exit 1
  fi
  local size
  size=$(wc -c < "$dest" | tr -d ' ')
  if [ "$size" -lt 100000 ]; then
    echo "ERROR: $dest is too small (${size} bytes). Likely a failed download."
    exit 1
  fi
  echo "  OK: $(basename "$dest") ($(numfmt --to=iec "$size" 2>/dev/null || echo "${size} bytes"))"
}

download_one \
  "https://www.bseindia.com/xml-data/corpfiling/AttachHis/06fc511a-9d0e-43df-a830-13b9dea59cba.pdf" \
  "$DATA/IB_investor_PPT.pdf" "IB Investor"

download_one \
  "https://www.bseindia.com/xml-data/corpfiling/AttachHis/7b26747e-1f53-4fc5-aa28-465e03617758.pdf" \
  "$DATA/IB_CASA_Numbers_PPT.pdf" "IB CASA"

download_one \
  "https://www.bseindia.com/xml-data/corpfiling/AttachHis/aedaff30-a173-45db-ac13-188e1257f05c.pdf" \
  "$DATA/PNB_investor_PPT.pdf" "PNB Investor"

download_one \
  "https://www.bseindia.com/xml-data/corpfiling/AttachHis/2e4de758-cbe7-4e01-82dd-7acca9ec9f2d.pdf" \
  "$DATA/PNB_CASA_Numbers_PPT.pdf" "PNB CASA"

echo ""
echo "IB + PNB PDFs ready in data/"
echo "HDFC: copy HDFC_investor_PPT.pdf and HDFC_Bank_CASA.pdf into data/ manually (see data/README.md)"
