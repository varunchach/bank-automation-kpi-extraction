"""
Fast Docling pipeline for OpenShift: tables + text from PDF without full-page OCR.
Filters to tables with relevant headers (KPI-related) so we pass only those; others
replaced with empty DataFrame to preserve original indices for IB/PNB extractors.
"""
from pathlib import Path
from typing import Tuple

import pandas as pd

# Headers that indicate a table is KPI-relevant (from IB/PNB extractor logic).
# Tables whose header text contains none of these are replaced with empty DataFrame.
RELEVANT_HEADER_KEYWORDS = frozenset({
    "profit", "income", "expenditure", "expense", "npa", "gnpa", "nnpa", "business",
    "deposit", "advances", "casa", "ratio", "capital", "car", "pcr", "gross", "net",
    "interest", "operating", "performance", "ratios", "movement", "snapshot",
    "breakup", "break up", "parameter", "sl no", "sl. no", "kpi", "provision",
    "revenue", "earned", "expend", "operating profit", "net profit", "deposits",
})


def _table_header_text(df: pd.DataFrame, max_cells: int = 50) -> str:
    """First row + column names as lowercase text for header matching."""
    if df is None or df.empty:
        return ""
    parts = [str(c).lower() for c in df.columns[:15]]
    if len(df) > 0:
        first = df.iloc[0].astype(str).str.lower()
        parts.extend(first.tolist()[:15])
    return " ".join(parts)


def _has_relevant_header(df: pd.DataFrame) -> bool:
    """True if table header contains any KPI-relevant keyword."""
    text = _table_header_text(df)
    return any(kw in text for kw in RELEVANT_HEADER_KEYWORDS)


def _filter_tables_by_header(tables: list[pd.DataFrame]) -> list[pd.DataFrame]:
    """Keep tables with relevant headers; replace others with empty DataFrame to preserve indices."""
    out = []
    for df in tables:
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            out.append(pd.DataFrame() if isinstance(df, pd.DataFrame) else pd.DataFrame())
            continue
        if _has_relevant_header(df):
            out.append(df)
        else:
            out.append(pd.DataFrame())
    return out


def _docling_converter_fast():
    """Docling converter with do_ocr=False and images_scale=1.0 for faster runs (table-focused)."""
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import PdfFormatOption

    pipeline_opts = PdfPipelineOptions(
        do_ocr=False,  # Skip OCR — use embedded text only (much faster)
        do_table_structure=True,
        images_scale=1.0,
    )
    try:
        import torch
        from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
        if torch.cuda.is_available():
            pipeline_opts.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CUDA)
    except Exception:
        pass
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)}
    )


def convert_pdf_once_fast(path: Path) -> Tuple[list[pd.DataFrame], str]:
    """Run fast Docling (no OCR): tables + markdown. Only tables with relevant headers are kept;
    others replaced with empty DataFrame so IB/PNB indices are preserved."""
    converter = _docling_converter_fast()
    result = converter.convert(str(path))
    doc = result.document
    tables = [t.export_to_dataframe(doc=doc) for t in doc.tables]
    tables = _filter_tables_by_header(tables)
    # Markdown: use full doc (for RAG) or we could filter by section; keep full for now
    markdown = doc.export_to_markdown() or ""
    return tables, markdown
