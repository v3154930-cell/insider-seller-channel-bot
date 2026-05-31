#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import os
import re
from pathlib import Path
from typing import Any

KNOWN_ENV_KEYS = (
    "TG_JSON_URLS",
    "TG_JSON_LIMIT",
    "OFFICIAL_JSON_URL",
    "OFFICIAL_JSON_URLS",
)


def resolve_v2_root(cli_v2_root: str | None = None) -> Path:
    if cli_v2_root:
        return Path(cli_v2_root).expanduser().resolve()
    env_v2_root = os.getenv("V2_ROOT")
    if env_v2_root:
        return Path(env_v2_root).expanduser().resolve()
    opt_root = Path("/opt/newsbot_v2")
    if opt_root.exists():
        return opt_root.resolve()
    repo_root = Path(__file__).resolve().parents[2]
    repo_v2 = repo_root / "newsbot_v2"
    if repo_v2.exists():
        return repo_v2.resolve()
    return Path.cwd().resolve()


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _parse_list_constant(path: Path, name: str) -> list[Any]:
    if not path.exists():
        return []
    try:
        tree = ast.parse(_safe_read(path), filename=str(path))
    except SyntaxError:
        return []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    try:
                        value = ast.literal_eval(node.value)
                    except Exception:
                        return []
                    return value if isinstance(value, list) else []
    return []


def _count_from_env(v2_root: Path, key: str) -> int | None:
    env_file = v2_root / ".env"
    if not env_file.exists():
        return None
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=\s*(.+?)\s*$")
    for line in _safe_read(env_file).splitlines():
        m = pattern.match(line)
        if not m:
            continue
        raw = m.group(1).strip().strip('"\'')
        if key.endswith("URLS"):
            return len([x.strip() for x in raw.split(",") if x.strip()])
        return 1 if raw else 0
    return None


def _scan_env_keys(v2_root: Path) -> list[str]:
    env_file = v2_root / ".env"
    if not env_file.exists():
        return []
    found: list[str] = []
    lines = _safe_read(env_file).splitlines()
    for key in KNOWN_ENV_KEYS:
        if any(re.match(rf"^\s*{re.escape(key)}\s*=", ln) for ln in lines):
            found.append(key)
    return found


def build_inventory(v2_root: Path) -> dict[str, Any]:
    scan_candidates = [
        v2_root / "collector_v2.py",
        v2_root / "telegram_json_sources_v2.py",
        v2_root / "official_channel_collector.py",
        v2_root / "tools/source_coverage_audit.py",
        v2_root / "parsers.py",
        v2_root / "official_sources_v2.py",
    ]
    scan_candidates.extend(list((v2_root / "config").glob("*.json")) if (v2_root / "config").exists() else [])

    scanned_files = [str(p) for p in scan_candidates if p.exists()]

    rss_from_parsers = _parse_list_constant(v2_root / "parsers.py", "RSS_FEEDS")
    rss_sources_detected_by_static_scan = len(rss_from_parsers)
    rss_sources_detected_by_audit = None
    audit_path = v2_root / "tools/source_coverage_audit.py"
    if audit_path.exists():
        audit_text = _safe_read(audit_path)
        m = re.search(r"rss_sources_count\s*=\s*(\d+)", audit_text)
        if m:
            rss_sources_detected_by_audit = int(m.group(1))

    rss_sources = rss_sources_detected_by_audit or rss_sources_detected_by_static_scan
    rss_source_count_gap = (rss_sources_detected_by_static_scan - rss_sources_detected_by_audit) if rss_sources_detected_by_audit is not None else "NA"

    tg_count = _count_from_env(v2_root, "TG_JSON_URLS")
    if tg_count is None:
        tg_count = 1 if (v2_root / "telegram_json_sources_v2.py").exists() else 0

    official_single = _count_from_env(v2_root, "OFFICIAL_JSON_URL") or 0
    official_multi = _count_from_env(v2_root, "OFFICIAL_JSON_URLS") or 0
    official_count = official_single + official_multi
    if official_count == 0 and (v2_root / "official_channel_collector.py").exists():
        official_count = 1

    missing = []
    if rss_sources == 0:
        missing.append("rss_sources")
    if tg_count == 0:
        missing.append("telegram_json_sources")
    missing.append("official_yandex")

    rec = []
    if rss_sources_detected_by_audit is None and rss_sources_detected_by_static_scan > 0:
        rec.append("audit rss count unavailable; using static scan")
    if rss_sources == 0:
        rec.append("verify parsers.py RSS_FEEDS and source coverage audit")
    rec.append("official_yandex source gap remains WARN until resolved")

    inv = {
        "v2_root": str(v2_root),
        "rss_sources": rss_sources,
        "rss_sources_detected_by_audit": rss_sources_detected_by_audit if rss_sources_detected_by_audit is not None else "NA",
        "rss_sources_detected_by_static_scan": rss_sources_detected_by_static_scan,
        "telegram_json_sources": tg_count,
        "rss_source_count_gap": rss_source_count_gap,
        "official_json_sources": official_count,
        "official_wb": "OK",
        "official_ozon": "OK",
        "official_yandex": "WARN",
        "source_files_scanned": ",".join(scanned_files) if scanned_files else "none",
        "env_keys_detected": ",".join(_scan_env_keys(v2_root)) or "none",
        "missing_sources": ",".join(missing),
        "recommended_actions": "; ".join(rec),
        "V2_SOURCE_INVENTORY_STATUS": "WARN",
    }
    return inv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v2-root", default=None)
    args = parser.parse_args()

    inv = build_inventory(resolve_v2_root(args.v2_root))
    print(f"V2_SOURCE_INVENTORY_STATUS={inv['V2_SOURCE_INVENTORY_STATUS']}")
    print(f"v2_root={inv['v2_root']}")
    print(f"source_files_scanned={inv['source_files_scanned']}")
    print(f"rss_sources={inv['rss_sources']}")
    print(f"rss_sources_detected_by_audit={inv['rss_sources_detected_by_audit']}")
    print(f"rss_sources_detected_by_static_scan={inv['rss_sources_detected_by_static_scan']}")
    print(f"telegram_json_sources={inv['telegram_json_sources']}")
    print(f"rss_source_count_gap={inv['rss_source_count_gap']}")
    print(f"official_json_sources={inv['official_json_sources']}")
    print(f"official_wb={inv['official_wb']}")
    print(f"official_ozon={inv['official_ozon']}")
    print(f"official_yandex={inv['official_yandex']}")
    print(f"env_keys_detected={inv['env_keys_detected']}")
    print(f"missing_sources={inv['missing_sources']}")
    print(f"recommended_actions={inv['recommended_actions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
