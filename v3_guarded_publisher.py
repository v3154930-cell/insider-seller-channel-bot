#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path("/opt/newsbot_v2")
DB = ROOT / "news_queue.db"
PY = ROOT / "venv/bin/python"
CANARY = ROOT / "newsbot_v3/tools/v3_controlled_send_canary.py"
LOG = ROOT / "logs/v3_guarded_publisher.log"

FAILED_DECISIONS = {
    "gate_failed",
    "send_failed",
    "duplicate_failed",
    "invalid_post_failed",
    "native_ad_failed",
}

NO_ACTION_PATTERNS = [
    "прямых действий пока нет",
    "прямого действия пока нет",
    "можно просто наблюдать",
    "это скорее фон",
    "фоновый контекст",
]

BACKGROUND_PATTERNS = [
    "нарушений с маркировкой",
    "количество нарушений",
    "нарушений при продаже марлированных товаров",
    "сократилось примерно в два раза",
    "стало меньше црпт",
    "говорит