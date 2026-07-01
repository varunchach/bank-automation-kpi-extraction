"""
OpenShift entrypoint: same app as streamlit_app.py but uses fast Docling (tables only, no OCR)
to avoid long runs and connection timeouts. Local app is unchanged.
"""
import logging
import sys
from pathlib import Path

# Ensure same path setup as main app
ROOT = Path(__file__).resolve().parent.parent
COMBINED = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(COMBINED))
sys.path.insert(0, str(ROOT / "IB"))
sys.path.insert(0, str(ROOT / "PNB"))

# Log accelerator at startup (for GPU testing: check pod logs for "CUDA available")
try:
    import torch
    if torch.cuda.is_available():
        logging.basicConfig(level=logging.INFO)
        logging.getLogger().info("CUDA available: %s", torch.cuda.get_device_name(0))
    else:
        logging.basicConfig(level=logging.INFO)
        logging.getLogger().info("CUDA not available (CPU mode)")
except Exception as e:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger().info("Accelerator check failed: %s", e)

import streamlit_app
from docling_fast import convert_pdf_once_fast

# Use fast Docling (no full-page OCR) so report finishes within route timeout
streamlit_app.convert_pdf_once = convert_pdf_once_fast

if __name__ == "__main__":
    streamlit_app.main()
