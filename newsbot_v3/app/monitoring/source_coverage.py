from __future__ import annotations


def source_coverage(v2_inventory: dict, v3_loaded: dict) -> dict:
    rss_ok = int(v3_loaded.get("rss_sources_loaded", 0)) >= int(v2_inventory.get("rss_sources", 0))
    tg_ok = int(v3_loaded.get("telegram_json_sources_loaded", 0)) >= int(v2_inventory.get("telegram_json_sources", 0))
    off_ok = int(v3_loaded.get("official_json_sources_loaded", 0)) >= int(v2_inventory.get("official_json_sources", 0))
    official_yandex_gap = "WARN"
    status = "OK" if all([rss_ok, tg_ok, off_ok]) else "WARN"
    if official_yandex_gap == "WARN":
        status = "WARN"
    return {
        "status": status,
        "rss_count": f"{v3_loaded.get('rss_sources_loaded',0)}/{v2_inventory.get('rss_sources',0)}",
        "telegram_json_count": f"{v3_loaded.get('telegram_json_sources_loaded',0)}/{v2_inventory.get('telegram_json_sources',0)}",
        "official_json_count": f"{v3_loaded.get('official_json_sources_loaded',0)}/{v2_inventory.get('official_json_sources',0)}",
        "official_wb_status": v2_inventory.get("official_wb", "UNKNOWN"),
        "official_ozon_status": v2_inventory.get("official_ozon", "UNKNOWN"),
        "official_yandex_status": "WARN",
        "official_yandex_gap": "official_yandex source gap remains WARN until resolved",
    }
