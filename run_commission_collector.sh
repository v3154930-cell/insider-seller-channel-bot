#!/bin/bash
cd "$(dirname "$0")" || exit 1
set -a
source .env
set +a
python commission_collector.py >> commissions.log 2>&1