"""
Run Indian Bank KPI extraction from PDF files or URLs.

Usage:
    python run_extraction.py                          # uses data/IB_*.pdf
    python run_extraction.py investor.pdf casa.pdf    # custom paths
    python run_extraction.py --json                   # output as JSON
"""

import argparse
import json
from pathlib import Path

from kpi_extractor import IndianBankKPIExtractor


def main():
    parser = argparse.ArgumentParser(description="Extract KPIs from Indian Bank PDFs")
    parser.add_argument(
        "investor_pdf",
        nargs="?",
        default=None,
        help="Path or URL to IB_investor_PPT.pdf",
    )
    parser.add_argument(
        "casa_pdf",
        nargs="?",
        default=None,
        help="Path or URL to IB_CASA_Numbers_PPT.pdf",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--csv", action="store_true", help="Output as CSV")
    args = parser.parse_args()

    data_dir = Path("data")
    investor = args.investor_pdf or str(data_dir / "IB_investor_PPT.pdf")
    casa = args.casa_pdf or str(data_dir / "IB_CASA_Numbers_PPT.pdf")

    extractor = IndianBankKPIExtractor(investor, casa)
    kpis = extractor.extract()

    if args.csv:
        df = extractor.to_dataframe()
        print(df.to_csv(index=False))
    elif args.json:
        print(extractor.to_json())
    else:
        print("Extracted KPIs:")
        print("-" * 50)
        for k, v in kpis.items():
            if v is not None:
                print(f"  {k}: {v}")
        print("-" * 50)


if __name__ == "__main__":
    main()
