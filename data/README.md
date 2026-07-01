# Sample PDF inputs

Place investor and CASA quarterly PDFs here before running extractors locally. PDFs are **not** committed to Git (too large). Download from BSE or use your own copies.

## Expected filenames

| Bank | Investor presentation | CASA / financial numbers |
|------|----------------------|---------------------------|
| IB   | `IB_investor_PPT.pdf` | `IB_CASA_Numbers_PPT.pdf` |
| PNB  | `PNB_investor_PPT.pdf` | `PNB_CASA_Numbers_PPT.pdf` |
| HDFC | `HDFC_investor_PPT.pdf` | `HDFC_Bank_CASA.pdf` |

## Default BSE URLs (also in `combined_soln/bse_nse_input.txt`)

```text
# IB Investor
https://www.bseindia.com/xml-data/corpfiling/AttachHis/06fc511a-9d0e-43df-a830-13b9dea59cba.pdf
# IB CASA
https://www.bseindia.com/xml-data/corpfiling/AttachHis/7b26747e-1f53-4fc5-aa28-465e03617758.pdf
# PNB Investor
https://www.bseindia.com/xml-data/corpfiling/AttachHis/aedaff30-a173-45db-ac13-188e1257f05c.pdf
# PNB CASA
https://www.bseindia.com/xml-data/corpfiling/AttachHis/2e4de758-cbe7-4e01-82dd-7acca9ec9f2d.pdf
```

HDFC URLs can be pasted in the Streamlit app or notebook when available.

## Optional assets (PNB OCR fallbacks)

These PNGs support PNB ratio extraction when table OCR is weak:

- `PNB_efficiency_ratios.png`
- `PNB_performance_highlights.png`
- `PNB_slippages_recoveries.png`

## Quick download (macOS/Linux)

Use the script (includes BSE Referer headers — plain `curl` often returns HTML):

```bash
./scripts/download_pdfs.sh
# or: make download
```

Manual curl with headers:

```bash
mkdir -p data
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
curl -fsSL -H "User-Agent: $UA" -H "Referer: https://www.bseindia.com/" \
  -o data/IB_investor_PPT.pdf \
  "https://www.bseindia.com/xml-data/corpfiling/AttachHis/06fc511a-9d0e-43df-a830-13b9dea59cba.pdf"
# … repeat for other URLs in the table above, or use download_pdfs.sh
```

Add HDFC PDFs manually when you have the links or files:

| File | Notes |
|------|-------|
| `HDFC_investor_PPT.pdf` | Required for HDFC CLI test (`python HDFC/export_to_csv.py`) |
| `HDFC_Bank_CASA.pdf` | Required for 3-bank Streamlit/CLI report |

There are no default HDFC BSE URLs in `combined_soln/bse_nse_input.txt` yet — paste URLs in the Streamlit app when available.
