#!/bin/bash
#==============================================================================
# STAGING SETUP SCRIPT
# 
# This script creates a staging copy of the newsbot project on the same VPS.
# It copies from the CURRENT WORKING production tree (NOT from git origin/main).
#
# IMPORTANT: Run this script on the VPS as root or with sudo privileges.
#
# What this script does:
# 1. Creates /opt/newsbot-staging directory
# 2. Copies production files (excluding sensitive data)
# 3. Creates separate venv
# 4. Creates staging-specific .env
# 5. Disables MAX posting, cron, Turso DB
# 6. Creates staging-specific database and logs
# 7. Makes scripts executable
#==============================================================================

set -e

echo "=============================================="
echo "  STAGING SETUP FOR NEWSBOT"
echo "=============================================="

# Check if running on VPS (not local)
if [ ! -d "/opt/newsbot" ]; then
    echo "ERROR: /opt/newsbot not found. This script must be run on the VPS."
    exit 1
fi

PROD_DIR="/opt/newsbot"
STAGING_DIR="/opt/newsbot-staging"

echo ""
echo "[1/8] Creating staging directory..."
if [ -d "$STAGING_DIR" ]; then
    echo "WARNING: Staging directory already exists at $STAGING_DIR"
    read -p "Continue and overwrite? (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
    rm -rf "$STAGING_DIR"
fi
mkdir -p "$STAGING_DIR"
mkdir -p "$STAGING_DIR/logs"
mkdir -p "$STAGING_DIR/outputs"
echo "Created: $STAGING_DIR"

echo ""
echo "[2/8] Copying production files (excluding .env, venv, .git, *.db)..."
# Copy only Python files, configs, scripts - exclude sensitive/production-specific files
rsync -a --exclude='.env' --exclude='venv/' --exclude='.git/' --exclude='*.db' --exclude='logs/' --exclude='posted_links.txt' --exclude='__pycache__/' --exclude='*.pyc' "$PROD_DIR/" "$STAGING_DIR/"
echo "Files copied"

echo ""
echo "[3/8] Creating staging virtual environment..."
cd "$STAGING_DIR"
python3 -m venv venv
echo "Virtual environment created at $STAGING_DIR/venv"

echo ""
echo "[4/8] Installing Python dependencies..."
"$STAGING_DIR/venv/bin/pip" install --upgrade pip
"$STAGING_DIR/venv/bin/pip" install -r "$STAGING_DIR/requirements.txt"
echo "Dependencies installed"

echo ""
echo "[5/8] Creating staging .env file..."
cat > "$STAGING_DIR/.env" << 'EOF'
# Staging Environment Configuration
# This file is used for testing without affecting production

# =================== DATABASE ===================
# Staging uses SQLite locally, NOT Turso production DB
#TURSO_DATABASE_URL=
#TURSO_AUTH_TOKEN=

# =================== MAX BOT (DISABLED) ===================
MAX_BOT_TOKEN=staging_dummy_token_do_not_use
MAX_CHANNEL_ID=staging_dummy_channel_do_not_use
CHANNEL_ID=staging_dummy_channel_do_not_use

# =================== LLM CONFIG ===================
GITHUB_TOKEN=

# =================== EXA CONFIG (DISABLED) ===================
ENABLE_EXA=false
EXA_MODE=shadow

# =================== DIGEST CONFIG (DISABLED) ===================
ENABLE_MORNING_DIGEST=false
ENABLE_EVENING_DIGEST=false
ENABLE_AUDIO_DIGEST=false

# =================== STAGING FLAGS ===================
STAGING_MODE=true

# =================== RETENTION ===================
DROP_TTL_HOURS=48
DIGEST_TTL_DAYS=5
SENT_TTL_DAYS=30
PENDING_TTL_DAYS=7
EOF
echo "Created: $STAGING_DIR/.env"

echo ""
echo "[6/8] Creating staging-specific files..."
# Create staging-specific posted_links file
touch "$STAGING_DIR/posted_links_staging.txt"

# The DB will be created automatically on first run (news_queue_staging.db)
echo "Created: $STAGING_DIR/posted_links_staging.txt"
echo "DB will be created on first run: $STAGING_DIR/news_queue_staging.db"

echo ""
echo "[7/8] Copying staging scripts from local..."
# The staging scripts are already in the staging/ folder from local
# Just make them executable
chmod +x "$STAGING_DIR/run_collector_staging.sh" 2>/dev/null || true
chmod +x "$STAGING_DIR/run_regular_preview_staging.sh" 2>/dev/null || true
chmod +x "$STAGING_DIR/run_digest_preview_staging.sh" 2>/dev/null || true
echo "Scripts made executable"

echo ""
echo "[8/8] Verification..."
echo ""
echo "=== STAGING DIRECTORY STRUCTURE ==="
ls -la "$STAGING_DIR/"
echo ""
echo "=== STAGING VENV ==="
ls "$STAGING_DIR/venv/bin/python" 2>/dev/null && echo "Python: OK" || echo "Python: MISSING"
echo ""
echo "=== STAGING .ENV (first 10 lines) ==="
head -10 "$STAGING_DIR/.env"
echo ""
echo "=== STAGING LOGS DIR ==="
ls -la "$STAGING_DIR/logs/"

echo ""
echo "=============================================="
echo "  STAGING SETUP COMPLETE!"
echo "=============================================="
echo ""
echo "Staging location: $STAGING_DIR"
echo ""
echo "To run staging collector:"
echo "  cd $STAGING_DIR"
echo "  source .env"
echo "  ./run_collector_staging.sh"
echo ""
echo "To run staging preview:"
echo "  cd $STAGING_DIR"
echo "  source .env"
echo "  ./run_regular_preview_staging.sh"
echo ""
echo "Preview output will be saved to:"
echo "  $STAGING_DIR/outputs/"
echo ""
echo "IMPORTANT: Production is at /opt/newsbot - DO NOT modify!"
echo "=============================================="