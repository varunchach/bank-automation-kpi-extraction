"""
Indian Bank KPI Extractor — Extracts KPIs from Indian Bank investor and CASA PDFs.

Accepts file path or URL for each PDF.
Returns final KPIs as dict or JSON.
"""

import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from urllib.request import urlretrieve

import pandas as pd
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import OcrAutoOptions, PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

LOG = logging.getLogger("kpi_app.ib")

# Full-page OCR + higher scale so RapidOCR gets usable images (avoids blank results in headless/container)
_DOCLING_PIPELINE_OPTS = PdfPipelineOptions(
    ocr_options=OcrAutoOptions(force_full_page_ocr=True),
    images_scale=2.0,
)

# -----------------------------------------------------------------------------
# PDF Loader
# -----------------------------------------------------------------------------


def _resolve_path_or_url(source: Union[str, Path]) -> Tuple[Path, bool]:
    """
    If source is URL, download to temp file. Returns (path, is_temp).
    is_temp=True means caller should delete path after use.
    """
    s = str(source).strip()
    if s.startswith(("http://", "https://")):
        fd, path = tempfile.mkstemp(suffix=".pdf")
        try:
            os.close(fd)
            urlretrieve(s, path)
            return Path(path), True
        except Exception:
            Path(path).unlink(missing_ok=True)
            raise
    return Path(s), False


def load_pdf_tables(source: Union[str, Path]) -> List[pd.DataFrame]:
    """Load PDF from file path or URL; return list of table DataFrames."""
    path, is_temp = _resolve_path_or_url(source)
    LOG.info("IB load_pdf_tables: source=%s path=%s", source, path.name if path else path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")
    try:
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=_DOCLING_PIPELINE_OPTS)
            }
        )
        doc = converter.convert(str(path)).document
        tables = [t.export_to_dataframe(doc=doc) for t in doc.tables]
        LOG.info("IB load_pdf_tables: %s -> %d tables", path.name, len(tables))
        return tables
    finally:
        if is_temp:
            path.unlink(missing_ok=True)


# -----------------------------------------------------------------------------
# Extraction Helpers
# -----------------------------------------------------------------------------


def _parse_date_column(col_name: str):
    s = str(col_name).strip()
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(y, mo, d), s
        except Exception:
            return None, s
    return None, s


def get_latest_quarter_column(df: pd.DataFrame) -> Optional[str]:
    best_dt, best_col = None, None
    for col in df.columns:
        dt, orig = _parse_date_column(col)
        if dt and (best_dt is None or dt > best_dt):
            best_dt, best_col = dt, orig
    return best_col


def get_previous_year_column(df: pd.DataFrame) -> Optional[str]:
    """Return column with date ~1 year before the latest date column (e.g. 31.12.2024 if latest is 31.12.2025)."""
    latest_col = get_latest_quarter_column(df)
    if latest_col is None:
        return None
    latest_dt, _ = _parse_date_column(latest_col)
    if latest_dt is None:
        return None
    prev_year = latest_dt.year - 1
    best_col, best_diff = None, float("inf")
    for col in df.columns:
        dt, _ = _parse_date_column(col)
        if dt is None:
            continue
        if "yoy" in str(col).lower() or "growth" in str(col).lower() or "qoq" in str(col).lower():
            continue
        if dt.year == prev_year:
            diff = abs((dt.month - latest_dt.month) * 31 + (dt.day - latest_dt.day))
            if diff < best_diff:
                best_diff, best_col = diff, col
    return best_col


def _find_growth_column(df: pd.DataFrame) -> Optional[str]:
    """Find column containing YoY % Growth. Prefer YoY over QoQ. Use % column, NOT Amt."""
    if df is None or len(df.columns) == 0:
        return None
    for col in df.columns:
        c = str(col).lower()
        if "qoq" in c or "quarter on quarter" in c or "amt" in c or "amount" in c:
            continue
        if any(k in c for k in ("yoy", "year on year", "year-on-year")):
            if "%" in str(col) or "pct" in c or "percent" in c:
                return col
        if any(k in c for k in ("growth", "variation", "var ")) and ("%" in str(col) or "pct" in c):
            return col
    return None


def _compute_growth_pct(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    """Growth % = [(Current / Prior) - 1] * 100. Returns None if either value missing or Prior is 0."""
    if current is None or prior is None or prior == 0:
        return None
    try:
        return round(((float(current) / float(prior)) - 1) * 100, 2)
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def _to_num(x) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    try:
        return float(str(x).replace(",", "").replace(" ", "").strip())
    except (ValueError, TypeError):
        return None


# -----------------------------------------------------------------------------
# Table Detection
# -----------------------------------------------------------------------------


def _table_has_entities(df: pd.DataFrame, entities: List[str]) -> bool:
    text = df.astype(str).to_string().lower()
    return any(e.lower() in text for e in entities)


def _table_has_ratios_column(df: pd.DataFrame) -> bool:
    return any("ratios" in str(c).lower() for c in df.columns)


def _table_starts_with_interest_earned_casa(df: pd.DataFrame) -> bool:
    text = df.astype(str).to_string().lower()
    return (
        "interest earned" in text
        and "(a)" in text
        and "(b)" in text
        and "(c)" in text
        and "(d)" in text
    )


def _table_is_kpi_movement_of_npa(df: pd.DataFrame) -> bool:
    text = df.astype(str).to_string().lower()
    if "gross npa" in text and "opening balance" in text:
        return True
    if "kpi movement" in text and "npa" in text and ("s no" in text or "sl no" in text) and "details" in text:
        return True
    if ("pcr" in text or "provision coverage" in text) and (
        "technical write" in text or "writeoff" in text or "npa" in text
    ):
        return True
    return False


def _table_is_business_snapshot(df: pd.DataFrame) -> bool:
    text = df.astype(str).to_string().lower()
    return "business snapshot" in text and ("sl no" in text or "sl. no" in text) and "parameter" in text


def _table_has_deposits_breakup(df: pd.DataFrame) -> bool:
    text = df.astype(str).to_string().lower()
    return "deposits" in text and ("breakup" in text or "break up" in text)


def _table_is_operating_profit_net_profit(df: pd.DataFrame) -> bool:
    text = df.astype(str).to_string().lower()
    return (
        "operating profit" in text
        and "net profit" in text
        and ("net interest income" in text or "interest income" in text)
    )


# -----------------------------------------------------------------------------
# Extraction Functions
# -----------------------------------------------------------------------------


def _extract_from_table_by_labels(
    df: pd.DataFrame,
    mapping: List[tuple],
    label_cols: Optional[List] = None,
    result: Optional[Dict] = None,
    extract_growth: bool = True,
) -> Dict:
    latest_col = get_latest_quarter_column(df)
    if latest_col is None and len(df.columns) > 0:
        latest_col = df.columns[-1]
    if latest_col is None:
        return result or {}
    if label_cols is None:
        label_cols = list(df.columns[:2]) if len(df.columns) >= 2 else [df.columns[0]]
    if result is None:
        result = {}
    prev_col = get_previous_year_column(df) if extract_growth else None
    growth_col = _find_growth_column(df) if extract_growth else None

    for key, labels in mapping:
        if key in result or key.endswith("_Growth_Pct"):
            continue
        val_float, match_row = None, None
        for _, row in df.iterrows():
            val = " ".join(str(row.get(c, "")) for c in label_cols).strip()
            if not any(lbl.lower() in val.lower() for lbl in labels):
                continue
            num = row.get(latest_col)
            if pd.isna(num):
                break
            s = str(num).replace(",", "").strip().rstrip("%")
            if "%" in str(num):
                try:
                    val_float = float(s)
                    result[key] = val_float
                except ValueError:
                    result[key] = s
                match_row = row
                break
            if s.replace(".", "").replace("-", "").isdigit() or (
                s.startswith("(") and s.endswith(")")
            ):
                try:
                    val_float = float(s.replace("(", "").replace(")", ""))
                    result[key] = val_float
                except ValueError:
                    result[key] = s
                match_row = row
                break

        if key in result and extract_growth and match_row is not None:
            growth_val = None
            if growth_col:
                g = match_row.get(growth_col)
                if g is not None:
                    try:
                        growth_val = float(str(g).replace(",", "").strip().rstrip("%"))
                    except (ValueError, TypeError):
                        pass
            if growth_val is None and prev_col and val_float is not None:
                prev_float = _to_num(match_row.get(prev_col))
                growth_val = _compute_growth_pct(val_float, prev_float)
            if growth_val is not None:
                result[key + "_Growth_Pct"] = growth_val
    return result


def _extract_investor(df: pd.DataFrame) -> Dict:
    """Deposits, Advances (Table 0, 1, 5). With Growth % from YoY column or computed."""
    latest_col = get_latest_quarter_column(df)
    if latest_col is None:
        return {}
    label_cols = [df.columns[0]] + ([df.columns[1]] if len(df.columns) > 1 else [])
    mapping = [
        ("Business", ["Business"]),
        ("Deposits", ["Deposits"]),
        ("Savings_Deposit_Domestic", ["Savings"]),
        ("Current_Deposit_Domestic", ["Current"]),
        ("CASA_Deposit_Domestic", ["CASA"]),
        ("CASA_Pct_Domestic", ["CASA% (Domestic)", "CASA%"]),
        ("Term_Deposit_Domestic", ["Term Deposits", "Term Deposit"]),
        ("Gross_Advances", ["Gross Advances-Domestic", "Gross Advances"]),
        ("RAM_Advances", ["Total (RAM)", "RAM"]),
        ("RAM_Pct_Domestic", ["RAM %toGrossDomesticAdvances", "RAM %"]),
        ("Retail_Advances", ["R etail", "Retail"]),
        ("Agriculture_Advances", ["A griculture", "Agriculture"]),
        ("MSME_Advances", ["M SME", "MSME"]),
        ("Corporate_Credit", ["Corporate"]),
        ("Other", ["Others (OtherIndustries/Sectors)", "Others"]),
    ]
    prev_col = get_previous_year_column(df)
    growth_col = _find_growth_column(df)
    result = {}
    for key, labels in mapping:
        if key in result:
            continue
        val_float, match_row = None, None
        for _, row in df.iterrows():
            val = " ".join(str(row.get(c, "")) for c in label_cols).strip()
            if not any(lbl.lower() in val.lower() for lbl in labels):
                continue
            num = row.get(latest_col)
            if pd.isna(num):
                break
            s = str(num).replace(",", "").strip().rstrip("%")
            if "%" in str(num):
                try:
                    val_float = float(s)
                    result[key] = val_float
                except ValueError:
                    result[key] = s
                match_row = row
                break
            if s.replace(".", "").replace("-", "").isdigit():
                val_float = float(s)
                result[key] = int(val_float)
                match_row = row
                break
        if key in result and match_row is not None and val_float is not None:
            growth_val = None
            if growth_col:
                g = match_row.get(growth_col)
                if g is not None:
                    try:
                        growth_val = float(str(g).replace(",", "").strip().rstrip("%"))
                    except (ValueError, TypeError):
                        pass
            if growth_val is None and prev_col:
                prev_float = _to_num(match_row.get(prev_col))
                growth_val = _compute_growth_pct(val_float, prev_float)
            if growth_val is not None:
                result[key + "_Growth_Pct"] = growth_val
    return result


def _extract_casa(df: pd.DataFrame) -> Dict:
    """P&L, NPA from CASA candidate tables. Extracts value + Growth % (YoY column or computed)."""
    latest_col = get_latest_quarter_column(df)
    if latest_col is None:
        return {}
    label_cols = [df.columns[0]] + ([df.columns[1]] if len(df.columns) > 1 else [])
    mapping = [
        ("Gross_NPA_Amount", ["Gross NPA", "GrossNPA"]),
        ("Net_NPA_Amount", ["Net NPA", "NetNPA"]),
        ("Operating_Profit", ["Operating Profit"]),
        ("Operating_Profit_Growth_Pct", ["Operating Profit"]),
        ("Net_Profit", ["Net Profit", "Profit After Tax"]),
        ("Net_Profit_Growth_Pct", ["Net Profit"]),
        ("Net_Interest_Income", ["Net Interest Income", "NII"]),
        ("Net_Interest_Income_Growth_Pct", ["Net Interest Income"]),
        ("Interest_Income", ["Interest Income"]),
        ("Other_Income", ["Other Income", "Non Interest Income"]),
        ("Total_Income", ["Total Income"]),
        ("Interest_Expenditure", ["Interest Expenditure", "Interest Expenses"]),
        ("Employee_Cost", ["Employee Cost", "Staff Expenses", "Salary"]),
        ("Other_Expenditure", ["Other Expenditure", "Overheads"]),
        ("Operating_Expenditure", ["Operating Expenditure"]),
        ("Total_Expenditure", ["Total Expenditure", "Total Expenses"]),
    ]
    growth_col = _find_growth_column(df) or next(
        (c for c in df.columns if "yoy" in str(c).lower() or "qoq" in str(c).lower() or "(%)" in str(c)),
        None,
    )
    prev_col = get_previous_year_column(df)
    result = {}
    for key, labels in mapping:
        if key in result:
            continue
        use_col = growth_col if key.endswith("_Growth_Pct") and growth_col else latest_col
        val_float, match_row = None, None
        for _, row in df.iterrows():
            val = " ".join(str(row.get(c, "")) for c in label_cols).strip()
            if not any(lbl.lower() in val.lower() for lbl in labels):
                continue
            num = row.get(use_col)
            if pd.isna(num):
                break
            s = str(num).replace(",", "").strip().rstrip("%")
            if "%" in str(num) or key.endswith("_Growth_Pct"):
                try:
                    v = float(s)
                    result[key] = v
                    if not key.endswith("_Growth_Pct"):
                        val_float = v
                    match_row = row
                except ValueError:
                    result[key] = s
                break
            if s.replace(".", "").replace("-", "").isdigit() or (
                s.startswith("(") and s.endswith(")")
            ):
                try:
                    v = int(float(s.replace("(", "").replace(")", "")))
                    result[key] = v
                    val_float = float(v)
                    match_row = row
                except ValueError:
                    result[key] = float(s) if "." in s else s
                    val_float = result[key]
                    match_row = row
                break

        if key.endswith("_Growth_Pct"):
            continue
        if result.get(key + "_Growth_Pct") is not None:
            continue
        if match_row is not None and val_float is not None:
            growth_val = None
            if growth_col:
                g = match_row.get(growth_col)
                if g is not None:
                    try:
                        growth_val = float(str(g).replace(",", "").strip().rstrip("%"))
                    except (ValueError, TypeError):
                        pass
            if growth_val is None and prev_col:
                prev_float = _to_num(match_row.get(prev_col))
                growth_val = _compute_growth_pct(val_float, prev_float)
            if growth_val is not None:
                result[key + "_Growth_Pct"] = growth_val
    return result


def _extract_performance_ratios(df: pd.DataFrame) -> Dict:
    ratios_col = next((c for c in df.columns if "ratios" in str(c).lower()), None)
    label_cols = [ratios_col] if ratios_col else [df.columns[0]]
    mapping = [
        ("RoE_Pct", ["RoE", "Return on Equity", "Return on Average Networth", "ROE"]),
        ("ROA_Pct", ["ROA", "Return on Assets"]),
        ("NIM_Global", ["NIM", "NIM (Global)", "Net Interest Margin"]),
        ("Cost_of_Deposits", ["Cost of Deposits", "Cost of Deposit"]),
        ("Yield_on_Advances", ["Yield on Advances"]),
        ("Yield_on_Investments", ["Yield on Investments"]),
        ("Cost_to_Income_Ratio", ["Cost to Income", "Cost to Income Ratio", "Cost-Income Ratio"]),
    ]
    return _extract_from_table_by_labels(df, mapping, label_cols=label_cols)


def _extract_casa_npa_car(df: pd.DataFrame) -> Dict:
    mapping = [
        ("Gross_NPA_Pct", ["Gross NPA", "Gross NPA%", "Gross NPA (%)"]),
        ("Net_NPA_Pct", ["Net NPA", "Net NPA%", "Net NPA (%)"]),
        ("CAR_Basel_III_Pct", ["CAR Basel III", "CAR Basel", "CRAR", "Capital Adequacy"]),
    ]
    return _extract_from_table_by_labels(df, mapping)


def _extract_casa_interest_earned_expenditure(df: pd.DataFrame) -> Dict:
    mapping = [
        ("Interest_Expenditure", ["Interest Expended", "Interest Expenditure", "Interest Expenses"]),
        ("Operating_Expenditure", ["Operating Expenses", "Operating Expenditure"]),
        ("Employee_Cost", ["Employees cost", "Employee Cost", "Staff Expenses"]),
        ("Other_Expenditure", ["Other Operating expenses", "Other Expenditure", "Overheads"]),
        ("Total_Expenditure", ["Total Expenditure"]),
    ]
    latest_col = get_latest_quarter_column(df)
    if latest_col is None and len(df.columns) > 0:
        latest_col = df.columns[-1]
    if latest_col is None:
        return {}
    label_cols = [c for c in df.columns if c != latest_col][:5]
    if not label_cols:
        label_cols = list(df.columns[:2]) if len(df.columns) >= 2 else [df.columns[0]]
    prev_col = get_previous_year_column(df)
    growth_col = _find_growth_column(df)
    result = {}
    for key, labels in mapping:
        if key in result:
            continue
        val_float, match_row = None, None
        for _, row in df.iterrows():
            val = " ".join(str(row.get(c, "")) for c in label_cols).strip()
            if not any(lbl.lower() in val.lower() for lbl in labels):
                continue
            num = row.get(latest_col)
            if pd.isna(num):
                break
            s = str(num).replace(",", "").replace(" ", "").strip().rstrip("%")
            if s.replace(".", "").replace("-", "").isdigit() or (
                s.startswith("(") and s.endswith(")")
            ):
                try:
                    v = float(s.replace("(", "").replace(")", ""))
                    val_float = v
                    result[key] = round(v, 2) if v != int(v) else int(v)
                    match_row = row
                except ValueError:
                    result[key] = s
                break
        if key in result and match_row is not None and val_float is not None:
            growth_val = None
            if growth_col:
                g = match_row.get(growth_col)
                if g is not None:
                    try:
                        growth_val = float(str(g).replace(",", "").strip().rstrip("%"))
                    except (ValueError, TypeError):
                        pass
            if growth_val is None and prev_col:
                prev_float = _to_num(match_row.get(prev_col))
                growth_val = _compute_growth_pct(val_float, prev_float)
            if growth_val is not None:
                result[key + "_Growth_Pct"] = growth_val
    return result


def _extract_investor_pcr(df: pd.DataFrame) -> Dict:
    mapping = [
        (
            "PCR_Pct",
            [
                "PCR",
                "Provision Coverage Ratio",
                "Technical Writeoff",
                "Technical Write-off",
                "including Technical Writeoff",
                "including Technical Write-off",
            ],
        )
    ]
    return _extract_from_table_by_labels(df, mapping)


def _extract_investor_npa_amounts(df: pd.DataFrame) -> Dict:
    mapping = [
        ("Gross_NPA_Amount", ["Gross NPA closing", "Gross NPAclosing", "Gross NPA closing Balance"]),
        ("Net_NPA_Amount", ["Net NPA [4-", "Net NPA [4-(5+6)]"]),
    ]
    latest_col = get_latest_quarter_column(df)
    if latest_col is None and len(df.columns) > 0:
        latest_col = df.columns[-1]
    if latest_col is None:
        return {}
    label_cols = [c for c in df.columns if c != latest_col][:5]
    if not label_cols:
        label_cols = list(df.columns[:2]) if len(df.columns) >= 2 else [df.columns[0]]
    prev_col = get_previous_year_column(df)
    growth_col = _find_growth_column(df)
    result = {}
    for key, labels in mapping:
        if key in result:
            continue
        val_float, match_row = None, None
        for _, row in df.iterrows():
            val = " ".join(str(row.get(c, "")) for c in label_cols).strip()
            if not any(lbl.lower() in val.lower() for lbl in labels):
                continue
            num = row.get(latest_col)
            if pd.isna(num):
                break
            s = str(num).replace(",", "").replace(" ", "").strip().rstrip("%")
            if s.replace(".", "").replace("-", "").isdigit():
                try:
                    val_float = float(s)
                    result[key] = int(val_float)
                    match_row = row
                except ValueError:
                    result[key] = float(s)
                    match_row = row
                break
        if key in result and match_row is not None and val_float is not None:
            growth_val = None
            if growth_col:
                g = match_row.get(growth_col)
                if g is not None:
                    try:
                        growth_val = float(str(g).replace(",", "").strip().rstrip("%"))
                    except (ValueError, TypeError):
                        pass
            if growth_val is None and prev_col:
                prev_float = _to_num(match_row.get(prev_col))
                growth_val = _compute_growth_pct(val_float, prev_float)
            if growth_val is not None:
                result[key + "_Growth_Pct"] = growth_val
    return result


def _extract_investor_profit_income(df: pd.DataFrame) -> Dict:
    latest_col = get_latest_quarter_column(df)
    if latest_col is None and len(df.columns) > 0:
        latest_col = df.columns[-1]
    if latest_col is None:
        return {}
    growth_col = _find_growth_column(df) or next((c for c in df.columns if "qoq" in str(c).lower() or "yoy" in str(c).lower()), None)
    prev_col = get_previous_year_column(df)
    label_cols = [c for c in df.columns if c != latest_col][:5]
    if not label_cols:
        label_cols = list(df.columns[:2]) if len(df.columns) >= 2 else [df.columns[0]]
    result = {}
    mapping_abs = [
        ("Operating_Profit", ["Operating Profit"]),
        ("Net_Profit", ["Net Profit", "Profit After Tax"]),
        ("Net_Interest_Income", ["Net Interest Income", "NII"]),
        ("Interest_Income", ["Interest Income"]),
    ]
    mapping_growth = [
        ("Operating_Profit_Growth_Pct", ["Operating Profit"]),
        ("Net_Profit_Growth_Pct", ["Net Profit"]),
        ("Net_Interest_Income_Growth_Pct", ["Net Interest Income", "NII"]),
    ]
    for key, labels in mapping_abs:
        if key in result:
            continue
        val_float, match_row = None, None
        for _, row in df.iterrows():
            val = " ".join(str(row.get(c, "")) for c in label_cols).strip()
            if not any(lbl.lower() in val.lower() for lbl in labels):
                continue
            num = row.get(latest_col)
            if pd.isna(num):
                break
            s = str(num).replace(",", "").strip().rstrip("%")
            if s.replace(".", "").replace("-", "").isdigit() or (
                s.startswith("(") and s.endswith(")")
            ):
                try:
                    v = float(s.replace("(", "").replace(")", ""))
                    val_float = v
                    result[key] = int(v) if v == int(v) else round(v, 2)
                    match_row = row
                except ValueError:
                    result[key] = s
                break
        if key in result and match_row is not None and val_float is not None and result.get(key + "_Growth_Pct") is None:
            growth_val = None
            if growth_col:
                g = match_row.get(growth_col)
                if g is not None:
                    try:
                        growth_val = float(str(g).replace(",", "").strip().rstrip("%"))
                    except (ValueError, TypeError):
                        pass
            if growth_val is None and prev_col:
                prev_float = _to_num(match_row.get(prev_col))
                growth_val = _compute_growth_pct(val_float, prev_float)
            if growth_val is not None:
                result[key + "_Growth_Pct"] = growth_val
    use_col = growth_col if growth_col else latest_col
    for key, labels in mapping_growth:
        if key in result:
            continue
        for _, row in df.iterrows():
            val = " ".join(str(row.get(c, "")) for c in label_cols).strip()
            if not any(lbl.lower() in val.lower() for lbl in labels):
                continue
            num = row.get(use_col)
            if pd.isna(num):
                break
            s = str(num).replace(",", "").strip().rstrip("%")
            try:
                result[key] = float(s)
            except ValueError:
                result[key] = s
            break
    return result


def _extract_investor_cd_ratio(df: pd.DataFrame) -> Dict:
    mapping = [
        (
            "Credit_Deposit_Ratio",
            ["CD Ratio %", "CD Ratio", "Credit-Deposit", "C-D Ratio", "Credit Deposit Ratio", "CDR"],
        )
    ]
    return _extract_from_table_by_labels(df, mapping)


def _merge_extract(tables_dfs: List[pd.DataFrame], indices: tuple, fn) -> Dict:
    merged = {}
    for i in (indices if indices else range(len(tables_dfs))):
        if i < len(tables_dfs):
            merged.update(fn(tables_dfs[i]) or {})
    return merged


def _run_investor_extraction(tables_dfs: List[pd.DataFrame]) -> Dict:
    LOG.info("IB investor: starting with %d tables", len(tables_dfs))
    extracted = _merge_extract(tables_dfs, (0, 1, 5), _extract_investor)
    LOG.info("IB investor: merge_extract(tables 0,1,5) -> %d keys", len(extracted))
    if not extracted:
        raise RuntimeError("Investor extraction returned no data.")
    perf, profit, pcr, cd_sources = [], [], [], []
    for i, df in enumerate(tables_dfs):
        if _table_has_ratios_column(df):
            perf.append(i)
        if _table_is_operating_profit_net_profit(df):
            profit.append(i)
        if _table_is_kpi_movement_of_npa(df):
            pcr.append(i)
        if _table_is_business_snapshot(df) or _table_has_deposits_breakup(df):
            cd_sources.append(i)
        if _table_is_business_snapshot(df) and i + 1 < len(tables_dfs):
            cd_sources.append(i + 1)
    for i in perf:
        r = _extract_performance_ratios(tables_dfs[i]) or {}
        if r:
            extracted.update(r)
            LOG.info("IB investor: performance_ratios from table %d -> %d keys", i, len(r))
    for i in profit:
        r = _extract_investor_profit_income(tables_dfs[i]) or {}
        if r:
            extracted.update(r)
            LOG.info("IB investor: profit_income from table %d -> %d keys", i, len(r))
    if not any(k in extracted for k in ["Operating_Profit", "Net_Interest_Income"]):
        for df in tables_dfs:
            r = _extract_investor_profit_income(df)
            if r:
                extracted.update(r)
                break
    for i in pcr:
        r1 = _extract_investor_pcr(tables_dfs[i]) or {}
        r2 = _extract_investor_npa_amounts(tables_dfs[i]) or {}
        if r1:
            extracted.update(r1)
            LOG.info("IB investor: PCR from table %d", i)
        if r2:
            extracted.update(r2)
            LOG.info("IB investor: NPA amounts from table %d", i)
    if "PCR_Pct" not in extracted:
        for df in tables_dfs:
            r = _extract_investor_pcr(df)
            if r:
                extracted.update(r)
                break
    if "Gross_NPA_Amount" not in extracted or "Net_NPA_Amount" not in extracted:
        for df in tables_dfs:
            r = _extract_investor_npa_amounts(df)
            if r:
                extracted.update(r)
                break
    for i in cd_sources:
        r = _extract_investor_cd_ratio(tables_dfs[i]) or {}
        if r:
            extracted.update(r)
            LOG.info("IB investor: CD ratio from table %d", i)
    if "Credit_Deposit_Ratio" not in extracted:
        for df in tables_dfs:
            r = _extract_investor_cd_ratio(df)
            if r:
                extracted.update(r)
                break
    LOG.info("IB investor: done, total %d keys", len(extracted))
    return extracted


TARGET_ENTITIES_CASA = [
    "Gross NPA",
    "Net NPA",
    "Operating Profit",
    "Net Profit",
    "Net Interest Income",
    "Interest Income",
    "Other Income",
    "Total Income",
    "Interest Expenditure",
    "Employee",
    "Operating Expenditure",
    "Total Expenditure",
    "RoE",
    "ROA",
    "NIM",
    "Cost of Deposits",
    "Yield on Advances",
    "Yield on Investments",
    "Cost to Income",
]


def _run_casa_extraction(tables_dfs: List[pd.DataFrame]) -> Dict:
    LOG.info("IB CASA: starting with %d tables", len(tables_dfs))
    candidates = [
        i for i in range(len(tables_dfs))
        if _table_has_entities(tables_dfs[i], TARGET_ENTITIES_CASA)
    ]
    casa_indices = candidates if candidates else list(range(len(tables_dfs)))
    LOG.info("IB CASA: candidate table indices %s", casa_indices)
    extracted = _merge_extract(tables_dfs, tuple(casa_indices), _extract_casa)
    LOG.info("IB CASA: merge_extract -> %d keys", len(extracted))
    interest_earned_idx = [
        i for i in range(len(tables_dfs))
        if _table_starts_with_interest_earned_casa(tables_dfs[i])
    ]
    for i in interest_earned_idx:
        extracted.update(_extract_casa_npa_car(tables_dfs[i]) or {})
        extracted.update(_extract_casa_interest_earned_expenditure(tables_dfs[i]) or {})
        if i + 1 < len(tables_dfs):
            extracted.update(_extract_casa_npa_car(tables_dfs[i + 1]) or {})
            extracted.update(_extract_casa_interest_earned_expenditure(tables_dfs[i + 1]) or {})
    LOG.info("IB CASA: done, total %d keys", len(extracted))
    return extracted


def _compute_derived(extracted: Dict) -> None:
    """Mutates extracted with Total_Expenditure, ratios to Business, etc."""
    op_ex = _to_num(extracted.get("Operating_Expenditure"))
    int_ex = _to_num(extracted.get("Interest_Expenditure"))
    if op_ex is not None and int_ex is not None:
        extracted["Total_Expenditure"] = op_ex + int_ex
    nii_qoq = extracted.get("Net_Interest_Income_Growth_Pct")
    if nii_qoq is not None:
        extracted["Net_Interest_Income_to_Business_Pct"] = _to_num(nii_qoq)
    business = _to_num(extracted.get("Business"))
    if business and business != 0:
        op = _to_num(extracted.get("Operating_Profit"))
        if op is not None:
            extracted["Operating_Profit_to_Business_Pct"] = round(op / business * 100, 2)
        np_ = _to_num(extracted.get("Net_Profit"))
        if np_ is not None:
            extracted["Net_Profit_to_Business_Pct"] = round(np_ / business * 100, 2)
        if extracted.get("Net_Interest_Income_to_Business_Pct") is None:
            nii = _to_num(extracted.get("Net_Interest_Income"))
            if nii is not None:
                extracted["Net_Interest_Income_to_Business_Pct"] = round(nii / business * 100, 2)


# -----------------------------------------------------------------------------
# Public API: IndianBankKPIExtractor
# -----------------------------------------------------------------------------

# PCT-based KPIs: never extract or compute growth (ratios/%, not amounts)
IB_PCT_KPI_KEYS = frozenset({
    "CASA_Pct_Domestic", "RAM_Pct_Domestic", "Gross_NPA_Pct", "Net_NPA_Pct",
    "CAR_Basel_III_Pct", "PCR_Pct", "Credit_Deposit_Ratio",
    "Operating_Profit_to_Business_Pct", "Net_Profit_to_Business_Pct",
    "Net_Interest_Income_to_Business_Pct", "RoE_Pct", "ROA_Pct", "NIM_Global",
    "Cost_of_Deposits", "Yield_on_Advances", "Yield_on_Investments",
    "Cost_to_Income_Ratio",
})

ALL_KPI_KEYS = [
    "Business",
    "Deposits",
    "Savings_Deposit_Domestic",
    "Current_Deposit_Domestic",
    "CASA_Deposit_Domestic",
    "CASA_Pct_Domestic",
    "Term_Deposit_Domestic",
    "Gross_Advances",
    "RAM_Advances",
    "RAM_Pct_Domestic",
    "Retail_Advances",
    "Agriculture_Advances",
    "MSME_Advances",
    "Corporate_Credit",
    "Other",
    "Gross_NPA_Amount",
    "Net_NPA_Amount",
    "Gross_NPA_Pct",
    "Net_NPA_Pct",
    "CAR_Basel_III_Pct",
    "PCR_Pct",
    "Credit_Deposit_Ratio",
    "Operating_Profit",
    "Operating_Profit_Growth_Pct",
    "Net_Profit",
    "Net_Profit_Growth_Pct",
    "Net_Interest_Income",
    "Net_Interest_Income_Growth_Pct",
    "Interest_Income",
    "Other_Income",
    "Total_Income",
    "Interest_Expenditure",
    "Employee_Cost",
    "Other_Expenditure",
    "Operating_Expenditure",
    "Total_Expenditure",
    "Operating_Profit_to_Business_Pct",
    "Net_Profit_to_Business_Pct",
    "Net_Interest_Income_to_Business_Pct",
    "RoE_Pct",
    "ROA_Pct",
    "NIM_Global",
    "Cost_of_Deposits",
    "Yield_on_Advances",
    "Yield_on_Investments",
    "Cost_to_Income_Ratio",
]


class IndianBankKPIExtractor:
    """
    Extracts KPIs from Indian Bank investor and CASA PDFs.

    Accepts file path or URL for each PDF.
    """

    def __init__(
        self,
        investor_pdf: Optional[Union[str, Path]] = None,
        casa_pdf: Optional[Union[str, Path]] = None,
        tables_inv: Optional[List[pd.DataFrame]] = None,
        tables_casa: Optional[List[pd.DataFrame]] = None,
    ):
        """
        Args:
            investor_pdf: Path or URL to IB_investor_PPT.pdf (ignored if tables_inv provided).
            casa_pdf: Path or URL to IB_CASA_Numbers_PPT.pdf (ignored if tables_casa provided).
            tables_inv: Pre-converted Docling tables for investor PDF (avoids second conversion).
            tables_casa: Pre-converted Docling tables for CASA PDF.
        """
        self.investor_pdf = investor_pdf
        self.casa_pdf = casa_pdf
        self._tables_inv = tables_inv
        self._tables_casa = tables_casa

    def extract(self) -> Dict:
        """
        Run extraction and return final KPIs as dictionary.
        Includes k+Growth_Pct for every KPI when available.
        """
        LOG.info("IB extract: starting")
        tables_inv = self._tables_inv if self._tables_inv is not None else load_pdf_tables(self.investor_pdf)
        tables_casa = self._tables_casa if self._tables_casa is not None else load_pdf_tables(self.casa_pdf)
        LOG.info("IB extract: investor %d tables, CASA %d tables", len(tables_inv), len(tables_casa))
        extracted_inv = _run_investor_extraction(tables_inv)
        LOG.info("IB extract: investor -> %d keys", len(extracted_inv))
        extracted_casa = _run_casa_extraction(tables_casa)
        LOG.info("IB extract: CASA -> %d keys", len(extracted_casa))
        merged = {**extracted_casa, **extracted_inv}
        _compute_derived(merged)
        LOG.info("IB extract: merged %d keys, derived computed", len(merged))
        result = {k: merged.get(k) for k in ALL_KPI_KEYS}
        base_keys = [k for k in ALL_KPI_KEYS if not k.endswith("_Growth_Pct")]
        for k in base_keys:
            if k in IB_PCT_KPI_KEYS:
                continue  # Never report growth for PCT-based KPIs
            g = merged.get(k + "_Growth_Pct")
            if g is not None:
                result[k + "_Growth_Pct"] = g
        return result

    def to_dict(self) -> Dict:
        """Alias for extract()."""
        return self.extract()

    def to_json(self, indent: Optional[int] = 2) -> str:
        """Return KPIs as JSON string."""
        return json.dumps(self.extract(), indent=indent)

    def to_dataframe(self) -> pd.DataFrame:
        """Return KPIs as single-row DataFrame."""
        return pd.DataFrame([self.extract()])
