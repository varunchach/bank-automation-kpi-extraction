.PHONY: help setup verify download smoke run clean-venv

help:
	@echo "Bank KPI Extraction — common commands"
	@echo ""
	@echo "  make setup     Create .venv (Python 3.11), install deps, download PDFs"
	@echo "  make verify    Check Python, packages, and data/ PDFs"
	@echo "  make download  Re-download IB + PNB PDFs only"
	@echo "  make smoke     Quick IB extraction test (~2–5 min)"
	@echo "  make run       Start Streamlit → http://localhost:8501"
	@echo "  make clean-venv Remove .venv (use if wrong Python was used)"
	@echo ""
	@echo "First time:  make setup && make verify && make run"

setup:
	chmod +x scripts/*.sh run_local.sh
	./scripts/setup.sh

verify:
	./scripts/verify_setup.sh

download:
	./scripts/download_pdfs.sh

smoke:
	./scripts/smoke_test.sh

run:
	./run_local.sh

clean-venv:
	rm -rf .venv
	@echo "Removed .venv — run: make setup"
