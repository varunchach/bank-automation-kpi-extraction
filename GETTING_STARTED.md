# Getting Started — First-Time Setup (End to End)

Follow this guide **in order**. Every command is copy-paste ready.  
Repo: [github.com/varunchach/bank-automation-kpi-extraction](https://github.com/varunchach/bank-automation-kpi-extraction)

**Goal:** Run the Streamlit app, generate an IB + PNB KPI report from BSE PDFs, optionally add HDFC.

**Time:** ~20 min setup + ~15 min first report on CPU.

---

## Before you start

| You need | Check |
|----------|--------|
| macOS or Linux (or WSL2 on Windows) | — |
| Python **3.11 only** | `python3.11 --version` → `Python 3.11.x` |
| If missing on Mac | `brew install python@3.11` |
| Git | `git --version` |
| curl | `curl --version` |
| ~8 GB RAM free | Activity Monitor / `free -h` |
| Internet | for pip + PDF download |

> **Do not use Python 3.14+** — Docling OCR fails with `Unsupported configuration: torch.PP-OCRv6...`

---

## Step 1 — Clone the repository

```bash
git clone https://github.com/varunchach/bank-automation-kpi-extraction.git
cd bank-automation-kpi-extraction
```

**You should see:** a folder with `run_local.sh`, `IB/`, `PNB/`, `HDFC/`, `combined_soln/`.

---

## Step 2 — Run automated setup (recommended)

Requires **Python 3.11** on your PATH. On Mac: `brew install python@3.11` if needed.

This creates `.venv`, installs PyTorch + dependencies, and downloads IB + PNB PDFs.

```bash
make setup
```

Or without Make:

```bash
chmod +x scripts/*.sh run_local.sh
./scripts/setup.sh
```

**Expected output (last lines):**

```
=== Summary: N passed, 0 failed, M warnings ===
Ready. Next: ./run_local.sh  →  http://localhost:8501
```

**If setup fails:**

| Error | Fix |
|-------|-----|
| `Python 3.11 is required` | Install: `brew install python@3.11` (Mac) or `apt install python3.11 python3.11-venv` (Ubuntu) |
| Wrong Python in `.venv` (3.14 OCR error) | `make clean-venv && make setup` |
| PDF download fails | Run `./scripts/download_pdfs.sh` again; or copy PDFs manually to `data/` (see [data/README.md](data/README.md)) |
| `pip install` errors | Ensure venv active: `source .venv/bin/activate` |

### Manual setup (if you prefer)

<details>
<summary>Click to expand manual commands</summary>

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install torch==2.5.1 torchvision==0.20.1 --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
./scripts/download_pdfs.sh
```

</details>

---

## Step 3 — Verify everything is ready

```bash
make verify
```

**You should see:** all checks under `[1] Python`, `[2] Python packages`, `[3] Data files` with ✓ marks.  
HDFC files may show `!` warnings — that is OK for a 2-bank report.

---

## Step 4 — Optional smoke test (proves extraction works)

Takes **2–5 minutes** on first run (Docling downloads OCR models).

```bash
make smoke
```

**Success looks like:** JSON output containing `"Business"`, `"Deposits"`, `"Net_Profit"` with numeric values.

**If it fails:** re-read Step 2; confirm PDFs in `data/` are real PDFs (`file data/*.pdf`).

---

## Step 5 — Start Streamlit

```bash
make run
```

Open in browser: **http://localhost:8501**

You should see: **Multi-Bank KPI Analyst (IB · PNB · HDFC)**

---

## Step 6 — Generate your first report (in the browser)

1. Expand **PDF URLs (IB, PNB, HDFC — optional)** at the top.  
   IB and PNB URLs are pre-filled from BSE.

2. Leave **HDFC** URL fields **empty** for your first run (2-bank report).

3. Click **Generate Summary Report** (blue button).

4. **Wait 10–20 minutes** on CPU. Do not refresh the page.  
   Watch the **Pipeline log** in the left sidebar for progress:
   - Downloading PDFs
   - Converting each PDF with Docling
   - Extracting KPIs
   - Building RAG index

5. When done, scroll to the **Report** section.  
   You should see a table with columns: **KPI · IB · PNB · Growth · Rank** (IB may appear as `Indian_Bank` in exports).

6. Click **Download Excel** (if shown) to export.

**Success criteria:** At least 20+ KPI rows with numbers for IB and PNB (not all blank).

---

## Step 7 — Add HDFC (optional, 3-bank report)

HDFC PDFs are **not** on BSE in this repo by default. Place files manually:

```bash
# Copy your files into data/ with exact names:
#   data/HDFC_investor_PPT.pdf
#   data/HDFC_Bank_CASA.pdf
ls -lh data/HDFC*.pdf
```

Or paste HDFC BSE URLs in the Streamlit **HDFC Investor** / **HDFC CASA** fields, then click **Generate Summary Report** again.

CLI test for HDFC only:

```bash
source .venv/bin/activate
python HDFC/export_to_csv.py
# → extracted_output/hdfc_extracted.csv
```

---

## Step 8 — Enable chatbot (optional)

KPI extraction works **without** API keys. The **Chat** tab needs:

```bash
cp combined_soln/llm_config.example.py combined_soln/llm_config.py
export LLM_BASE_URL="https://your-llm-endpoint/v1"
export LLM_API_KEY="your-key"
export LLM_MODEL="your-model-name"
export TAVILY_API_KEY="your-tavily-key"
```

Restart Streamlit (`Ctrl+C`, then `./run_local.sh`).

Try asking: *"Compare Net Profit growth for IB and PNB"* or *"What is PNB.NS trading at?"*

---

## What each path does

```
┌─────────────────────────────────────────────────────────────┐
│  Path A — Streamlit (recommended for first time)            │
│  ./run_local.sh → Generate Summary Report → Report + Chat   │
│  Needs: setup only (PDFs downloaded by app OR in data/)     │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Path B — CLI / scripts                                     │
│  ./scripts/smoke_test.sh     → IB JSON                      │
│  python HDFC/export_to_csv.py → HDFC CSV                    │
│  Needs: PDFs in data/                                       │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Path C — Jupyter notebooks                                 │
│  IB/extract_tables.ipynb, PNB/PNB_extract_tables.ipynb,     │
│  combined_soln/unified_kpi_notebook.ipynb                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Common problems

| Symptom | Solution |
|---------|----------|
| Blank report / all None | PDF quarter mismatch or OCR failed — use full mode (`run_local.sh`), not fast mode |
| Page stuck / no progress | Normal on CPU — wait; check sidebar Pipeline log |
| Port 8501 already in use | `lsof -i :8501` and kill old Streamlit, or use port 8502 |
| `ModuleNotFoundError: IB` | Run from repo root; use `./run_local.sh` not raw `streamlit run` |
| Chat says API key missing | Complete Step 8 |
| BSE download HTML not PDF | Use `./scripts/download_pdfs.sh` (has Referer headers) or Streamlit download |

---

## Next steps

- Full reference: [README.md](README.md)
- OpenShift deploy: [RUNBOOK.md](RUNBOOK.md)
- PDF filenames & URLs: [data/README.md](data/README.md)

---

## Quick command cheat sheet

```bash
# Full first-time setup (Python 3.11 required)
git clone https://github.com/varunchach/bank-automation-kpi-extraction.git
cd bank-automation-kpi-extraction
make setup
make verify
make smoke          # optional, ~2–5 min
make run            # → http://localhost:8501
```
