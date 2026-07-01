"""
HDFC Bank KPI Extractor — Extracts KPIs from HDFC investor and CASA PDFs.

Same interface as Indian Bank and PNB: HDFCKPIExtractor(investor_pdf, casa_pdf)
Returns dict with same ALL_KPI_KEYS (46 keys) as IB/PNB.

Discovery mapping (Phase 1):
- Investor T0: P&L (₹ bn) — Net interest income, Operating expenses, Profit after tax
- Investor T1: Balance sheet — Deposits, Net Advances
- Investor T2: Loans — Gross Advances, Retail, Corporate
- Investor T4: CASA ratio
- Investor T6: PCR
- CASA T0: Full P&L (crores) — Interest earned, Gross NPAs, Net NPAs, NPA %, CAR, ROA
"""

import json
import logging
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.request import urlretrieve

import pandas as pd
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import OcrAutoOptions, PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

LOG = logging.getLogger("kpi_app.hdfc")

_DOCLING_PIPELINE_OPTS = PdfPipelineOptions(
    ocr_options=OcrAutoOptions(force_full_page_ocr=True),
    images_scale=2.0,
)

# PCT-based KPIs: never extract or compute growth
HDFC_PCT_KPI_KEYS = frozenset({
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


# -----------------------------------------------------------------------------
# PDF Loader
# -----------------------------------------------------------------------------


def _resolve_path_or_url(source: Union[str, Path]) -> Tuple[Path, bool]:
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
    LOG.info("HDFC load_pdf_tables: source=%s path=%s", source, path.name if path else path)
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
        LOG.info("HDFC load_pdf_tables: %s -> %d tables", path.name, len(tables))
        return tables
    finally:
        if is_temp:
            path.unlink(missing_ok=True)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _to_num(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).replace(" ", "").strip().rstrip("%")
    # European decimal: 0,48 -> 0.48 (comma as decimal separator)
    if re.match(r"^\d+,\d+$", s):
        s = s.replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _parse_hdfc_col(col: str) -> Tuple[Optional[datetime], str]:
    """Parse HDFC date formats: Dec'25, Q3 FY'26, 31.12.2025."""
    s = str(col).strip()
    # DD.MM.YYYY or 31.12.2025
    m = re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(y, mo, d), s
        except Exception:
            return None, s
    # Dec'25, Sep'25
    months = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    m = re.search(r"(\w{3})['\"]?(\d{2})", s, re.I)
    if m:
        mon, yy = m.group(1).lower()[:3], int(m.group(2))
        y = 2000 + yy if yy < 50 else 1900 + yy
        if mon in months:
            try:
                return datetime(y, months[mon], 1), s
            except Exception:
                return None, s
    # Q3 FY'26 -> Dec 2025
    m = re.search(r"Q([1234])[\s.]*FY['\s]*(\d{2})", s, re.I)
    if m:
        q, yy = int(m.group(1)), int(m.group(2))
        y = 2000 + yy
        end_month = {1: 6, 2: 9, 3: 12, 4: 3}[q]
        end_year = y if q != 4 else y - 1
        try:
            return datetime(end_year, end_month, 1), s
        except Exception:
            return None, s
    return None, s


def get_latest_col(df: pd.DataFrame) -> Optional[Any]:
    """Return column with most recent date."""
    if df is None or len(df.columns) == 0:
        return None
    best_dt, best_col = None, None
    for c in df.columns:
        dt, _ = _parse_hdfc_col(str(c))
        if dt and (best_dt is None or dt > best_dt):
            best_dt, best_col = dt, c
    if best_col:
        return best_col
    for c in df.columns:
        if "growth" not in str(c).lower() and "qoq" not in str(c).lower() and "yoy" not in str(c).lower():
            return c
    return df.columns[-1] if len(df.columns) > 0 else None


def get_previous_year_col(df: pd.DataFrame) -> Optional[Any]:
    """Return column with date ~1 year before latest."""
    latest = get_latest_col(df)
    if latest is None:
        return None
    latest_dt, _ = _parse_hdfc_col(str(latest))
    if latest_dt is None:
        return None
    prev_year = latest_dt.year - 1
    best_col, best_diff = None, float("inf")
    for c in df.columns:
        dt, _ = _parse_hdfc_col(str(c))
        if dt is None:
            continue
        if "yoy" in str(c).lower() or "growth" in str(c).lower() or "qoq" in str(c).lower():
            continue
        if dt.year == prev_year:
            diff = abs((dt.month - latest_dt.month) * 31 + (dt.day - latest_dt.day))
            if diff < best_diff:
                best_diff, best_col = diff, c
    return best_col


def _find_growth_col(df: pd.DataFrame) -> Optional[Any]:
    """Find YoY % growth column."""
    if df is None or len(df.columns) == 0:
        return None
    for c in df.columns:
        s = str(c).lower()
        if "qoq" in s or "quarter" in s:
            continue
        if "yoy" in s or "yoy" in str(c):
            return c
    return None


def _compute_growth_pct(current: Optional[float], prior: Optional[float]) -> Optional[float]:
    if current is None or prior is None or prior == 0:
        return None
    try:
        return round(((float(current) / float(prior)) - 1) * 100, 2)
    except (ValueError, TypeError, ZeroDivisionError):
        return None


def _bn_to_crores(val: Any, balance_sheet: bool = False) -> Optional[float]:
    """Investor PDF: Balance sheet (T1,T2) uses lakh cr (1 unit = 100,000 cr).
    P&L (T0) uses ₹ bn (1 bn = 100 cr)."""
    n = _to_num(val)
    if n is None:
        return None
    if balance_sheet and 10 <= n < 100:
        return round(n * 100_000, 2)
    return round(n * 100, 2)


# -----------------------------------------------------------------------------
# Investor PDF Extraction
# -----------------------------------------------------------------------------


def _extract_investor(tables_inv: List[pd.DataFrame]) -> Dict[str, Any]:
    extracted: Dict[str, Any] = {}

    # T0: P&L (₹ bn) — Net interest income, Operating expenses, Profit after tax
    t0 = tables_inv[0] if len(tables_inv) > 0 else None
    if t0 is not None and not t0.empty:
        col = get_latest_col(t0)
        growth_col = _find_growth_col(t0)
        if col:
            label_col = t0.columns[0]
            for _, row in t0.iterrows():
                val = str(row.get(label_col, "")).lower()
                n = row.get(col)
                g = row.get(growth_col) if growth_col else None
                num = _to_num(n)
                if "net interest income" in val and num is not None:
                    extracted["Net_Interest_Income"] = int(_bn_to_crores(n) or 0)
                    if g is not None:
                        extracted["Net_Interest_Income_Growth_Pct"] = _to_num(g)
                elif "operating expenses" in val and num is not None:
                    extracted["Operating_Expenditure"] = int(_bn_to_crores(n) or 0)
                    if g is not None:
                        extracted["Operating_Expenditure_Growth_Pct"] = _to_num(g)
                elif "profit after tax" in val and num is not None:
                    extracted["Net_Profit"] = int(_bn_to_crores(n) or 0)
                    if g is not None:
                        extracted["Net_Profit_Growth_Pct"] = _to_num(g)
                # Don't use "net revenue" for Operating_Profit - CASA has correct "Operating Profit before provisions"

    # T1: Balance sheet — Deposits, Net Advances (₹ bn)
    t1 = tables_inv[1] if len(tables_inv) > 1 else None
    if t1 is not None and not t1.empty:
        col = get_latest_col(t1)
        growth_col = _find_growth_col(t1)
        if col:
            label_col = t1.columns[0]
            for _, row in t1.iterrows():
                val = str(row.get(label_col, "")).lower()
                n = row.get(col)
                g = row.get(growth_col) if growth_col else None
                if "deposits" in val and "total" not in val:
                    v = _bn_to_crores(n, balance_sheet=True)
                    if v is not None:
                        extracted["Deposits"] = int(v)
                elif "net advances" in val:
                    v = _bn_to_crores(n, balance_sheet=True)
                    if v is not None:
                        extracted["Gross_Advances"] = int(v)

    # T2: Loans — Gross Advances, Retail, Corporate (₹ bn)
    t2 = tables_inv[2] if len(tables_inv) > 2 else None
    if t2 is not None and not t2.empty:
        col = get_latest_col(t2)
        if col:
            label_col = t2.columns[0]
            for _, row in t2.iterrows():
                val = str(row.get(label_col, "")).lower()
                n = row.get(col)
                if "gross advances" in val:
                    v = _bn_to_crores(n, balance_sheet=True)
                    if v is not None and extracted.get("Gross_Advances") is None:
                        extracted["Gross_Advances"] = int(v)
                elif "retail" in val and "assets" not in val and "mix" not in val:
                    v = _bn_to_crores(n, balance_sheet=True)
                    if v is not None:
                        extracted["Retail_Advances"] = int(v)
                elif "corporate" in val and "other wholesale" in val:
                    v = _bn_to_crores(n, balance_sheet=True)
                    if v is not None:
                        extracted["Corporate_Credit"] = int(v)
                elif "small and mid-market" in val:
                    v = _bn_to_crores(n, balance_sheet=True)
                    if v is not None:
                        extracted["MSME_Advances"] = int(v)
                elif "business banking" in val:
                    v = _bn_to_crores(n, balance_sheet=True)
                    if v is not None:
                        extracted["RAM_Advances"] = int(v)

    # T4: CASA ratio
    t4 = tables_inv[4] if len(tables_inv) > 4 else None
    if t4 is not None and not t4.empty:
        col = get_latest_col(t4)
        if col is None and "Dec'25" in str(t4.columns):
            col = "Dec'25"
        if col:
            label_col = t4.columns[0]
            for _, row in t4.iterrows():
                val = str(row.get(label_col, "")).lower()
                if "casa ratio" in val:
                    v = _to_num(row.get(col))
                    if v is not None:
                        extracted["CASA_Pct_Domestic"] = round(v, 2)
                    break

    # T6: PCR
    t6 = tables_inv[6] if len(tables_inv) > 6 else None
    if t6 is not None and not t6.empty:
        # PCR table has ex-agri 71%, 70% etc. Use last numeric column.
        for c in t6.columns:
            if "dec'25" in str(c).lower():
                for _, row in t6.iterrows():
                    txt = " ".join(str(row.get(x, "")) for x in t6.columns).lower()
                    if "ex-agri" in txt or "pcr" in txt:
                        v = _to_num(row.get(c))
                        if v is not None and 50 < v < 100:
                            extracted["PCR_Pct"] = round(v, 2)
                            break
                break

    # Business = Deposits + Gross_Advances
    dep = _to_num(extracted.get("Deposits"))
    adv = _to_num(extracted.get("Gross_Advances"))
    if dep is not None and adv is not None:
        extracted["Business"] = int(dep + adv)

    # CASA_Deposit_Domestic = Deposits * CASA%
    casa_pct = _to_num(extracted.get("CASA_Pct_Domestic"))
    if dep is not None and casa_pct is not None:
        extracted["CASA_Deposit_Domestic"] = int(dep * casa_pct / 100)
    if dep is not None and extracted.get("CASA_Deposit_Domestic") is None:
        extracted["Term_Deposit_Domestic"] = int(dep)

    # RAM % if we have RAM and Gross Advances
    ram = _to_num(extracted.get("RAM_Advances"))
    if ram is not None and adv is not None and adv != 0:
        extracted["RAM_Pct_Domestic"] = round(ram / adv * 100, 2)

    # Credit Deposit Ratio
    if dep is not None and adv is not None and dep != 0:
        extracted["Credit_Deposit_Ratio"] = round(adv / dep * 100, 2)

    return extracted


# -----------------------------------------------------------------------------
# CASA PDF Extraction
# -----------------------------------------------------------------------------


def _extract_casa(tables_casa: List[pd.DataFrame], extracted: Dict[str, Any]) -> None:
    """Extract from CASA T0 (standalone bank P&L, NPA, CAR, ROA)."""
    if len(tables_casa) == 0:
        return
    df = tables_casa[0]
    if df is None or df.empty:
        return

    # CASA T0 columns: first few are indices, then date columns
    # Find latest quarter column (31.12.2025 or similar)
    col = None
    for c in df.columns:
        if "31.12.2025" in str(c) or "31.12.2024" in str(c):
            col = c
            break
    if col is None:
        col = df.columns[2] if len(df.columns) > 2 else df.columns[-1]

    label_col = df.columns[1] if len(df.columns) > 1 else df.columns[0]

    for _, row in df.iterrows():
        val = str(row.get(label_col, "")).lower()
        n = row.get(col)
        num = _to_num(n)
        if num is None:
            continue
        if "gross npas" in val or "gross npa" in val:
            if extracted.get("Gross_NPA_Amount") is None:
                extracted["Gross_NPA_Amount"] = int(num)
        elif "net npas" in val or "net npa" in val:
            if extracted.get("Net_NPA_Amount") is None:
                extracted["Net_NPA_Amount"] = int(num)
        elif "% of gross npas" in val or "gross npas to gross advances" in val:
            extracted["Gross_NPA_Pct"] = round(num, 2)
        elif "% of net npas" in val or "net npas to net advances" in val:
            extracted["Net_NPA_Pct"] = round(num, 2)
        elif "capital adequacy" in val:
            extracted["CAR_Basel_III_Pct"] = round(num, 2)
        elif "return on assets" in val:
            extracted["ROA_Pct"] = round(num, 2)
        elif "interest earned" in val and "(a)" in val:
            if extracted.get("Interest_Income") is None:
                extracted["Interest_Income"] = int(num)
        elif "interest expended" in val or "interest expend" in val:
            if extracted.get("Interest_Expenditure") is None:
                extracted["Interest_Expenditure"] = int(num)
        elif "operating expenses" in val and "(i)+" in val:
            if extracted.get("Operating_Expenditure") is None:
                extracted["Operating_Expenditure"] = int(num)
        elif "employees cost" in val:
            if extracted.get("Employee_Cost") is None:
                extracted["Employee_Cost"] = int(num)
        elif "other operating expenses" in val:
            if extracted.get("Other_Expenditure") is None:
                extracted["Other_Expenditure"] = int(num)
        elif "total expenditure" in val and "excluding" in val:
            if extracted.get("Total_Expenditure") is None:
                extracted["Total_Expenditure"] = int(num)
        elif "total income" in val and "(1)+(2)" in val:
            if extracted.get("Total_Income") is None:
                extracted["Total_Income"] = int(num)
        elif "operating profit" in val and "before provisions" in val:
            if extracted.get("Operating_Profit") is None:
                extracted["Operating_Profit"] = int(num)
        elif "net profit" in val and "period" in val:
            if extracted.get("Net_Profit") is None:
                extracted["Net_Profit"] = int(num)
        elif "other" in val and "income" in val and "refer" in val:
            if extracted.get("Other_Income") is None:
                extracted["Other_Income"] = int(num)

    # Derived
    if extracted.get("Net_Interest_Income") is None:
        ii = _to_num(extracted.get("Interest_Income"))
        ie = _to_num(extracted.get("Interest_Expenditure"))
        if ii is not None and ie is not None:
            extracted["Net_Interest_Income"] = int(ii - ie)
    if extracted.get("Total_Expenditure") is None:
        oe = _to_num(extracted.get("Operating_Expenditure"))
        ie = _to_num(extracted.get("Interest_Expenditure"))
        if oe is not None and ie is not None:
            extracted["Total_Expenditure"] = int(oe + ie)


# -----------------------------------------------------------------------------
# Derived KPIs
# -----------------------------------------------------------------------------


def _compute_derived(extracted: Dict[str, Any]) -> None:
    business = _to_num(extracted.get("Business"))
    if business is not None and business != 0:
        op = _to_num(extracted.get("Operating_Profit"))
        if op is not None:
            extracted["Operating_Profit_to_Business_Pct"] = round(op / business * 100, 2)
        np_ = _to_num(extracted.get("Net_Profit"))
        if np_ is not None:
            extracted["Net_Profit_to_Business_Pct"] = round(np_ / business * 100, 2)
        nii = _to_num(extracted.get("Net_Interest_Income"))
        if nii is not None:
            extracted["Net_Interest_Income_to_Business_Pct"] = round(nii / business * 100, 2)

    if extracted.get("Cost_to_Income_Ratio") is None:
        opex = _to_num(extracted.get("Operating_Expenditure"))
        tot_inc = _to_num(extracted.get("Total_Income"))
        if opex is not None and tot_inc is not None and tot_inc != 0:
            extracted["Cost_to_Income_Ratio"] = round(opex / tot_inc * 100, 2)


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------


class HDFCKPIExtractor:
    """Extracts KPIs from HDFC Bank investor and CASA PDFs."""

    def __init__(
        self,
        investor_pdf: Optional[Union[str, Path]] = None,
        casa_pdf: Optional[Union[str, Path]] = None,
        tables_inv: Optional[List[pd.DataFrame]] = None,
        tables_casa: Optional[List[pd.DataFrame]] = None,
    ):
        self.investor_pdf = investor_pdf
        self.casa_pdf = casa_pdf
        self._tables_inv = tables_inv
        self._tables_casa = tables_casa

    def extract(self) -> Dict[str, Optional[Any]]:
        """Run extraction and return final KPIs (46 keys)."""
        LOG.info("HDFC extract: starting")
        tables_inv = self._tables_inv if self._tables_inv is not None else load_pdf_tables(self.investor_pdf)
        tables_casa = self._tables_casa if self._tables_casa is not None else load_pdf_tables(self.casa_pdf)
        LOG.info("HDFC extract: investor %d tables, CASA %d tables", len(tables_inv), len(tables_casa))

        extracted = _extract_investor(tables_inv)
        _extract_casa(tables_casa, extracted)
        _compute_derived(extracted)

        result = {k: extracted.get(k) for k in ALL_KPI_KEYS}
        base_keys = [k for k in ALL_KPI_KEYS if not k.endswith("_Growth_Pct")]
        for k in base_keys:
            if k in HDFC_PCT_KPI_KEYS:
                continue
            g = extracted.get(k + "_Growth_Pct")
            if g is not None:
                result[k + "_Growth_Pct"] = g

        LOG.info("HDFC extract: done, %d keys", len(result))
        return result

    def to_dict(self) -> Dict[str, Optional[Any]]:
        return self.extract()

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.extract(), indent=indent)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([self.extract()])
