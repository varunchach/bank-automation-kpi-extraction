"""Streamlit app: URL inputs → Download → KPI Report (Excel) + RAG Chatbot with Web & Finance tools."""

from __future__ import annotations

# Version shown in UI (bump on releases)
APP_VERSION = "1.1.0"

import io
import logging
import os
import sys
from pathlib import Path

# Pipeline logging: goes to stderr (visible in oc logs / pod logs) and optionally to session for UI
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stderr,
)
LOG = logging.getLogger("kpi_app")
_pipeline_log: list[str] = []


class _PipelineLogHandler(logging.Handler):
    """Sends IB, PNB, and HDFC extractor logs into the sidebar Pipeline log so they are visible in the UI."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # Prefix so user can see which extractor (IB vs PNB vs HDFC)
            if "kpi_app.ib" in record.name:
                prefix = "IB: "
            elif "kpi_app.pnb" in record.name:
                prefix = "PNB: "
            elif "kpi_app.hdfc" in record.name:
                prefix = "HDFC: "
            else:
                prefix = ""
            _pipeline_log.append(f"[{record.levelname}] {prefix}{msg}")
            if len(_pipeline_log) > 150:
                _pipeline_log.pop(0)
        except Exception:
            pass


def _install_ib_pnb_pipeline_logging() -> None:
    """Forward kpi_app.ib, kpi_app.pnb, and kpi_app.hdfc loggers to the pipeline log (sidebar + oc logs)."""
    handler = _PipelineLogHandler()
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(message)s"))
    for name in ("kpi_app.ib", "kpi_app.pnb", "kpi_app.hdfc"):
        logger = logging.getLogger(name)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)


_install_ib_pnb_pipeline_logging()


def _plog(msg: str, level: str = "info") -> None:
    """Log to logger and append to pipeline log for UI. Flush so oc logs shows progress during run."""
    getattr(LOG, level)(msg)
    _pipeline_log.append(f"[{level.upper()}] {msg}")
    if len(_pipeline_log) > 100:
        _pipeline_log.pop(0)
    try:
        sys.stderr.flush()
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
COMBINED = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(COMBINED))
sys.path.insert(0, str(ROOT / "IB"))
sys.path.insert(0, str(ROOT / "PNB"))
sys.path.insert(0, str(ROOT / "HDFC"))

import streamlit as st
import pandas as pd
import requests

# All writable paths under /tmp (containers run non-root)
WORK_DIR = Path("/tmp") / "kpi_app"
DOWNLOADS_DIR = WORK_DIR / "downloads"
WORK_DIR.mkdir(parents=True, exist_ok=True)
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Browser-like headers to avoid 403 — BSE and similar sites often require Referer
DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/pdf,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com",
}

# -----------------------------------------------------------------------------
# Download PDFs
# -----------------------------------------------------------------------------


def download_pdf(url: str, dest: Path, progress_callback=None) -> Path:
    """Download PDF from URL to local path. Uses browser-like headers to avoid 403."""
    url = str(url).strip()
    _plog(f"Download starting: {dest.name}")
    if not url.startswith(("http://", "https://")):
        _plog("Invalid URL", "error")
        raise ValueError("Invalid URL")
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, headers=DOWNLOAD_HEADERS, timeout=120, stream=True)
    if r.status_code == 403:
        _plog(f"403 Forbidden for {dest.name}", "error")
        raise RuntimeError("403 Forbidden — server blocked the request.")
    r.raise_for_status()
    total = int(r.headers.get("content-length", 0)) or None
    written = 0
    if progress_callback:
        progress_callback(0.0)
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
            written += len(chunk)
            if progress_callback and total and total > 0:
                progress_callback(written / total)
    if progress_callback:
        progress_callback(1.0)
    _plog(f"Download OK: {dest.name} ({written} bytes)")
    return dest


def _ensure_rapidocr_writable_path() -> None:
    """Point RapidOCR model cache to writable dir under /tmp."""
    (WORK_DIR / "rapidocr").mkdir(parents=True, exist_ok=True)
    import rapidocr.inference_engine.base as _rapid_base
    _rapid_base.InferSession.DEFAULT_MODEL_PATH = WORK_DIR / "rapidocr"


def run_unified_extraction(
    ib_inv_path: Path,
    ib_casa_path: Path,
    pnb_inv_path: Path,
    pnb_casa_path: Path,
    hdfc_inv_path: Path | None = None,
    hdfc_casa_path: Path | None = None,
) -> pd.DataFrame:
    """Run IB + PNB (+ optional HDFC) extraction and return combined DataFrame."""
    _ensure_rapidocr_writable_path()
    from IB.kpi_extractor import IndianBankKPIExtractor
    from PNB.pnb_extractor import PNBKPIExtractor
    from kpi_ranking import compute_rank
    from kpi_report_format import build_report_df

    kpis_ib = IndianBankKPIExtractor(ib_inv_path, ib_casa_path).extract()
    kpis_pnb = PNBKPIExtractor(pnb_inv_path, pnb_casa_path, data_dir=ROOT / "data").extract()
    kpis_hdfc = None
    if hdfc_inv_path and hdfc_casa_path and hdfc_inv_path.exists() and hdfc_casa_path.exists():
        from HDFC.hdfc_extractor import HDFCKPIExtractor
        kpis_hdfc = HDFCKPIExtractor(hdfc_inv_path, hdfc_casa_path).extract()
    return build_report_df(kpis_ib, kpis_pnb, compute_rank, kpis_hdfc=kpis_hdfc)


def run_unified_extraction_from_tables(
    ib_inv_tables: list[pd.DataFrame],
    ib_casa_tables: list[pd.DataFrame],
    pnb_inv_tables: list[pd.DataFrame],
    pnb_casa_tables: list[pd.DataFrame],
    hdfc_inv_tables: list[pd.DataFrame] | None = None,
    hdfc_casa_tables: list[pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """Run IB + PNB (+ optional HDFC) extraction from pre-converted tables (no second Docling run)."""
    _ensure_rapidocr_writable_path()
    from IB.kpi_extractor import IndianBankKPIExtractor
    from PNB.pnb_extractor import PNBKPIExtractor
    from kpi_ranking import compute_rank
    from kpi_report_format import build_report_df

    kpis_ib = IndianBankKPIExtractor(None, None, tables_inv=ib_inv_tables, tables_casa=ib_casa_tables).extract()
    kpis_pnb = PNBKPIExtractor(None, None, data_dir=ROOT / "data", tables_inv=pnb_inv_tables, tables_casa=pnb_casa_tables).extract()
    kpis_hdfc = None
    if hdfc_inv_tables is not None and hdfc_casa_tables is not None and len(hdfc_inv_tables) > 0 and len(hdfc_casa_tables) > 0:
        from HDFC.hdfc_extractor import HDFCKPIExtractor
        kpis_hdfc = HDFCKPIExtractor(None, None, tables_inv=hdfc_inv_tables, tables_casa=hdfc_casa_tables).extract()
    return build_report_df(kpis_ib, kpis_pnb, compute_rank, kpis_hdfc=kpis_hdfc)


def _docling_converter():
    """Shared Docling converter (full-page OCR, scale 2.0). Uses GPU when available."""
    _ensure_rapidocr_writable_path()
    from docling.document_converter import DocumentConverter
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import OcrAutoOptions, PdfPipelineOptions
    from docling.document_converter import PdfFormatOption
    pipeline_opts = PdfPipelineOptions(
        ocr_options=OcrAutoOptions(force_full_page_ocr=True),
        images_scale=2.0,
    )
    try:
        import torch
        from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
        if torch.cuda.is_available():
            pipeline_opts.accelerator_options = AcceleratorOptions(device=AcceleratorDevice.CUDA)
            _plog("Docling using GPU (CUDA)")
        else:
            _plog("Docling using CPU (no CUDA)")
    except Exception as e:
        _plog(f"Docling accelerator fallback to default: {e}")
    return DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)}
    )


def convert_pdf_once(path: Path) -> tuple[list[pd.DataFrame], str]:
    """Run Docling once per PDF; return (tables, markdown). Use for both KPI and RAG to avoid double conversion."""
    _plog(f"Docling converting: {path.name}")
    converter = _docling_converter()
    result = converter.convert(str(path))
    doc = result.document
    tables = [t.export_to_dataframe(doc=doc) for t in doc.tables]
    markdown = doc.export_to_markdown() or ""
    _plog(f"Docling OK: {path.name} -> {len(tables)} tables, {len(markdown)} chars markdown")
    return tables, markdown


def extract_pdf_text(path: Path) -> str:
    """Extract text from PDF using Docling (used only when no pre-converted doc)."""
    _, markdown = convert_pdf_once(path)
    return markdown


# -----------------------------------------------------------------------------
# Chatbot Tools: Tavily Web Search & Yahoo Finance
# -----------------------------------------------------------------------------


def web_search(query: str, max_results: int = 5, tavily_api_key: str | None = None) -> str:
    """Search the web via Tavily. Returns concatenated snippets."""
    try:
        from tavily import TavilyClient
        key = (tavily_api_key or "").strip() or getattr(
            __import__("llm_config", fromlist=["TAVILY_API_KEY"]), "TAVILY_API_KEY", ""
        )
        if not key:
            return "Tavily API key not configured. Set TAVILY_API_KEY in llm_config or env."
        client = TavilyClient(api_key=key)
        results = client.search(query, max_results=max_results, search_depth="basic", topic="general")
        snippets = []
        for r in (results.get("results") or []):
            title = r.get("title", "")
            content = r.get("content", r.get("snippet", ""))
            url = r.get("url", "")
            snippets.append(f"[{title}]({url})\n{content}")
        return "\n\n".join(snippets) if snippets else "No results found."
    except Exception as e:
        return f"Web search failed: {e}"


def yahoo_finance(symbols: list[str]) -> str:
    """Fetch stock info from Yahoo Finance. Use INDIANB.NS (Indian Bank), PNB.NS (PNB)."""
    try:
        import yfinance as yf
        lines = []
        for sym in symbols:
            sym = sym.strip().upper()
            if not sym:
                continue
            ticker = yf.Ticker(sym)
            info = ticker.info
            name = info.get("longName", sym)
            price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
            if price is None:
                hist = ticker.history(period="5d")
                price = float(hist["Close"].iloc[-1]) if not hist.empty else None
            if price is None:
                lines.append(f"{name} ({sym}): No price data")
                continue
            price = float(price)
            prev = info.get("previousClose")
            prev = float(prev) if prev is not None else None
            change_str = ""
            if prev and prev > 0:
                change_pct = (price - prev) / prev * 100
                change_str = f" ({change_pct:+.2f}%)"
            lines.append(f"{name} ({sym}): ₹{price:.2f}{change_str}")
        return "\n".join(lines) if lines else "No data."
    except Exception as e:
        return f"Yahoo Finance failed: {e}"


# Tool definitions for agentic RAG (OpenAI-compatible)
AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for news, market updates, or general information. Use for queries about recent events, headlines, or external facts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query string"},
                    "max_results": {"type": "integer", "description": "Max results", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_info",
            "description": "Get live stock prices for Indian Bank (INDIANB.NS), PNB (PNB.NS), or HDFC Bank (HDFCBANK.NS). Use for share price, trading, or market data queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Stock symbols: INDIANB.NS, PNB.NS, or both",
                    },
                },
                "required": ["symbols"],
            },
        },
    },
]


def _rule_based_answer(question: str, pdf_text: str, kpi_table: str | None, use_web: bool, use_finance: bool) -> str:
    """Fallback: no LLM — use KPI lookup + keyword search + tools. Works with zero external dependencies."""
    q_lower = question.lower()
    parts = []

    # Yahoo Finance for stock queries
    if use_finance and any(k in q_lower for k in ["stock", "share price", "trading", "INDIANB", "PNB", "HDFC", "price"]):
        syms = ["INDIANB.NS", "PNB.NS", "HDFCBANK.NS"]
        if "indian bank" in q_lower and "hdfc" not in q_lower:
            syms = ["INDIANB.NS"]
        elif "pnb" in q_lower and "indian" not in q_lower and "hdfc" not in q_lower:
            syms = ["PNB.NS"]
        elif "hdfc" in q_lower:
            syms = ["HDFCBANK.NS"]
        parts.append("**Live stock data:**\n" + yahoo_finance(syms))

    # Web search for news
    if use_web and any(k in q_lower for k in ["news", "latest", "recent", "today"]):
        parts.append("**Web search:**\n" + web_search(question, max_results=3))

    # KPI lookup — parse table for direct answers
    if kpi_table:
        lines = kpi_table.split("\n")
        for line in lines:
            if "Rank" in line:
                continue
            for term in ["net profit", "npa", "gnpa", "nnpa", "casa", "deposits", "advances", "roa", "roe", "nim", "car", "pcr"]:
                if term in q_lower and term.replace(" ", "_")[:3] in line.lower():
                    parts.append(f"**From KPI report:**\n{line.strip()}")
                    break

    # Keyword search in PDF text
    words = [w for w in question.replace("?", "").split() if len(w) > 3]
    if words and pdf_text:
        doc_lower = pdf_text.lower()
        for w in words[:5]:
            if w.lower() in doc_lower:
                idx = doc_lower.find(w.lower())
                snippet = pdf_text[max(0, idx - 80) : idx + len(w) + 120]
                if snippet and snippet not in str(parts):
                    parts.append(f"**Relevant excerpt:**\n...{snippet.strip()}...")
                break

    if parts:
        return "\n\n".join(parts) + "\n\n*(Rule-based response — no LLM. For natural answers, set an LLM endpoint in the sidebar.)*"
    return "No matching data found. Try asking about specific KPIs (e.g. Net Profit, GNPA %), stock prices, or recent news. You can also configure an LLM endpoint in the sidebar for fuller answers."


def _execute_tool(name: str, arguments: dict, tavily_api_key: str | None) -> str:
    """Execute a tool by name and return result string."""
    import json
    if name == "web_search":
        query = arguments.get("query", "")
        max_results = int(arguments.get("max_results", 5))
        return web_search(query, max_results=max_results, tavily_api_key=tavily_api_key)
    if name == "get_stock_info":
        syms = arguments.get("symbols", [])
        if isinstance(syms, str):
            syms = [s.strip() for s in syms.replace(",", " ").split() if s.strip()]
        if not syms:
            syms = ["INDIANB.NS", "PNB.NS", "HDFCBANK.NS"]
        return yahoo_finance(syms)
    return f"Unknown tool: {name}"


def _append_tool_results_if_mentioned(
    answer: str, question: str, tavy_key: str | None
) -> str:
    """If the LLM put a tool call in text instead of using tool_calls, run the tool and append result."""
    out = answer
    q_lower = question.lower()
    # Detect get_stock_info mentioned in text (e.g. "[get_stock_info(symbols=[...])]" or "get_stock_info(...)")
    # Skip if we already have live stock data (e.g. from fallback)
    if ("get_stock_info" in answer or "stock price" in answer.lower()) and "**Live stock data:**" not in answer:
        syms = ["INDIANB.NS", "PNB.NS"]
        if "pnb" in q_lower and "indian" not in q_lower:
            syms = ["PNB.NS"]
        elif "indian bank" in q_lower:
            syms = ["INDIANB.NS"]
        stock_result = yahoo_finance(syms)
        if stock_result and "failed" not in stock_result.lower():
            out = out.rstrip() + "\n\n**Live stock data:**\n" + stock_result
    # Detect web_search mentioned; skip if already present
    if "web_search" in answer and "**Web search:**" not in answer and ("news" in q_lower or "latest" in q_lower or "recent" in q_lower):
        search_result = web_search(question, max_results=3, tavily_api_key=tavy_key)
        if search_result:
            out = out.rstrip() + "\n\n**Web search:**\n" + search_result
    return out


def answer_question(
    pdf_text: str,
    kpi_table: str | None,
    question: str,
    kpi_df=None,
    entities_json: dict | None = None,
    llm_base_url: str | None = None,
    llm_api_key: str | None = None,
    llm_model: str | None = None,
    tavily_api_key: str | None = None,
    use_web_search: bool = True,
    use_yahoo_finance: bool = True,
    use_agentic: bool = True,
) -> str:
    """Answer using Agentic RAG (LLM + tools) or rule-based fallback. Pass entities as JSON to LLM."""
    import json
    from llm_config import LLM_BASE_URL, LLM_API_KEY as _LLM_KEY, LLM_MODEL as _LLM_MODEL, TAVILY_API_KEY as _TAVILY_KEY

    base_url = (llm_base_url or "").strip() or LLM_BASE_URL
    api_key = (llm_api_key or "").strip() or _LLM_KEY or ""
    model = (llm_model or "").strip() or _LLM_MODEL or "Llama-4-Scout-17B-16E-W4A16"
    tavy_key = (tavily_api_key or "").strip() or _TAVILY_KEY or ""

    if entities_json is None:
        from rag_milvus import search_chunks, get_fallback_chunks, build_entities_json
        retrieved = search_chunks(question)
        # When RAG returns nothing (e.g. pymilvus not installed), use chunked pdf_text so LLM gets extracted context
        if not retrieved and pdf_text:
            retrieved = get_fallback_chunks(pdf_text, max_chunks=5)
        entities_json = build_entities_json(kpi_df, retrieved)
    context_str = json.dumps(entities_json, indent=2, default=str)
    full_context = f"## Extracted Entities (JSON)\n```json\n{context_str}\n```"

    def fallback():
        return _rule_based_answer(question, pdf_text, kpi_table, use_web_search, use_yahoo_finance)

    if not base_url or not api_key:
        return fallback()

    try:
        from openai import OpenAI
        client = OpenAI(base_url=base_url.rstrip("/") + ("/v1" if not base_url.rstrip().endswith("/v1") else ""), api_key=api_key)
    except Exception as e:
        return f"OpenAI client error: {e}\n\n" + fallback()

    system_prompt = (
        "You are an analyst assistant for multi-bank KPI comparison (IB, PNB, HDFC). Use the provided JSON entities (kpis and retrieved_chunks) to answer. "
        "kpis contains the KPI report. retrieved_chunks are relevant document excerpts. "
        "When you need live data, use the tools: web_search for news/market updates, get_stock_info for share prices (INDIANB.NS, PNB.NS, HDFCBANK.NS). "
        "IMPORTANT: Answer in a natural, conversational way. Give a direct, synthesized response. Do NOT use step-by-step formats, "
        "numbered steps (Step 1, Step 2), meta-commentary like 'The final answer is', or 'Let me extract...'. "
        "Write as if in a brief analyst note: concise, flowing prose. Cite figures when relevant."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context (entities as JSON):\n{full_context}\n\nQuestion: {question}\n\nAnswer based on the entities. Use tools if you need live stock prices or recent news."},
    ]

    max_iterations = 3
    tools = AGENT_TOOLS if (use_agentic and (use_web_search or use_yahoo_finance)) else None
    for _ in range(max_iterations):
        kwargs = {"model": model, "messages": messages, "max_tokens": 1500}
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            r = client.chat.completions.create(**kwargs)
        except Exception as e:
            if tools and "tool" in str(e).lower():
                tools = None
                continue
            return f"LLM error: {e}\n\n" + fallback()
        msg = r.choices[0].message

        if not getattr(msg, "tool_calls", None) or not msg.tool_calls:
            text = (msg.content or "").strip()
            if text:
                text = _append_tool_results_if_mentioned(text, question, tavy_key)
            return text if text else "No response."

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = _execute_tool(name, args, tavy_key)
            messages.append({"role": "assistant", "content": None, "tool_calls": [tc]})
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })

    fb = fallback()
    return _append_tool_results_if_mentioned(fb, question, tavy_key)


# -----------------------------------------------------------------------------
# Streamlit UI
# -----------------------------------------------------------------------------


def main():
    st.set_page_config(
        page_title="Multi-Bank KPI Analyst",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    st.markdown("""
        <style>
        [data-testid="stChatInput"] { padding: 1rem; }
        [data-testid="stChatMessage"] { min-height: 2rem; }
        .stExpander summary { font-weight: 600; }
        </style>
    """, unsafe_allow_html=True)
    st.title("📊 Multi-Bank KPI Analyst (IB · PNB · HDFC)")
    st.caption("KPI extraction (Value | Growth % | Rank) • RAG chatbot with web search & Yahoo Finance")
    st.sidebar.markdown(f"**App version:** `{APP_VERSION}`")
    with st.sidebar.expander("Pipeline log", expanded=True):
        if _pipeline_log:
            st.text("\n".join(_pipeline_log[-80:]))
        else:
            st.caption("Run « Generate Summary Report » to see step-by-step logs here and in pod logs (oc logs).")

    try:
        from llm_config import LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, TAVILY_API_KEY
    except ImportError:
        LLM_BASE_URL = LLM_API_KEY = LLM_MODEL = TAVILY_API_KEY = ""
    use_agentic = use_web = use_finance = True

    # PDF URLs: load from bse_nse_input.txt if present, else use defaults
    _DEFAULT_IB_INV = "https://www.bseindia.com/xml-data/corpfiling/AttachHis/06fc511a-9d0e-43df-a830-13b9dea59cba.pdf"
    _DEFAULT_IB_CASA = "https://www.bseindia.com/xml-data/corpfiling/AttachHis/7b26747e-1f53-4fc5-aa28-465e03617758.pdf"
    _DEFAULT_PNB_INV = "https://www.bseindia.com/xml-data/corpfiling/AttachHis/aedaff30-a173-45db-ac13-188e1257f05c.pdf"
    _DEFAULT_PNB_CASA = "https://www.bseindia.com/xml-data/corpfiling/AttachHis/2e4de758-cbe7-4e01-82dd-7acca9ec9f2d.pdf"
    _input_file = COMBINED / "bse_nse_input.txt"
    if _input_file.exists():
        _lines = [u.strip() for u in _input_file.read_text().splitlines() if u.strip() and not u.strip().startswith("#")]
        if len(_lines) >= 4:
            BSE_IB_INV, BSE_IB_CASA, BSE_PNB_INV, BSE_PNB_CASA = _lines[0], _lines[1], _lines[2], _lines[3]
        else:
            BSE_IB_INV, BSE_IB_CASA, BSE_PNB_INV, BSE_PNB_CASA = _DEFAULT_IB_INV, _DEFAULT_IB_CASA, _DEFAULT_PNB_INV, _DEFAULT_PNB_CASA
    else:
        BSE_IB_INV, BSE_IB_CASA, BSE_PNB_INV, BSE_PNB_CASA = _DEFAULT_IB_INV, _DEFAULT_IB_CASA, _DEFAULT_PNB_INV, _DEFAULT_PNB_CASA

    with st.expander("📥 PDF URLs (IB, PNB, HDFC — optional)", expanded=True):
        st.caption("Defaults from **bse_nse_input.txt** if present (6 URLs: IB Investor, IB CASA, PNB Investor, PNB CASA, HDFC Investor, HDFC CASA). HDFC URLs are optional.")
        st.info("**To run a report:** Click **Generate Summary Report** below once. Do not refresh. The run can take **10–20 minutes** (4–6 PDFs on CPU).")
        c1, c2, c3 = st.columns(3)
        with c1:
            ib_inv_url = st.text_input("IB Investor URL", value=BSE_IB_INV, key="ib_inv")
            ib_casa_url = st.text_input("IB CASA URL", value=BSE_IB_CASA, key="ib_casa")
        with c2:
            pnb_inv_url = st.text_input("PNB Investor URL", value=BSE_PNB_INV, key="pnb_inv")
            pnb_casa_url = st.text_input("PNB CASA URL", value=BSE_PNB_CASA, key="pnb_casa")
        with c3:
            hdfc_inv_url = st.text_input("HDFC Bank Investor URL (optional)", value="", key="hdfc_inv", placeholder="Leave empty to skip HDFC")
            hdfc_casa_url = st.text_input("HDFC Bank CASA URL (optional)", value="", key="hdfc_casa", placeholder="Leave empty to skip HDFC")

        if st.button("Generate Summary Report", type="primary", help="Starts download + conversion + KPI + RAG. One click; wait 10–20 min."):
            _pipeline_log.clear()
            _plog("Report generation started")
            urls = [ib_inv_url, ib_casa_url, pnb_inv_url, pnb_casa_url]
            labels = ["IB Investor", "IB CASA", "PNB Investor", "PNB CASA"]
            if not all(u.strip() for u in urls):
                missing = [l for l, u in zip(labels, urls) if not u.strip()]
                st.error(f"Missing: {', '.join(missing)}")
            else:
                failed = []
                downloads = [
                    (ib_inv_url.strip(), DOWNLOADS_DIR / "ib_investor.pdf", "IB Investor"),
                    (ib_casa_url.strip(), DOWNLOADS_DIR / "ib_casa.pdf", "IB CASA"),
                    (pnb_inv_url.strip(), DOWNLOADS_DIR / "pnb_investor.pdf", "PNB Investor"),
                    (pnb_casa_url.strip(), DOWNLOADS_DIR / "pnb_casa.pdf", "PNB CASA"),
                ]
                include_hdfc = bool(hdfc_inv_url.strip() and hdfc_casa_url.strip())
                if include_hdfc:
                    downloads.extend([
                        (hdfc_inv_url.strip(), DOWNLOADS_DIR / "hdfc_investor.pdf", "HDFC Investor"),
                        (hdfc_casa_url.strip(), DOWNLOADS_DIR / "hdfc_casa.pdf", "HDFC CASA"),
                    ])
                n_dl = len(downloads)
                dl_progress = st.progress(0.0)
                for i, (url, dest, label) in enumerate(downloads):
                    try:
                        def make_cb(idx, total):
                            return lambda p: dl_progress.progress((idx + p) / total)
                        download_pdf(url, dest, progress_callback=make_cb(i, n_dl))
                    except Exception as e:
                        failed.append(f"{label}: {e}")
                if failed:
                    _plog(f"Download failed: {failed}", "error")
                    dl_progress.empty()
                    st.error("Download failed:\n" + "\n".join(failed))
                    st.stop()
                ib_inv = DOWNLOADS_DIR / "ib_investor.pdf"
                ib_casa = DOWNLOADS_DIR / "ib_casa.pdf"
                pnb_inv = DOWNLOADS_DIR / "pnb_investor.pdf"
                pnb_casa = DOWNLOADS_DIR / "pnb_casa.pdf"
                hdfc_inv = DOWNLOADS_DIR / "hdfc_investor.pdf" if include_hdfc else None
                hdfc_casa = DOWNLOADS_DIR / "hdfc_casa.pdf" if include_hdfc else None
                dl_progress.progress(1.0)
                dl_progress.empty()
                st.success("PDFs downloaded.")

                paths = [ib_inv, ib_casa, pnb_inv, pnb_casa]
                labels = ["IB Investor", "IB CASA", "PNB Investor", "PNB CASA"]
                if include_hdfc:
                    paths.extend([hdfc_inv, hdfc_casa])
                    labels.extend(["HDFC Investor", "HDFC CASA"])
                ext_progress = st.progress(0.0)
                # Single Docling conversion per PDF → tables + markdown (no second pass)
                converted = []
                for j, (p, label) in enumerate(zip(paths, labels)):
                    ext_progress.progress(0.05 + 0.70 * (j + 1) / len(paths))
                    st.caption(f"⏳ Converting {label} ({j+1}/{len(paths)}) — one pass for KPI + RAG...")
                    try:
                        tables, markdown = convert_pdf_once(p)
                        converted.append((p.name, tables, markdown))
                    except Exception as e:
                        _plog(f"Docling FAILED for {p.name}: {e}", "error")
                        ext_progress.empty()
                        st.exception(e)
                        st.stop()
                _plog("Building KPI report from extracted tables")
                st.caption("Building KPI report from extracted tables...")
                try:
                    hdfc_inv_tbl = converted[4][1] if include_hdfc and len(converted) > 4 else None
                    hdfc_casa_tbl = converted[5][1] if include_hdfc and len(converted) > 5 else None
                    df = run_unified_extraction_from_tables(
                        converted[0][1], converted[1][1], converted[2][1], converted[3][1],
                        hdfc_inv_tables=hdfc_inv_tbl,
                        hdfc_casa_tables=hdfc_casa_tbl,
                    )
                    _plog(f"KPI report OK: {len(df)} rows, columns: {list(df.columns)[:5]}...")
                except Exception as e:
                    _plog(f"KPI extraction FAILED: {e}", "error")
                    ext_progress.empty()
                    st.exception(e)
                    st.stop()
                combined_text = "\n\n".join(f"--- {name} ---\n{md}" for name, _, md in converted)
                st.session_state["pdf_text"] = combined_text
                st.session_state["pdf_text_by_file"] = [(name, md) for name, _, md in converted]
                ext_progress.progress(0.85)
                st.session_state["report_generated"] = True
                st.session_state["pdf_paths"] = list(paths)
                st.session_state["kpi_df"] = df
                try:
                    _plog("RAG indexing starting (Milvus + embeddings)")
                    with st.spinner("Indexing documents for RAG (Milvus)..."):
                        from rag_milvus import index_documents
                        n_chunks = index_documents(st.session_state["pdf_text"])
                    _plog(f"RAG indexing OK: {n_chunks} chunks indexed")
                except Exception as idx_err:
                    _plog(f"RAG indexing FAILED: {idx_err}", "error")
                    st.warning(f"RAG indexing failed (chat may be limited): {idx_err}")
                ext_progress.progress(1.0)
                ext_progress.empty()
                _plog("Report generation completed successfully")
                st.success("Report ready. KPI table and downloads are below.")
                # Show report in THIS run so user sees it even if connection timed out during the long run (rerun may never reach browser)
                st.subheader("📋 Results")
                if df is not None and not df.empty:
                    with st.expander("KPI Report (Value | Growth % | Rank)", expanded=True):
                        st.dataframe(df.astype(str), use_container_width=True)
                    buf = io.BytesIO()
                    df.astype(str).to_excel(buf, index=False, engine="openpyxl")
                    buf.seek(0)
                    st.download_button("Download Excel", data=buf, file_name="KPI_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_excel_after_run")
                else:
                    st.warning("Report was generated but the KPI table is empty. Check extraction logs.")
                st.subheader("📥 Downloaded outputs")
                for p in paths:
                    try:
                        size = p.stat().st_size if p.exists() else 0
                        size_str = f"{size / 1024:.1f} KB" if size else "—"
                        st.caption(f"• {p.name} — {size_str}")
                    except Exception:
                        st.caption(f"• {p.name}")
                pdf_text = "\n\n".join(f"--- {name} ---\n{md}" for name, _, md in converted)
                if pdf_text:
                    st.download_button("Download extracted text (all PDFs)", data=pdf_text.encode("utf-8"), file_name="extracted_text.txt", mime="text/plain", key="dl_extracted_after_run")
                st.divider()
                # Rerun so chat and sidebar reflect report_generated; report already shown above
                st.rerun()

    # KPI report (Value | Growth % | Rank per KPI)
    if st.session_state.get("report_generated"):
        st.subheader("📋 Results")
        kpi_df = st.session_state.get("kpi_df")
        if kpi_df is not None and not kpi_df.empty:
            with st.expander("KPI Report (Value | Growth % | Rank)", expanded=True):
                st.dataframe(kpi_df.astype(str), use_container_width=True)
                buf = io.BytesIO()
                kpi_df.astype(str).to_excel(buf, index=False, engine="openpyxl")
                buf.seek(0)
                st.download_button("Download Excel", data=buf, file_name="KPI_Report.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.warning("Report was generated but the KPI table is empty. Check extraction logs.")

        # Downloaded PDFs and extracted text
        st.subheader("📥 Downloaded outputs")
        pdf_paths = st.session_state.get("pdf_paths") or []
        pdf_text_by_file = st.session_state.get("pdf_text_by_file") or []
        if pdf_paths:
            col1, col2 = st.columns([1, 1])
            with col1:
                st.markdown("**Downloaded PDFs**")
                for p in pdf_paths:
                    try:
                        size = p.stat().st_size if p.exists() else 0
                        size_str = f"{size / 1024:.1f} KB" if size else "—"
                        st.caption(f"• {p.name} — {size_str}")
                    except Exception:
                        st.caption(f"• {p.name}")
            with col2:
                pdf_text = st.session_state.get("pdf_text") or ""
                if pdf_text:
                    st.markdown("**Extracted text**")
                    st.download_button(
                        "Download extracted text (all PDFs)",
                        data=pdf_text.encode("utf-8"),
                        file_name="extracted_text.txt",
                        mime="text/plain",
                        key="dl_extracted_all",
                    )
            if pdf_text_by_file:
                with st.expander("View extracted text by file", expanded=False):
                    for name, md in pdf_text_by_file:
                        with st.expander(f"📄 {name}", expanded=False):
                            st.text_area("Extracted text", value=md[:50000] + ("…" if len(md) > 50000 else ""), height=200, key=f"text_{name}", disabled=True, label_visibility="collapsed")
                            if len(md) > 50000:
                                st.caption(f"Showing first 50,000 characters of {len(md):,} total. Use « Download extracted text » for full content.")
        st.divider()

    st.divider()
    st.subheader("💬 Chat")
    st.caption("Ask about documents, KPIs, stock prices, or news. Generate report first.")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    if st.session_state.get("report_generated") and st.session_state.get("pdf_paths"):
        pdf_paths = st.session_state["pdf_paths"]
        pdf_text = st.session_state.get("pdf_text") or ""
        if not pdf_text:
            with st.spinner("Extracting text from PDFs (one-time, ~5 min)..."):
                texts = [f"--- {p.name} ---\n" + extract_pdf_text(p) for p in pdf_paths]
                pdf_text = "\n\n".join(texts)
                st.session_state["pdf_text"] = pdf_text
                with st.spinner("Indexing for RAG (Milvus)..."):
                    from rag_milvus import index_documents
                    index_documents(pdf_text)
        kpi_df = st.session_state.get("kpi_df")
        kpi_table = kpi_df.to_string(index=False) if kpi_df is not None and not kpi_df.empty else None

        if st.session_state["chat_history"] and st.button("🗑️ Clear chat", key="clear_chat"):
            st.session_state["chat_history"] = []
            st.rerun()
        def _render_sources(sources: dict | None, key_prefix: str = "ref") -> None:
            """Render References expander from stored sources (retrieved_chunks + KPI)."""
            if not sources:
                return
            chunks = sources.get("retrieved_chunks") or []
            kpi_used = sources.get("kpi_used", False)
            if not chunks and not kpi_used:
                return
            with st.expander("📎 References (sources used for this answer)", expanded=False):
                if kpi_used:
                    st.markdown("**KPI report** (IB vs PNB vs HDFC)")
                    st.caption("Key metrics from the extracted report were used as context.")
                if chunks:
                    st.markdown("**Document excerpts** (from extracted PDFs)")
                    for i, c in enumerate(chunks, 1):
                        snippet = (c[:400] + "…") if len(c) > 400 else c
                        st.text_area(f"[{i}]", value=snippet, height=80, disabled=True, key=f"{key_prefix}_{i}")

        chat_container = st.container()
        with chat_container:
            for hist_idx, msg in enumerate(st.session_state["chat_history"]):
                with st.chat_message(msg["role"]):
                    st.write(msg["content"])
                    if msg.get("role") == "assistant" and msg.get("sources"):
                        _render_sources(msg["sources"], key_prefix=f"ref_hist_{hist_idx}")

        # If we have a pending question from last submit, show it and generate answer now
        pending = st.session_state.pop("pending_question", None)
        if pending:
            from rag_milvus import search_chunks, get_fallback_chunks, build_entities_json
            retrieved = search_chunks(pending)
            if not retrieved and pdf_text:
                retrieved = get_fallback_chunks(pdf_text, max_chunks=5)
            entities_json = build_entities_json(kpi_df, retrieved)
            with st.chat_message("assistant"):
                with st.status("Thinking...", expanded=True, state="running") as status:
                    answer = answer_question(
                        pdf_text,
                        kpi_table,
                        pending,
                        kpi_df=kpi_df,
                        entities_json=entities_json,
                        llm_base_url=LLM_BASE_URL,
                        llm_api_key=LLM_API_KEY,
                        llm_model=LLM_MODEL,
                        tavily_api_key=TAVILY_API_KEY,
                        use_web_search=use_web,
                        use_yahoo_finance=use_finance,
                        use_agentic=use_agentic,
                    )
                    status.update(label="Done", state="complete")
                st.write(answer)
                _render_sources({"retrieved_chunks": retrieved, "kpi_used": kpi_df is not None and not kpi_df.empty})
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": answer,
                "sources": {"retrieved_chunks": retrieved, "kpi_used": kpi_df is not None and not kpi_df.empty},
            })
            st.rerun()

        user_q = st.chat_input("Ask about IB, PNB, HDFC, KPIs, stock prices, or news...")
        if user_q:
            st.session_state["chat_history"].append({"role": "user", "content": user_q})
            st.session_state["pending_question"] = user_q
            st.rerun()
    else:
        st.info("Generate a report first (expand « Configure PDF URLs » above) to enable the chatbot.")


if __name__ == "__main__":
    main()
