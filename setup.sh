#!/usr/bin/env sh
# Run full setup from project root. Use: ./setup.sh  or  sh setup.sh
# Vision requires Python 3.10. Prefer python3.10 if present.
set -e
cd "$(dirname "$0")"
if command -v python3.10 >/dev/null 2>&1; then
  python3.10 scripts/setup.py
else
  python3 scripts/setup.py
fi
echo ""
echo "Activate the venv and run the agent:"
echo "  source .venv/bin/activate"
echo "  python main.py"
