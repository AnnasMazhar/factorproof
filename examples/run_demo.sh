#!/usr/bin/env bash
# examples/run_demo.sh — full offline factor-lab pipeline demo
# Usage: bash examples/run_demo.sh
# Requires: uv venv activated or uv run available

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

echo "=== factor-lab v0.1 offline demo ==="
echo ""

echo "--- 1. Factor registry ---"
uv run factor-lab list
echo ""

echo "--- 2. Screen all factors on planted-signal synthetic data ---"
uv run factor-lab screen \
    --data signal \
    --horizons 1,5,20 \
    --out results/
echo ""

echo "--- 3. Promote noise_control (must REJECT, exit 1) ---"
set +e
uv run factor-lab promote noise_control --data signal
NOISE_EXIT=$?
set -e
echo "Exit code: $NOISE_EXIT"
if [ "$NOISE_EXIT" -ne 1 ]; then
    echo "FAIL: noise_control should REJECT (exit 1), got exit $NOISE_EXIT"
    exit 1
fi
echo ""

echo "--- 4. Promote mom_20 on planted-signal data (must PROMOTE, exit 0) ---"
uv run factor-lab promote mom_20 --data signal --plant-signal
MOM_EXIT=$?
echo "Exit code: $MOM_EXIT"
if [ "$MOM_EXIT" -ne 0 ]; then
    echo "FAIL: mom_20 should PROMOTE (exit 0), got exit $MOM_EXIT"
    exit 1
fi
echo ""

echo "--- 5. Explain a factor ---"
uv run factor-lab explain mom_20
echo ""

echo "--- 6. Report from results/ ---"
uv run factor-lab report --from results/ --format md
echo ""

echo "=== Demo complete. Results in results/ ==="
echo "  results/factor_table.md"
echo "  results/ic_decay.png"
echo "  results/quantile_returns.png"
echo "  results/report.html"
