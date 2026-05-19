from pathlib import Path
import shutil

BASE = Path("/opt/newsbot_v2/rules_docs/inbox")

def move(path, marketplace):
    target_dir = BASE / marketplace
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / path.name

    if path.parent == target_dir:
        return "KEEP"

    if target.exists():
        stem = target.stem
        suffix = target.suffix
        i = 2
        while target.exists():
            target = target_dir / f"{stem}_copy{i}{suffix}"
            i += 1

    shutil.move(str(path), str(target))
    return f"MOVE -> {target}"

def detect(name):
    n = name.lower()

    ozon_words = [
        "ozon", "озон",
        "commission", "comission", "сomission",
        "marketplace-services-rates",
        "return tariffs",
        "оферта товарная",
        "полный список комиссий",
        "комиссии и тарифов",
    ]

    wb_words = [
        "wildberries", "wb", "вайлдберриз",
    ]

    yandex_words = [
        "yandex", "яндекс", "yandex_market", "market.yandex",
    ]

    if any(w in n for w in ozon_words):
        return "ozon"

    if any(w in n for w in wb_words):
        return "wildberries"

    if any(w in n for w in yandex_words):
        return "yandex_market"

    return "unknown"

moved = 0

for path in list(BASE.rglob("*")):
    if not path.is_file():
        continue

    marketplace = detect(path.name)
    result = move(path, marketplace)

    if result != "KEEP":
        moved += 1

    print(path.name, "=>", marketplace, result)

print()
print("moved:", moved)

print("\n=== FILES BY FOLDER ===")
for marketplace in ["ozon", "wildberries", "yandex_market", "unknown"]:
    folder = BASE / marketplace
    files = [p for p in folder.glob("*") if p.is_file()]
    print(marketplace, len(files))
    for p in files:
        print(" -", p.name)
