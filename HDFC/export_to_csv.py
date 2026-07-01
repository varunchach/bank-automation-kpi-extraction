#!/usr/bin/env python3
"""Extract HDFC KPIs and save to CSV. Run from project root: python HDFC/export_to_csv.py"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "HDFC"))

from HDFC.hdfc_extractor import HDFCKPIExtractor

DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "extracted_output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

investor_pdf = DATA_DIR / "HDFC_investor_PPT.pdf"
casa_pdf = DATA_DIR / "HDFC_Bank_CASA.pdf"

print("Extracting HDFC KPIs...")
extractor = HDFCKPIExtractor(investor_pdf, casa_pdf)
kpis = extractor.extract()
df = extractor.to_dataframe()

# Transposed: KPI | Value
df_t = df.T.reset_index()
df_t.columns = ["KPI", "Value"]

csv_path = OUTPUT_DIR / "hdfc_extracted.csv"
df_t.to_csv(csv_path, index=False)
print(f"Saved to {csv_path}")
print("\nExtracted values:")
print(df_t.to_string(index=False))
