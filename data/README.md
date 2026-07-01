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

```bash
mkdir -p data
curl -L -o data/IB_investor_PPT.pdf "https://www.bseindia.com/xml-data/corpfiling/AttachHis/06fc511a-9d0e-43df-a830-13b9dea59cba.pdf"
curl -L -o data/IB_CASA_Numbers_PPT.pdf "https://www.bseindia.com/xml-data/corpfiling/AttachHis/7b26747e-1f53-4fc5-aa28-465e03617758.pdf"
curl -L -o data/PNB_investor_PPT.pdf "https://www.bseindia.com/xml-data/corpfiling/AttachHis/aedaff30-a173-45db-ac13-188e1257f05c.pdf"
curl -L -o data/PNB_CASA_Numbers_PPT.pdf "https://www.bseindia.com/xml-data/corpfiling/AttachHis/2e4de758-cbe7-4e01-82dd-7acca9ec9f2d.pdf"
```

Add HDFC PDFs manually when you have the links or files.
