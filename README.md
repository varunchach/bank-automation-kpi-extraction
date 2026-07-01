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
6. [Verify the install works](#6-verify-the-install-works)
7. [Streamlit app — full UI walkthrough](#7-streamlit-app--full-ui-walkthrough)
8. [Running extractors per bank (CLI / notebooks)](#8-running-extractors-per-bank-cli--notebooks)
9. [Unified report (IB + PNB + HDFC)](#9-unified-report-ib--pnb--hdfc)
10. [Configuration (LLM & Tavily)](#10-configuration-llm--tavily)
11. [Docker & OpenShift deploy](#11-docker--openshift-deploy)
12. [KPI list (46 keys)](#12-kpi-list-46-keys)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. What this project does

| Step | Description |
|------|-------------|
| **Ingest** | PDFs from `data/` (CLI) or BSE URLs pasted in Streamlit |
| **Parse** | [Docling](https://github.com/DS4SD/docling) → tables + markdown (full-page OCR, scale 2.0) |
| **Extract** | Bank extractors (`IB/`, `PNB/`, `HDFC/`) → 46 KPI keys + YoY growth % where applicable |
| **Compare** | `build_report_df()` → ranked report (IB · PNB · optional HDFC) |
| **Export** | CSV / Excel; optional validation vs `reference_kpis/*.json` |
| **Chat** | RAG (Milvus Lite) + Tavily web search + Yahoo Finance (`INDIANB.NS`, `PNB.NS`, `HDFCBANK.NS`) |

**Two ways to run:**

| Path | When to use |
|------|-------------|
| **Streamlit** (`./run_local.sh`) | End-to-end: download PDFs from URLs → extract → report → chat |
| **CLI / notebooks** | Single-bank testing, debugging extractors, CSV export |

---

## 2. Architecture

```
PDF inputs (IB, PNB, HDFC — investor + CASA each)
    → Docling (tables + markdown, OCR on first run downloads models)
    → IB/kpi_extractor.py | PNB/pnb_extractor.py | HDFC/hdfc_extractor.py
    → combined_soln/kpi_report_format.build_report_df()
    → Streamlit UI | Excel | RAG chatbot
```

---

## 3. Repository layout

```
├── IB/                         # IB extractor
│   ├── kpi_extractor.py
│   ├── extract_tables.ipynb
│   └── run_extraction.py       # CLI
├── PNB/
│   ├── pnb_extractor.py
│   └── PNB_extract_tables.ipynb
├── HDFC/
│   ├── hdfc_extractor.py
│   ├── export_to_csv.py        # CLI → extracted_output/hdfc_extracted.csv
│   ├── HDFC_extract_tables.ipynb
│   └── discovery_hdfc_tables.ipynb
├── combined_soln/
│   ├── streamlit_app.py        # Main UI
│   ├── streamlit_app_openshift.py  # Fast mode (tables-only Docling)
│   ├── kpi_report_format.py
│   ├── kpi_ranking.py
│   ├── rag_milvus.py
│   ├── bse_nse_input.txt       # Default BSE PDF URLs (up to 6 lines)
│   ├── llm_config.example.py
│   └── unified_kpi_notebook.ipynb
├── data/                       # Local PDFs (gitignored) — see data/README.md
├── reference_kpis/             # ib.json, pnb.json, hdfc.json
├── extracted_output/           # Generated CSV (gitignored)
├── requirements.txt
├── run_local.sh
└── RUNBOOK.md
```

**Not committed to Git:** `.venv/`, `data/*.pdf`, `__pycache__/`, secrets, runtime downloads.

---

## 4. Prerequisites

| Requirement | Details |
|-------------|---------|
| **Python** | **3.11.x strongly recommended** (matches Dockerfile). Avoid 3.14+ for now — Docling/RapidOCR may fail on newest Python. |
| **OS** | macOS or Linux (Windows: use WSL2) |
| **RAM** | 8 GB minimum; 16 GB recommended for 4–6 PDFs |
| **Disk** | ~2 GB for venv + Docling/OCR models (downloaded on first extraction) |
| **Network** | Required for `pip install`, BSE PDF download, and optional LLM/Tavily |
| **Time (first run)** | `pip install`: 5–15 min · First Docling run: downloads OCR models · Full report: **10–20 min on CPU** (4 PDFs) |

Optional: CUDA GPU or Apple MPS speeds Docling; chatbot needs LLM endpoint + Tavily API key.

---

## 5. Step-by-step local setup

All commands assume you are at the **repository root** (folder containing `run_local.sh`).

### Step 1 — Clone

```bash
git clone https://github.com/varunchach/bank-automation-kpi-extraction.git
cd bank-automation-kpi-extraction
```

### Step 2 — Virtual environment + dependencies

Use **Python 3.11** if available:

```bash
# Prefer 3.11 (recommended)
python3.11 -m venv .venv
# Or: python3 -m venv .venv   (must be 3.11.x)

source .venv/bin/activate          # Windows (WSL): source .venv/bin/activate
python -m pip install --upgrade pip

# Install PyTorch CPU first (same order as Dockerfile — avoids Docling/OCR issues)
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu

pip install -r requirements.txt
```

Expected: no errors; `pip show docling streamlit` prints versions.

### Step 3 — PDF inputs

PDFs are **not in Git**. You need them for CLI/notebook runs. Streamlit can download from URLs instead (Step 7).

#### Option A — Download IB + PNB from BSE (curl)

```bash
mkdir -p data
curl -L -o data/IB_investor_PPT.pdf \
  "https://www.bseindia.com/xml-data/corpfiling/AttachHis/06fc511a-9d0e-43df-a830-13b9dea59cba.pdf"
curl -L -o data/IB_CASA_Numbers_PPT.pdf \
  "https://www.bseindia.com/xml-data/corpfiling/AttachHis/7b26747e-1f53-4fc5-aa28-465e03617758.pdf"
curl -L -o data/PNB_investor_PPT.pdf \
  "https://www.bseindia.com/xml-data/corpfiling/AttachHis/aedaff30-a173-45db-ac13-188e1257f05c.pdf"
curl -L -o data/PNB_CASA_Numbers_PPT.pdf \
  "https://www.bseindia.com/xml-data/corpfiling/AttachHis/2e4de758-cbe7-4e01-82dd-7acca9ec9f2d.pdf"
```

**Verify downloads** (each file should be a PDF, typically 2–10 MB):

```bash
file data/*.pdf
ls -lh data/*.pdf
```

If `file` says `HTML` or size is tiny (~5 KB), BSE blocked the request — copy PDFs manually into `data/` or use Streamlit download (browser-like headers).

#### Option B — HDFC PDFs (required for HDFC CLI test & 3-bank report)

Place these files in `data/`:

| File | Purpose |
|------|---------|
| `HDFC_investor_PPT.pdf` | Investor presentation |
| `HDFC_Bank_CASA.pdf` | CASA / financial numbers |

Obtain from your internal share / BSE filings / team drive. There is no default public BSE URL in `bse_nse_input.txt` yet — paste HDFC URLs in Streamlit when you have them.

See also **[data/README.md](data/README.md)**.

### Step 4 — LLM / Tavily (optional — chatbot only)

KPI extraction **does not** need these. Chat tab does.

```bash
cp combined_soln/llm_config.example.py combined_soln/llm_config.py
# Edit llm_config.py OR export env vars:
export LLM_BASE_URL="https://your-endpoint/v1"
export LLM_API_KEY="your-key"
export LLM_MODEL="your-model"
export TAVILY_API_KEY="your-tavily-key"
```

The repo ships `combined_soln/llm_config.py` with empty defaults; env vars override file values.

---

## 6. Verify the install works

Run **one** of these before Streamlit.

### Option A — HDFC CSV export (needs HDFC PDFs in `data/`)

```bash
source .venv/bin/activate
python HDFC/export_to_csv.py
```

**Success:** prints `Saved to extracted_output/hdfc_extracted.csv` and a KPI | Value table.  
**First run:** 1–3 minutes per PDF while Docling downloads OCR models.

### Option B — IB-only quick test (needs IB PDFs only)

```bash
source .venv/bin/activate
export PYTHONPATH=".:IB:PNB:HDFC:combined_soln"
python IB/run_extraction.py --json
```

**Success:** JSON with keys like `Business`, `Deposits`, `Net_Profit`.

### Option C — Skip CLI verify and go straight to Streamlit

Streamlit downloads PDFs from URLs — local `data/` can be empty if you use Step 7.

---

## 7. Streamlit app — full UI walkthrough

### Start the server

```bash
chmod +x run_local.sh
./run_local.sh
```

Open **http://localhost:8501** in your browser.

`run_local.sh` sets `PYTHONPATH` for `IB`, `PNB`, `HDFC`, and `combined_soln`, then runs `combined_soln/streamlit_app.py`.

### UI steps

1. **PDF URLs** (top expander)
   - IB and PNB URLs are pre-filled from `combined_soln/bse_nse_input.txt` (or built-in BSE defaults).
   - HDFC Investor / CASA URLs are **optional** — leave blank for a 2-bank report (IB + PNB only).
   - To customize defaults, edit `bse_nse_input.txt` (one URL per line, `#` comments allowed; up to 6 lines for HDFC).

2. **Generate Summary Report** (primary button)
   - Downloads PDFs → Docling conversion (one pass per PDF) → KPI extraction → RAG index build.
   - **Do not refresh** the page while running.
   - **Expected time:** ~10–20 minutes for 4 PDFs on CPU; longer with 6 PDFs (HDFC included).
   - Watch progress in the main panel and **Pipeline log** in the sidebar.

3. **Report tab**
   - Table: KPI name · IB · PNB · (HDFC if provided) · Growth % · Rank rows.
   - Download Excel via the export button when the report is ready.

4. **Chat tab** (optional)
   - Ask about extracted KPIs, bank news, or stock prices.
   - Requires `LLM_*` and `TAVILY_API_KEY` (Step 4). Works without them for KPI-only Q&A from cached report data if extraction succeeded.

### Fast mode (tables only, no full OCR)

For quicker (less accurate) runs — same as OpenShift fast image:

```bash
cd combined_soln
PYTHONPATH=..:.:../IB:../PNB:../HDFC streamlit run streamlit_app_openshift.py --server.headless=false
```

See **[RUNBOOK.md](RUNBOOK.md)**.

---

## 8. Running extractors per bank (CLI / notebooks)

Always activate venv and set `PYTHONPATH` when not using `run_local.sh`:

```bash
source .venv/bin/activate
export PYTHONPATH=".:IB:PNB:HDFC:combined_soln"
```

| Bank | Command / notebook |
|------|---------------------|
| IB | `python IB/run_extraction.py --json` · `IB/extract_tables.ipynb` |
| PNB | `PNB/PNB_extract_tables.ipynb` |
| HDFC | `python HDFC/export_to_csv.py` · `HDFC/HDFC_extract_tables.ipynb` |

Example (HDFC):

```python
from pathlib import Path
from HDFC.hdfc_extractor import HDFCKPIExtractor

kpis = HDFCKPIExtractor(
    Path("data/HDFC_investor_PPT.pdf"),
    Path("data/HDFC_Bank_CASA.pdf"),
).extract()
```

---

## 9. Unified report (IB + PNB + HDFC)

**Notebook:** `combined_soln/unified_kpi_notebook.ipynb`

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
df.to_csv("extracted_output/unified_report.csv", index=False)
```

Pass `kpis_hdfc=None` (or omit) for IB + PNB only.

---

## 10. Configuration (LLM & Tavily)

| Variable | Purpose |
|----------|---------|
| `LLM_BASE_URL` | OpenAI-compatible chat endpoint |
| `LLM_API_KEY` | LLM API key |
| `LLM_MODEL` | Model id |
| `TAVILY_API_KEY` | Web search for chatbot |

---

## 11. Docker & OpenShift deploy

See **[RUNBOOK.md](RUNBOOK.md)** and **[DEPLOY.md](DEPLOY.md)**.

```bash
docker build -t bank-kpi-analyst:latest .
docker run -p 8501:8501 bank-kpi-analyst:latest
```

OpenShift: `./deploy_openshift_new.sh cpu` or `gpu` after building/pushing images (see RUNBOOK.md).

---

## 12. KPI list (46 keys)

All banks share the same schema. Examples:

`Business`, `Deposits`, `CASA_Pct_Domestic`, `Gross_Advances`, `Gross_NPA_Amount`, `Gross_NPA_Pct`, `Operating_Profit`, `Net_Profit`, `Net_Interest_Income`, `RoE_Pct`, `ROA_Pct`, `NIM_Global`, `Cost_to_Income_Ratio`, `Credit_Deposit_Ratio`, …

Full list: `ALL_KPI_KEYS` in `IB/kpi_extractor.py`. Ratio/percentage KPIs do not get `*_Growth_Pct` columns.

Reference values (optional): `reference_kpis/ib.json`, `pnb.json`, `hdfc.json`.

---

## 13. Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `ValueError: Unsupported configuration: torch.PP-OCRv6...` | Python 3.14+ or PyTorch not installed before Docling | Use Python **3.11**, install `torch` + `torchvision` **before** `requirements.txt` (Step 2) |
| `ModuleNotFoundError: IB` / `HDFC` | `PYTHONPATH` not set | Use `./run_local.sh` or `export PYTHONPATH=.:IB:PNB:HDFC:combined_soln` |
| BSE curl returns HTML / tiny file | 403 or redirect | Download PDFs manually to `data/` or use Streamlit (uses browser headers) |
| Step 5 fails: HDFC file not found | HDFC PDFs not in `data/` | Add `HDFC_investor_PPT.pdf` + `HDFC_Bank_CASA.pdf` or use IB test (Section 6 Option B) |
| Empty / wrong KPIs | OCR/table mismatch | Use full mode (`run_local.sh`); check PDF quarter matches table columns |
| Streamlit hangs / slow | Normal on CPU | Wait 10–20 min; watch sidebar Pipeline log; do not refresh |
| Port 8501 in use | Another Streamlit instance | `streamlit run ... --server.port 8502` or kill old process |
| Chatbot errors | Missing API keys | Set Step 4 env vars |
| `pip install` very slow | Large ML stack | Expected; use Python 3.11 venv, stable network |

---

## Quick reference — copy/paste full setup

```bash
git clone https://github.com/varunchach/bank-automation-kpi-extraction.git
cd bank-automation-kpi-extraction
python3.11 -m venv .venv && source .venv/bin/activate
pip install --upgrade pip
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
mkdir -p data && curl -L -o data/IB_investor_PPT.pdf "https://www.bseindia.com/xml-data/corpfiling/AttachHis/06fc511a-9d0e-43df-a830-13b9dea59cba.pdf"
# ... (other curl commands from Step 3)
# Add HDFC PDFs to data/ manually
chmod +x run_local.sh && ./run_local.sh
# → http://localhost:8501 → Generate Summary Report
```
