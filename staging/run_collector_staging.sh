#!/bin/bash
# Staging Collector Script
# Collects news to staging database WITHOUT affecting production
# Usage: ./run_collector_staging.sh

set -e

STAGING_DIR="/opt/newsbot-staging"

cd "$STAGING_DIR" || { echo "ERROR: Staging directory not found at $STAGING_DIR"; exit 1; }

# Source staging environment (uses local SQLite, not Turso)
set -a
source "$STAGING_DIR/.env"
set +a

# Create staging logs directory if not exists
mkdir -p "$STAGING_DIR/logs"

# Run collector - writes to staging DB (news_queue_staging.db)
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting staging collector..." | tee -a "$STAGING_DIR/logs/collector.log"
"$STAGING_DIR/venv/bin/python" "$STAGING_DIR/collector.py" >> "$STAGING_DIR/logs/collector.log" 2>&1
echo "$(date '+%Y-%m-%d %H:%M:%S') - Staging collector finished" | tee -a "$STAGING_DIR/logs/collector.log"