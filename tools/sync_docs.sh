#!/usr/bin/env bash
# Sync Python package sources into docs/ for the Pyodide web UI.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p docs/py/editorial_collector
cp editorial_collector/*.py docs/py/editorial_collector/
echo "synced $(ls docs/py/editorial_collector | wc -l | tr -d ' ') modules -> docs/py/editorial_collector/"
