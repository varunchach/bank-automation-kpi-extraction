#!/usr/bin/env bash
# Print path to Python 3.11.x or exit 1 with install hints.
set -euo pipefail

for candidate in \
  python3.11 \
  /opt/homebrew/bin/python3.11 \
  /usr/local/bin/python3.11 \
  "$HOME/.pyenv/shims/python3.11"
do
  if command -v "$candidate" >/dev/null 2>&1; then
    ver=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
    if [ "$ver" = "3.11" ]; then
      echo "$candidate"
      exit 0
    fi
  fi
done

cat >&2 <<'EOF'
ERROR: Python 3.11 is required (3.12+ and especially 3.14 break Docling OCR).

Install Python 3.11, then re-run setup:

  macOS (Homebrew):   brew install python@3.11
  Ubuntu/Debian:      sudo apt install python3.11 python3.11-venv
  pyenv:              pyenv install 3.11.9 && pyenv local 3.11.9

Verify:  python3.11 --version  →  Python 3.11.x
EOF
exit 1
