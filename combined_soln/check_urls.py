#!/usr/bin/env python3
"""Test URL accessibility and optionally download PDFs. Use for debugging 403/download issues."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/pdf,*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com",
}


def check(url: str) -> tuple[int, str, int]:
    """Check URL accessibility. Returns (status_code, reason, content_length)."""
    try:
        r = requests.head(url, headers=HEADERS, timeout=15, allow_redirects=True)
        length = int(r.headers.get("content-length", 0) or 0)
        if r.status_code == 405:
            # Some servers disallow HEAD; try GET with Range for first byte
            r2 = requests.get(
                url, headers={**HEADERS, "Range": "bytes=0-0"},
                timeout=15, allow_redirects=True, stream=True
            )
            length = int(r2.headers.get("content-length", 0) or 0)
            return r2.status_code, r2.reason or "", length
        return r.status_code, r.reason or "", length
    except Exception as e:
        return -1, str(e), 0


def download(url: str, dest: Path) -> tuple[bool, str]:
    """Download URL to dest. Returns (success, message)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=120, stream=True)
        if r.status_code == 403:
            return False, "403 Forbidden — server blocks request"
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return True, f"Saved ({dest.stat().st_size // 1024} KB)"
    except requests.exceptions.HTTPError as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def main():
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print("Usage: python check_urls.py [--download] <url1> [url2 ...]")
        print("       python check_urls.py --sample   # test with known public PDFs")
        print("  --download  Save PDFs to combined_soln/downloads/")
        print("  --sample    Run with sample URLs (arxiv, etc.)")
        sys.exit(0)

    do_download = "--download" in args
    if do_download:
        args.remove("--download")

    use_sample = "--sample" in args
    if use_sample:
        args.remove("--sample")
        # Read URLs from urls_to_test.txt (BSE corp filing PDFs)
        urls_file = Path(__file__).resolve().parent / "urls_to_test.txt"
        if urls_file.exists():
            args = [u.strip() for u in urls_file.read_text().splitlines() if u.strip() and not u.startswith("#")]
        else:
            args = []

    if not args:
        urls_file = Path(__file__).resolve().parent / "urls_to_test.txt"
        if urls_file.exists():
            args = [u.strip() for u in urls_file.read_text().splitlines() if u.strip() and not u.startswith("#")]
        if not args:
            print("No URLs. Either:")
            print("  1. Edit combined_soln/urls_to_test.txt with your URLs, then: python check_urls.py --sample")
            print("  2. Or pass URLs: python check_urls.py https://your-url.pdf [--download]")
            sys.exit(1)

    downloads_dir = Path(__file__).resolve().parent / "downloads"
    downloads_dir.mkdir(exist_ok=True)

    ok, fail = 0, 0
    for i, url in enumerate(args):
        url = url.strip()
        if not url.startswith(("http://", "https://")):
            print(f"[{i+1}] Invalid: {url}")
            fail += 1
            continue

        code, reason, length = check(url)
        size_str = f"~{length // 1024} KB" if length else "unknown size"
        short = url[:70] + "..." if len(url) > 70 else url
        print(f"\n[{i+1}] {short}")
        print(f"     Status: {code} {reason} | Size: {size_str}")

        if code == 200:
            ok += 1
            if do_download:
                dest = downloads_dir / f"downloaded_{i+1}.pdf"
                success, msg = download(url, dest)
                if success:
                    print(f"     Download: OK — {msg}")
                else:
                    print(f"     Download: FAILED — {msg}")
                    fail += 1
            else:
                print(f"     Downloadable: YES")
        elif code == 403:
            print(f"     Downloadable: NO (403 Forbidden)")
            fail += 1
        elif code == 404:
            print(f"     Downloadable: NO (404 Not Found)")
            fail += 1
        else:
            print(f"     Downloadable: NO (unexpected status)")
            fail += 1

    print(f"\n--- Result: {ok} accessible, {fail} failed ---")


if __name__ == "__main__":
    main()
