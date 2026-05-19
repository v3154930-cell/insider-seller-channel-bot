import hashlib
import shutil
from pathlib import Path
from datetime import datetime

BASE = Path("/opt/newsbot_v2/rules_docs/inbox")
ARCHIVE = Path("/opt/newsbot_v2/rules_docs/archive/duplicates")
ARCHIVE.mkdir(parents=True, exist_ok=True)

def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

seen = {}
moved = 0
kept = 0

for path in sorted(BASE.rglob("*")):
    if not path.is_file():
        continue

    try:
        digest = sha256_file(path)
    except Exception as e:
        print("SKIP unreadable:", path, e)
        continue

    if digest in seen:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = ARCHIVE / f"{stamp}_{path.name}"
        shutil.move(str(path), str(target))
        print("DUPLICATE MOVED:", path, "=>", target)
        moved += 1
    else:
        seen[digest] = path
        kept += 1

print()
print("cleanup finished")
print("kept:", kept)
print("duplicates moved:", moved)
print("archive:", ARCHIVE)
