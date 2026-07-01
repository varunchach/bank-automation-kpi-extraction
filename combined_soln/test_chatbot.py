#!/usr/bin/env python3
"""Dummy script to test the chatbot path (answer_question) without running full Streamlit/Docling.
Shows the exact context (kpis + retrieved_chunks) sent to the LLM so you can verify we use extracted content.
Run from repo root: python combined_soln/test_chatbot.py
"""
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "IB"))
sys.path.insert(0, str(ROOT / "PNB"))
sys.path.insert(0, str(ROOT / "combined_soln"))

# Set True to force rule-based only (no LLM) so answers clearly come from context
SHOW_CONTEXT = True
OFFLINE_ONLY = False


def main():
    import pandas as pd
    from rag_milvus import search_chunks, get_fallback_chunks, build_entities_json
    from streamlit_app import answer_question

    # Dummy extracted content (what would come from Docling + KPI extraction)
    pdf_text = (
        "Indian Bank reported Net Profit of Rs 2500 crore. Gross NPA was 3.2%. "
        "PNB advances grew 12% YoY. CASA ratio improved to 42%. Capital adequacy CAR at 16%."
    )
    kpi_table = (
        "KPI\tIndian Bank\tPNB\n"
        "Net_Profit\t2500\t3200\n"
        "Gross_NPA_Pct\t3.2\t4.1\n"
        "CASA_Pct_Domestic\t42.5\t40.2\n"
    )
    kpi_df = pd.DataFrame([
        {"KPI": "Net_Profit", "Indian Bank": 2500, "PNB": 3200},
        {"KPI": "Gross_NPA_Pct", "Indian Bank": 3.2, "PNB": 4.1},
    ])

    question = "What did the document say about CASA and capital adequacy?"
    print("=== Chatbot test: context is built from extracted data ===\n")

    # Build context exactly as answer_question does (so you see we use chunks, not "LLM only")
    retrieved = search_chunks(question)
    if not retrieved and pdf_text:
        retrieved = get_fallback_chunks(pdf_text, max_chunks=5)
    entities_json = build_entities_json(kpi_df, retrieved)

    if SHOW_CONTEXT:
        print("Context sent to LLM (kpis + retrieved_chunks from extracted PDF text):")
        print(json.dumps(entities_json, indent=2, default=str))
        print("\n---\n")

    try:
        ans = answer_question(
            pdf_text,
            kpi_table,
            question,
            kpi_df=kpi_df,
            entities_json=entities_json,  # use the context we just built (no double-call)
            llm_base_url="",
            llm_api_key="",
            use_web_search=not OFFLINE_ONLY,
            use_yahoo_finance=not OFFLINE_ONLY,
            use_agentic=False,
        )
        print(f"Q: {question}\nA: {ans}\n")
    except Exception as e:
        print(f"ERROR: {e}\n")
        raise

    print("=== Done: answer is based on the context above (kpis + retrieved_chunks) ===")


if __name__ == "__main__":
    main()
