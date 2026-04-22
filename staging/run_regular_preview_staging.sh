#!/bin/bash
# Staging Regular Preview Script
# Preview regular publishing WITHOUT posting to MAX
# Saves final payload to /opt/newsbot-staging/outputs/preview_*.txt
# Usage: ./run_regular_preview_staging.sh

set -e

STAGING_DIR="/opt/newsbot-staging"

cd "$STAGING_DIR" || { echo "ERROR: Staging directory not found at $STAGING_DIR"; exit 1; }

# Source staging environment
set -a
source "$STAGING_DIR/.env"
set +a

# Create staging logs and outputs directories if not exists
mkdir -p "$STAGING_DIR/logs"
mkdir -p "$STAGING_DIR/outputs"

# Run preview - saves to staging output, does NOT post to MAX
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting staging regular preview..." | tee -a "$STAGING_DIR/logs/preview.log"
"$STAGING_DIR/venv/bin/python" "$STAGING_DIR/preview_staging.py" >> "$STAGING_DIR/logs/preview.log" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') - Staging preview finished" | tee -a "$STAGING_DIR/logs/preview.log"

echo ""
echo "=== STAGING OUTPUT ==="
echo "Preview files saved to: $STAGING_DIR/outputs/"
ls -la "$STAGING_DIR/outputs/" 2>/dev/null || echo "No output files yet"
echo "======================"