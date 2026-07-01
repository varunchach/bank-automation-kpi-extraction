"""
KPI Report Format — Final output structure matching the standard template.
Same wording, same order. Drops rows where either IB or PNB value is None.
When kpis_hdfc is provided, adds HDFC_Bank column; drops row only if all three banks have None.
"""

import pandas as pd
from typing import Dict, List, Any, Optional

# (internal_key, display_name, has_growth, has_dual_rank)
# has_dual_rank: Operating Profit & Net Profit have Rank by growth + Rank by Value
REPORT_KPI_SPEC = [
    ("Business", "Business", True, False),
    ("Deposits", "Deposits", True, False),
    ("Savings_Deposit_Domestic", "Savings Deposit (Domestic)", True, False),
    ("Current_Deposit_Domestic", "Current Deposit (Domestic)", True, False),
    ("CASA_Deposit_Domestic", "CASA Deposit (Domestic)", True, False),
    ("CASA_Pct_Domestic", "CASA % (Domestic)", False, False),
    ("Term_Deposit_Domestic", "Term Deposit (Domestic)", True, False),
    ("Gross_Advances", "Gross Advances", True, False),
    ("RAM_Advances", "RAM Advances", True, False),
    ("RAM_Pct_Domestic", "RAM % (Domestic)", False, False),
    ("Retail_Advances", "Retail Advances", True, False),
    ("Agriculture_Advances", "Agriculture Advances", True, False),
    ("MSME_Advances", "MSME Advances", True, False),
    ("Corporate_Credit", "Corporate Credit & other", True, False),
    ("Gross_NPA_Amount", "Gross NPA (Amount)", False, False),
    ("Net_NPA_Amount", "Net NPA (Amount)", False, False),
    ("Operating_Profit", "Operating Profit", True, True),
    ("Net_Profit", "Net Profit", True, True),
    ("Net_Interest_Income", "Net Interest Income", True, False),
    ("Interest_Income", "Interest Income", True, False),
    ("Other_Income", "Other Income", True, False),
    ("Total_Income", "Total Income", True, False),
    ("Interest_Expenditure", "Interest Expenditure", True, False),
    ("Employee_Cost", "Employee Cost", True, False),
    ("Other_Expenditure", "Other Expenditure", True, False),
    ("Operating_Expenditure", "Operating Expenditure", True, False),
    ("Total_Expenditure", "Total Expenditure", True, False),
    ("Operating_Profit_to_Business_Pct", "Operating Profit to Business (%)", False, False),
    ("Net_Profit_to_Business_Pct", "Net Profit to Business (%)", False, False),
    ("Net_Interest_Income_to_Business_Pct", "Net Interest Income to Business (%)", False, False),
    ("RoE_Pct", "RoE (%)", False, False),
    ("ROA_Pct", "ROA (%)", False, False),
    ("NIM_Global", "NIM (Global)", False, False),
    ("Cost_of_Deposits", "Cost of Deposits", False, False),
    ("Yield_on_Advances", "Yield on Advances", False, False),
    ("Yield_on_Investments", "Yield on Investments", False, False),
    ("Cost_to_Income_Ratio", "Cost to Income Ratio", False, False),
    ("Gross_NPA_Pct", "Gross NPA (%)", False, False),
    ("Net_NPA_Pct", "Net NPA (%)", False, False),
    ("PCR_Pct", "Provision Coverage Ratio (%)", False, False),
    ("CAR_Basel_III_Pct", "CAR Basel III (%)", False, False),
    ("Credit_Deposit_Ratio", "Credit-Deposit (C-D) Ratio", False, False),
]


def build_report_df(
    kpis_ib: Dict[str, Any],
    kpis_pnb: Dict[str, Any],
    compute_rank,
    kpis_hdfc: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    """
    Build report DataFrame with template order and wording.
    When kpis_hdfc is None: drops KPIs where either IB or PNB value is None.
    When kpis_hdfc is provided: adds HDFC_Bank column; drops row only if all three banks have None.
    """
    has_hdfc = kpis_hdfc is not None
    rows = []
    for item in REPORT_KPI_SPEC:
        key = item[0]
        display_name = item[1]
        has_growth = item[2]
        has_dual_rank = item[3]
        v_ib = kpis_ib.get(key)
        v_pnb = kpis_pnb.get(key)
        v_hdfc = kpis_hdfc.get(key) if kpis_hdfc else None
        if has_hdfc:
            if v_ib is None and v_pnb is None and v_hdfc is None:
                continue
        else:
            if v_ib is None or v_pnb is None:
                continue
        g_ib = kpis_ib.get(key + "_Growth_Pct")
        g_pnb = kpis_pnb.get(key + "_Growth_Pct")
        g_hdfc = kpis_hdfc.get(key + "_Growth_Pct") if kpis_hdfc else None
        g_ib_str = f"{g_ib}%" if g_ib is not None else None
        g_pnb_str = f"{g_pnb}%" if g_pnb is not None else None
        g_hdfc_str = f"{g_hdfc}%" if g_hdfc is not None else None
        ranks_value = compute_rank([v_ib, v_pnb, v_hdfc] if has_hdfc else [v_ib, v_pnb], key)
        row = {"KPI": display_name, "Indian_Bank": v_ib, "PNB": v_pnb}
        if has_hdfc:
            row["HDFC_Bank"] = v_hdfc
        rows.append(row)
        if has_growth:
            growth_row = {"KPI": f"{display_name} Growth (%)" if has_dual_rank else "Growth (%)", "Indian_Bank": g_ib_str, "PNB": g_pnb_str}
            if has_hdfc:
                growth_row["HDFC_Bank"] = g_hdfc_str
            rows.append(growth_row)
        if has_dual_rank:
            g_vals = [g_ib, g_pnb, g_hdfc] if has_hdfc else [g_ib, g_pnb]
            ranks_growth = compute_rank(g_vals, "Operating_Profit_Growth_Pct") if "Operating" in key else compute_rank(g_vals, "Net_Profit_Growth_Pct")
            rg_row = {"KPI": "Rank by growth", "Indian_Bank": ranks_growth[0], "PNB": ranks_growth[1]}
            if has_hdfc:
                rg_row["HDFC_Bank"] = ranks_growth[2]
            rows.append(rg_row)
            rv_row = {"KPI": "Rank by Value", "Indian_Bank": ranks_value[0], "PNB": ranks_value[1]}
            if has_hdfc:
                rv_row["HDFC_Bank"] = ranks_value[2]
            rows.append(rv_row)
        else:
            r_row = {"KPI": "Rank", "Indian_Bank": ranks_value[0], "PNB": ranks_value[1]}
            if has_hdfc:
                r_row["HDFC_Bank"] = ranks_value[2]
            rows.append(r_row)
    return pd.DataFrame(rows)
