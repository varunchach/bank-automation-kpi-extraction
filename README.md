# Bank Automation — KPI Extraction

Extract **46 standardized KPIs** from bank investor + CASA PDFs. Compare **IB · PNB · HDFC** side-by-side with ranks, Excel export, and an optional RAG chatbot.

**Repository:** [github.com/varunchach/bank-automation-kpi-extraction](https://github.com/varunchach/bank-automation-kpi-extraction)

---

## New here? Start here

| Doc | Purpose |
|-----|---------|
| **[GETTING_STARTED.md](GETTING_STARTED.md)** | **First-time setup — follow this step by step** |
| [Makefile](Makefile) | `make setup`, `make verify`, `make run` shortcuts |
| [data/README.md](data/README.md) | PDF filenames and download URLs |
| [RUNBOOK.md](RUNBOOK.md) | OpenShift / Docker deploy |
| [DEPLOY.md](DEPLOY.md) | Container build and push |

### Fastest path (3 commands)

**Requires Python 3.11** (`brew install python@3.11` on Mac if missing).

```bash
git clone https://github.com/varunchach/bank-automation-kpi-extraction.git
cd bank-automation-kpi-extraction
make setup && make run
```

Or without Make: `chmod +x scripts/*.sh run_local.sh && ./scripts/setup.sh && ./run_local.sh`

Then open **http://localhost:8501** → click **Generate Summary Report**.

---

## What this project does

| Step | Tool |
|------|------|
| Load PDFs | `data/` folder or BSE URLs in Streamlit |
| Parse tables | [Docling](https://github.com/DS4SD/docling) (OCR + table extraction) |
| Extract KPIs | `IB/`, `PNB/`, `HDFC/` extractors |
| Compare & rank | `combined_soln/kpi_report_format.py` |
| UI | Streamlit (`./run_local.sh`) |
| Chat (optional) | Milvus RAG + LLM + Tavily + Yahoo Finance |

---

## Repository layout

```
bank-automation-kpi-extraction/
├── GETTING_STARTED.md      ← start here
├── scripts/
│   ├── setup.sh            ← venv + deps + PDF download
│   ├── verify_setup.sh     ← check install
│   ├── download_pdfs.sh    ← IB + PNB from BSE
│   └── smoke_test.sh       ← quick IB extraction test
├── IB/                     # IB bank extractor
├── PNB/                    # PNB bank extractor
├── HDFC/                   # HDFC bank extractor
├── combined_soln/          # Streamlit app, report, RAG
├── data/                   # PDFs (gitignored)
├── run_local.sh            # start Streamlit
└── requirements.txt
```

---

## Prerequisites

| Item | Requirement |
|------|-------------|
| Python | **3.11.x only** (see `.python-version`) — install with `brew install python@3.11` on Mac |
| RAM | 8 GB+ (16 GB for 6 PDFs) |
| OS | macOS, Linux, or WSL2 |
| Time | ~20 min setup; ~15 min first report (CPU) |

Optional: LLM + Tavily API keys for chatbot only.

---

## Scripts reference

| Command | What it does |
|---------|--------------|
| `make setup` | Create venv (Python 3.11 only), install deps, download IB+PNB PDFs |
| `make verify` | Check Python, packages, PDFs |
| `make download` | Re-download IB+PNB PDFs only |
| `make smoke` | Run IB extraction, print JSON sample |
| `make run` | Start Streamlit on port 8501 |
| `make clean-venv` | Delete `.venv` if wrong Python was used |

Equivalent shell scripts live in `scripts/`.

---

## Streamlit UI (summary)

1. `./run_local.sh` → http://localhost:8501  
2. **Generate Summary Report** (IB + PNB URLs pre-filled)  
3. Wait ~10–20 min (CPU) — watch sidebar **Pipeline log**  
4. View report table · download Excel · use Chat tab (optional)

Full UI walkthrough: [GETTING_STARTED.md § Step 6](GETTING_STARTED.md#step-6--generate-your-first-report-in-the-browser)

---

## CLI examples

```bash
source .venv/bin/activate
export PYTHONPATH=".:IB:PNB:HDFC:combined_soln"

# IB
python IB/run_extraction.py --json

# HDFC → CSV
python HDFC/export_to_csv.py
```

---

## KPI schema (46 keys)

Shared across all banks: `Business`, `Deposits`, `Gross_Advances`, `Operating_Profit`, `Net_Profit`, `Gross_NPA_Pct`, `RoE_Pct`, `NIM_Global`, …

Full list: `ALL_KPI_KEYS` in `IB/kpi_extractor.py`.  
Reference JSON: `reference_kpis/ib.json`, `pnb.json`, `hdfc.json`.

---

## Docker

```bash
docker build -t bank-kpi-analyst:latest .
docker run -p 8501:8501 bank-kpi-analyst:latest
```

OpenShift: see [RUNBOOK.md](RUNBOOK.md).

---

## Troubleshooting

See [GETTING_STARTED.md — Common problems](GETTING_STARTED.md#common-problems).

Quick fixes:

- **Python 3.14 OCR error** → use Python 3.11 + install torch before requirements  
- **Missing PDFs** → `./scripts/download_pdfs.sh`  
- **Import errors** → use `./run_local.sh` (sets PYTHONPATH)  
- **Slow** → normal on CPU; first Docling run downloads models  

---

## License

Internal / POC. Update BSE URLs when new quarterly filings are published.
