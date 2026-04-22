#!/bin/bash
# Staging Digest Preview Script
# Preview digest publishing WITHOUT posting to MAX
# Usage: ./run_digest_preview_staging.sh

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

# Run digest preview - saves to staging output, does NOT post to MAX
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting staging digest preview..." | tee -a "$STAGING_DIR/logs/preview_digest.log"
"$STAGING_DIR/venv/bin/python" "$STAGING_DIR/preview_digest_staging.py" >> "$STAGING_DIR/logs/preview_digest.log" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') - Staging digest preview finished" | tee -a "$STAGING_DIR/logs/preview_digest.log"

echo ""
echo "=== STAGING DIGEST OUTPUT ==="
echo "Preview files saved to: $STAGING_DIR/outputs/"
ls -la "$STAGING_DIR/outputs/" 2>/dev/null || echo "No output files yet"
echo "======================"