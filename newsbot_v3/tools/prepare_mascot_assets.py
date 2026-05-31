import argparse
import csv
import json
import shutil
import zipfile
from pathlib import Path

REQUIRED = {
    "base": "01_Friendly_Approved_Style_Base.png",
    "good_news": "02_Happy_Good_News.png",
    "important": "03_Alert_Urgent_Important.png",
    "analytics": "04_Thoughtful_Analytics.png",
    "law_taxes": "05_Serious_Law_Taxes.png",
    "compliance": "06_Confident_Marking_Compliance.png",
    "money_profit": "07_Optimistic_Money_Profit.png",
    "morning_digest": "08_Fresh_Morning_Digest.png",
    "evening_digest": "09_Calm_Evening_Digest.png",
    "interesting": "10_Curious_Interesting_News.png",
    "audio_digest": "11_Energetic_Audio_Digest.png",
}

META = {
    "base": ("fallback/default news mascot", "Базовый маскот", "Base mascot"),
    "good_news": ("positive marketplace news", "Хорошие новости", "Good news"),
    "important": ("urgent/important seller updates", "Важные обновления", "Important"),
    "analytics": ("analytics/statistics/market observations", "Аналитика", "Analytics"),
    "law_taxes": ("law, taxes, court, regulation", "Закон и налоги", "Law and taxes"),
    "compliance": ("marking, certification, compliance, rules", "Комплаенс и маркировка", "Compliance"),
    "money_profit": ("money, payouts, profit, economics", "Деньги и прибыль", "Money and profit"),
    "morning_digest": ("morning digest", "Утренний дайджест", "Morning digest"),
    "evening_digest": ("evening/final digest", "Вечерний дайджест", "Evening digest"),
    "interesting": ("interesting/light news", "Интересные новости", "Interesting"),
    "audio_digest": ("audio digest", "Аудиодайджест", "Audio digest"),
}


def resize_to_width(src: Path, dst: Path, max_width: int):
    try:
        from PIL import Image
    except Exception as exc:
        raise RuntimeError("Pillow is required to prepare mascot assets") from exc
    with Image.open(src) as img:
        if img.width <= max_width:
            out = img.copy()
        else:
            ratio = max_width / float(img.width)
            out = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        out.save(dst, format="PNG")


def select_mascot_asset(kind, manifest):
    k = (kind or "").lower()
    mapping_checks = [
        ("morning", "morning_digest"),
        ("final", "evening_digest"),
        ("evening", "evening_digest"),
        ("audio", "audio_digest"),
        ("urgent", "important"),
        ("important", "important"),
        ("interesting", "interesting"),
        ("profit", "money_profit"),
        ("money", "money_profit"),
        ("payout", "money_profit"),
        ("law", "law_taxes"),
        ("tax", "law_taxes"),
        ("court", "law_taxes"),
        ("marking", "compliance"),
        ("compliance", "compliance"),
        ("rules", "compliance"),
        ("analytics", "analytics"),
        ("stat", "analytics"),
    ]
    target = "base"
    for token, key in mapping_checks:
        if token in k:
            target = key
            break
    return manifest.get(target) or manifest.get("base")


def prepare(zip_path: Path, out_dir: Path):
    if not zip_path.exists():
        raise FileNotFoundError(f"ZIP not found: {zip_path}")

    source = out_dir / "source"
    web = out_dir / "web"
    mobile = out_dir / "mobile"
    source.mkdir(parents=True, exist_ok=True)
    web.mkdir(parents=True, exist_ok=True)
    mobile.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as zf:
        names = set(zf.namelist())
        missing = [f for f in REQUIRED.values() if f not in names]
        if missing:
            raise RuntimeError(f"ZIP missing required files: {missing}")

        for name in REQUIRED.values():
            with zf.open(name) as src, open(source / name, "wb") as dst:
                shutil.copyfileobj(src, dst)

        for extra in ("README.txt", "manifest.csv"):
            if extra in names:
                with zf.open(extra) as src, open(source / extra, "wb") as dst:
                    shutil.copyfileobj(src, dst)

    manifest = {}
    for key, filename in REQUIRED.items():
        src_path = source / filename
        web_path = web / filename
        mobile_path = mobile / filename
        resize_to_width(src_path, web_path, 1280)
        resize_to_width(src_path, mobile_path, 720)
        intended_use, title_ru, title_en = META[key]
        manifest[key] = {
            "key": key,
            "source_filename": filename,
            "source_path": str(src_path.relative_to(out_dir)),
            "web_path": str(web_path.relative_to(out_dir)),
            "mobile_path": str(mobile_path.relative_to(out_dir)),
            "intended_use": intended_use,
            "title_ru": title_ru,
            "title_en": title_en,
        }

    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", required=True, dest="zip_path")
    parser.add_argument("--out", required=True, dest="out_dir")
    args = parser.parse_args()
    prepare(Path(args.zip_path), Path(args.out_dir))


if __name__ == "__main__":
    main()
