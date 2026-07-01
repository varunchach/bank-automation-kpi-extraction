"""Export Reference + IB + PNB + HDFC to Excel. Reads from extracted_output/."""
import json
from pathlib import Path
import pandas as pd

REF_DIR = Path(__file__).resolve().parent.parent / "reference_kpis"
EXTRACTED_DIR = Path(__file__).resolve().parent / "extracted_output"
OUT_FILE = Path(__file__).resolve().parent / "KPI_verification.xlsx"

ALL_KPI_KEYS = [
    "Business", "Deposits", "Savings_Deposit_Domestic", "Current_Deposit_Domestic",
    "CASA_Deposit_Domestic", "CASA_Pct_Domestic", "Term_Deposit_Domestic",
    "Gross_Advances", "RAM_Advances", "RAM_Pct_Domestic", "Retail_Advances",
    "Agriculture_Advances", "MSME_Advances", "Corporate_Credit", "Other",
    "Gross_NPA_Amount", "Net_NPA_Amount", "Gross_NPA_Pct", "Net_NPA_Pct",
    "CAR_Basel_III_Pct", "PCR_Pct", "Credit_Deposit_Ratio",
    "Operating_Profit", "Operating_Profit_Growth_Pct", "Net_Profit", "Net_Profit_Growth_Pct",
    "Net_Interest_Income", "Net_Interest_Income_Growth_Pct", "Interest_Income",
    "Other_Income", "Total_Income", "Interest_Expenditure", "Employee_Cost",
    "Other_Expenditure", "Operating_Expenditure", "Total_Expenditure",
    "Operating_Profit_to_Business_Pct", "Net_Profit_to_Business_Pct", "Net_Interest_Income_to_Business_Pct",
    "RoE_Pct", "ROA_Pct", "NIM_Global", "Cost_of_Deposits", "Yield_on_Advances",
    "Yield_on_Investments", "Cost_to_Income_Ratio",
]

def main():
    ref_ib = json.load(open(REF_DIR / "ib.json")).get("kpis", {})
    ref_pnb = json.load(open(REF_DIR / "pnb.json")).get("kpis", {})
    ref_hdfc = {}
    if (REF_DIR / "hdfc.json").exists():
        ref_hdfc = json.load(open(REF_DIR / "hdfc.json")).get("kpis", {})
    ib_path = EXTRACTED_DIR / "indian_bank_extracted.json"
    pnb_path = EXTRACTED_DIR / "pnb_extracted.json"
    hdfc_path = EXTRACTED_DIR / "hdfc_extracted.json"
    if not ib_path.exists() or not pnb_path.exists():
        print("Run extract notebooks first to populate extracted_output/")
        return
    kpis_ib = json.load(open(ib_path))
    kpis_pnb = json.load(open(pnb_path))
    kpis_hdfc = json.load(open(hdfc_path)) if hdfc_path.exists() else {}
    rows = [{"KPI": k, "Reference_IB": ref_ib.get(k), "Extracted_IB": kpis_ib.get(k),
             "Reference_PNB": ref_pnb.get(k), "Extracted_PNB": kpis_pnb.get(k),
             "Reference_HDFC": ref_hdfc.get(k), "Extracted_HDFC": kpis_hdfc.get(k)} for k in ALL_KPI_KEYS]
    pd.DataFrame(rows).to_excel(OUT_FILE, sheet_name="KPI_Verification", index=False, engine="openpyxl")
    print(f"Saved to {OUT_FILE}")

if __name__ == "__main__":
    main()
