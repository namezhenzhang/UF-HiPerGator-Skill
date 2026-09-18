#!/usr/bin/env bash
# Run on a HiPerGator login node. Requires Python 3 and Slurm client commands.
set -euo pipefail
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/monitor.py" "$@"
