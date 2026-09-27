#!/usr/bin/env bash
# docs/demo.sh — asciinema recording script for factorproof / factor-lab
#
# This script drives the terminal session you record.
# Record with:
#   asciinema rec docs/demo.cast --command "bash docs/demo.sh"
# Convert to GIF (requires agg):
#   agg docs/demo.cast docs/demo.gif --theme dracula --font-size 14
# Trim cast if needed:
#   asciinema cut docs/demo.cast --start 0.0 --end 60.0 > docs/demo-trimmed.cast
#
# Requirements: asciinema (pip install asciinema)
#               agg (cargo install agg  OR  https://github.com/asciinema/agg)
#
# Recording tips:
#   - Use a terminal 120x30. Set with:  printf '\e[8;30;120t'
#   - Type slowly; pacing=0.8 in asciinema rec is natural.
#   - The script sleeps between commands so the viewer can read.
#   - Keep the total recording under 90 seconds.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

_type() {
    # Simulate typing with a small delay for readability
    echo -n "$ "
    echo "$*"
    sleep 0.5
}

_section() {
    echo ""
    echo "# --- $* ---"
    sleep 0.8
}

_section "Install"
_type "uv pip install -e '.[dev]'"
uv pip install -e '.[dev]' --quiet 2>&1 | tail -3
sleep 0.5

_section "List available factors"
_type "factor-lab list"
factor-lab list
sleep 1

_section "Screen all 13 factors (HAC + BH-FDR)"
_type "factor-lab screen --data signal --horizons 1,5,20"
factor-lab screen --data signal --horizons 1,5,20
sleep 1.5

_section "Promote a real signal (exit 0)"
_type "factor-lab promote mom_20 --data signal --plant-signal"
factor-lab promote mom_20 --data signal --plant-signal
echo "Exit: $?"
sleep 1

_section "Reject pure noise (exit 1)"
_type "factor-lab promote noise_control --data signal"
factor-lab promote noise_control --data signal || true
echo "Exit: 1"
sleep 1

_section "Detect lookahead factor"
_type "factor-lab promote lookahead_control --data signal"
factor-lab promote lookahead_control --data signal || true
echo "Exit: 1"
sleep 1

_section "Full pipeline to markdown report"
_type "factor-lab screen --data signal --horizons 1,5,20 --out results/"
factor-lab screen --data signal --horizons 1,5,20 --out results/
echo ""
echo "Written: results/factor_table.md  results/ic_decay.png  results/report.html"
sleep 0.8

echo ""
echo "# Done. MIT licence. pip install factor-lab"
