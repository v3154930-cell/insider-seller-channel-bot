#!/bin/bash
# Run EXA shadow/preview pipeline
# This script runs only the shadow/merge logic without touching regular pipeline

echo "=========================================="
echo "EXA Shadow Pipeline"
echo "=========================================="

# Check for virtual environment
if [ -d "venv" ]; then
    source venv/Scripts/activate
    echo "Using virtual environment"
elif [ -d ".venv" ]; then
    source .venv/Scripts/activate
    echo "Using .venv virtual environment"
fi

# Set default EXA config if not already set
export ENABLE_EXA="${ENABLE_EXA:-false}"
export EXA_MODE="${EXA_MODE:-shadow}"
export EXA_MAX_ITEMS_PER_QUERY="${EXA_MAX_ITEMS_PER_QUERY:-5}"
export EXA_MAX_TOTAL_ITEMS="${EXA_MAX_TOTAL_ITEMS:-30}"

echo "Config:"
echo "  ENABLE_EXA: $ENABLE_EXA"
echo "  EXA_MODE: $EXA_MODE"
echo "  EXA_MAX_ITEMS_PER_QUERY: $EXA_MAX_ITEMS_PER_QUERY"
echo "  EXA_MAX_TOTAL_ITEMS: $EXA_MAX_TOTAL_ITEMS"
echo ""

# Run the shadow preview
python preview_shadow_merge.py

echo ""
echo "=========================================="
echo "Shadow pipeline complete"
echo "No DB writes, no MAX API calls"
echo "=========================================="
