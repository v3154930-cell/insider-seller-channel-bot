#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi
if [[ -x /opt/newsbot_v2/venv/bin/python ]]; then
  PY=/opt/newsbot_v2/venv/bin/python
else
  PY=python3
fi
exec "$PY" stable_publisher_v3.py "$@"
