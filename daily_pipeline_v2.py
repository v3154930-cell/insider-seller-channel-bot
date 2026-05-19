import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path("/opt/newsbot_v2")
PYTHON = str(BASE_DIR / "venv" / "bin" / "python")

STEPS = [
    ("Import uploaded rules documents", "import_rules_docs_bulk_v2.py", False),
    ("Detect marketplace rules signals", "rules_monitor_v2.py", True),
    ("Classify rules signals", "classify_rules_signals_v2.py", True),
    ("Auto-check signals against documents", "rules_auto_check_v2.py", True),
    ("Build rules digest preview", "rules_digest_preview_v2.py", True),
]

def run_step(name, script, required):
    print("=" * 100)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] START: {name}")
    print("-" * 100)

    result = subprocess.run(
        [PYTHON, str(BASE_DIR / script)],
        cwd=str(BASE_DIR),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=1800,
    )

    print(result.stdout)

    if result.returncode == 0:
        print(f"[OK] {name}")
        return True

    print(f"[FAILED] {name} returncode={result.returncode}")
    return not required

def main():
    print("=" * 100)
    print(f"DAILY PIPELINE V2 STARTED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 100)

    ok_all = True

    for name, script, required in STEPS:
        ok = run_step(name, script, required)
        if not ok:
            ok_all = False

    print("=" * 100)
    print(f"DAILY PIPELINE V2 FINISHED: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("STATUS:", "OK" if ok_all else "FAILED")

    sys.exit(0 if ok_all else 1)

if __name__ == "__main__":
    main()
