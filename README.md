# Bank Automation — KPI Extraction

Automated extraction of **46 standardized KPIs** from public bank investor presentations and CASA/financial PDFs, with side-by-side comparison, ranking, Excel export, and an optional RAG chatbot (Milvus + LLM + web search + Yahoo Finance).

**Supported banks:** IB, PNB, HDFC (each uses 2 PDFs: investor PPT + CASA numbers).

Repository: [github.com/varunchach/bank-automation-kpi-extraction](https://github.com/varunchach/bank-automation-kpi-extraction)

---

## Table of contents

1. [What this project does](#1-what-this-project-does)
2. [Architecture](#2-architecture)
3. [Repository layout](#3-repository-layout)
4. [Prerequisites](#4-prerequisites)
5. [Step-by-step local setup](#5-step-by-step-local-setup)
6. [Running extractors per bank](#6-running-extractors-per-bank)
7. [Unified report (IB + PNB + HDFC)](#7-unified-report-ib--pnb--hdfc)
8. [Streamlit app (UI)](#8-streamlit-app-ui)
9. [Configuration (LLM & Tavily)](#9-configuration-llm--tavily)
10. [Docker & OpenShift deploy](#10-docker--openshift-deploy)
11. [KPI list (46 keys)](#11-kpi-list-46-keys)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. What this project does

| Step | Description |
|------|-------------|
| **Ingest** | Load PDFs from `data/` or BSE URLs (Streamlit download) |
| **Parse** | [Docling](https://github.com/DS4SD/docling) converts PDFs to tables + markdown (full-page OCR, scale 2.0) |
| **Extract** | Bank-specific Python extractors map table rows to 46 KPI keys + YoY growth % |
| **Compare** | `build_report_df()` builds IB vs PNB vs HDFC report with ranks |
| **Export** | CSV/Excel; optional reference JSON validation in `reference_kpis/` |
| **Chat** | RAG over PDF text (Milvus Lite) + Tavily web search + Yahoo Finance symbols |

---

## 2. Architecture

```
PDF inputs (IB, PNB, HDFC inv + CASA)
    → Docling (tables + markdown)
    → Bank extractors (IB/, PNB/, HDFC/)
    → kpi_report_format.build_report_df()
    → Streamlit UI + Excel + RAG chatbot
```

---

## 3. Repository layout

```
├── IB/                    # IB extractor (kpi_extractor.py)
├── PNB/                   # PNB extractor (pnb_extractor.py)
├── HDFC/                  # HDFC extractor (hdfc_extractor.py)
├── combined_soln/         # Streamlit app, report format, RAG, ranking
├── data/                  # PDFs (gitignored) — see data/README.md
├── reference_kpis/        # Optional reference JSON for validation
├── extracted_output/      # Generated CSV (gitignored)
├── openshift/             # OpenShift manifests
├── requirements.txt
├── run_local.sh
└── RUNBOOK.md
```

**Not in Git:** `.venv/`, large PDFs, duplicate downloads, secrets, `__pycache__/`.

---

## 4. Prerequisites

| Requirement | Notes |
|-------------|-------|
| Python | 3.11+ |
| RAM | 8 GB+ (Docling OCR) |
| Optional | CUDA GPU or Apple MPS |
| Chatbot | LLM endpoint + Tavily API key |

---

## 5. Step-by-step local setup

### Step 1 — Clone

```bash
git clone https://github.com/varunchach/bank-automation-kpi-extraction.git
cd bank-automation-kpi-extraction
```

### Step 2 — Virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3 — Download PDFs into `data/`

See **[data/README.md](data/README.md)** for filenames and BSE URLs.

```bash
mkdir -p data
curl -L -o data/IB_investor_PPT.pdf "https://www.bseindia.com/xml-data/corpfiling/AttachHis/06fc511a-9d0e-43df-a830-13b9dea59cba.pdf"
curl -L -o data/IB_CASA_Numbers_PPT.pdf "https://www.bseindia.com/xml-data/corpfiling/AttachHis/7b26747e-1f53-4fc5-aa28-465e03617758.pdf"
curl -L -o data/PNB_investor_PPT.pdf "https://www.bseindia.com/xml-data/corpfiling/AttachHis/aedaff30-a173-45db-ac13-188e1257f05c.pdf"
curl -L -o data/PNB_CASA_Numbers_PPT.pdf "https://www.bseindia.com/xml-data/corpfiling/AttachHis/2e4de758-cbe7-4e01-82dd-7acca9ec9f2d.pdf"
```

Add `HDFC_investor_PPT.pdf` and `HDFC_Bank_CASA.pdf` when available.

### Step 4 — LLM / Tavily (optional)

```bash
cp combined_soln/llm_config.example.py combined_soln/llm_config.py
export LLM_BASE_URL="https://your-endpoint/v1"
export LLM_API_KEY="your-key"
export LLM_MODEL="your-model"
export TAVILY_API_KEY="your-tavily-key"
```

### Step 5 — Quick test (HDFC CSV export)

```bash
python HDFC/export_to_csv.py
# → extracted_output/hdfc_extracted.csv
```

### Step 6 — Start Streamlit

```bash
chmod +x run_local.sh
./run_local.sh
```

Open **http://localhost:8501**.

---

## 6. Running extractors per bank

**IB:** `IB/extract_tables.ipynb` or `python IB/run_extraction.py --json`

**PNB:** `PNB/PNB_extract_tables.ipynb`

**HDFC:** `python HDFC/export_to_csv.py` or `HDFC/HDFC_extract_tables.ipynb`

Example (Python):

```python
from pathlib import Path
from HDFC.hdfc_extractor import HDFCKPIExtractor
kpis = HDFCKPIExtractor(
    Path("data/HDFC_investor_PPT.pdf"),
    Path("data/HDFC_Bank_CASA.pdf"),
).extract()
```

---

## 7. Unified report (IB + PNB + HDFC)

Notebook: `combined_soln/unified_kpi_notebook.ipynb`

```python
from IB.kpi_extractor import IndianBankKPIExtractor
from PNB.pnb_extractor import PNBKPIExtractor
from HDFC.hdfc_extractor import HDFCKPIExtractor
from kpi_ranking import compute_rank
from kpi_report_format import build_report_df

kpis_ib = IndianBankKPIExtractor("data/IB_investor_PPT.pdf", "data/IB_CASA_Numbers_PPT.pdf").extract()
kpis_pnb = PNBKPIExtractor("data/PNB_investor_PPT.pdf", "data/PNB_CASA_Numbers_PPT.pdf", data_dir="data").extract()
kpis_hdfc = HDFCKPIExtractor("data/HDFC_investor_PPT.pdf", "data/HDFC_Bank_CASA.pdf").extract()
df = build_report_df(kpis_ib, kpis_pnb, compute_rank, kpis_hdfc=kpis_hdfc)
```

---

## 8. Streamlit app (UI)

| Mode | Command |
|------|---------|
| Full OCR (local) | `./run_local.sh` |
| Fast (tables only) | See RUNBOOK.md |

Paste BSE URLs, download PDFs, extract KPIs, export Excel, use chat tab for KPIs/news/stocks (`INDIANB.NS`, `PNB.NS`, `HDFCBANK.NS`).

---

## 9. Configuration (LLM & Tavily)

| Variable | Purpose |
|----------|---------|
| `LLM_BASE_URL` | Chat completions endpoint |
| `LLM_API_KEY` | LLM API key |
| `LLM_MODEL` | Model id |
| `TAVILY_API_KEY` | Web search |

KPI extraction works without these; chatbot needs them.

---

## 10. Docker & OpenShift deploy

See **[RUNBOOK.md](RUNBOOK.md)** for image build and `./deploy_openshift_new.sh cpu|gpu`.

---

## 11. KPI list (46 keys)

Shared schema: `Business`, `Deposits`, `CASA_Pct_Domestic`, `Gross_Advances`, `Gross_NPA_Amount`, `Operating_Profit`, `Net_Profit`, `RoE_Pct`, `NIM_Global`, etc. See `ALL_KPI_KEYS` in `IB/kpi_extractor.py`.

---

## 12. Troubleshooting

| Issue | Fix |
|-------|-----|
| Missing `docling` | `pip install -r requirements.txt` in venv |
| Empty KPIs | Use full OCR mode; verify PDF quarter |
| BSE 403 | Manual PDF download to `data/` |
| Slow extraction | 1–3 min/PDF on CPU is normal |
| Chatbot errors | Set LLM and Tavily env vars |
