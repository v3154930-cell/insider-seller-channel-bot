#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sqlite3
from pathlib import Path
from datetime import datetime

NEWS_DB = Path("/opt/newsbot_v2/news_queue.db")
TARIFF_DB = Path("/opt/newsbot_v2/data/unified_tariffs.db")
OZON_INBOX = Path("/opt/newsbot_v2/rules_docs/inbox/ozon")
RULES_INBOX = Path("/opt/newsbot_v2/rules_docs/inbox")

NOW = datetime.now()

RECOMMENDED_OZON_PACKAGE = [
    {
        "title": "1. Комиссии / вознаграждение по схемам продаж",
        "why": "главный боевой файл для расчёта комиссий Ozon в Seller Helper",
        "keywords": ["marketplace-services-rates", "marketplace services rates"],
        "critical": True,
    },
    {
        "title": "2. Полный список комиссий и тарифов",
        "why": "логистика, возвраты, размещение, штрафы, услуги, дополнительные удержания",
        "keywords": ["полный список комиссий", "комиссий и тарифов", "tariffs"],
        "critical": True,
    },
    {
        "title": "3. Тарифы возвратов",
        "why": "возвраты, обратная логистика, вывозы, утилизация, обработка возвратов",
        "keywords": ["return tariffs", "возврат"],
        "critical": True,
    },
    {
        "title": "4. Логистика FBO/FBS/realFBS",
        "why": "логистика может сильно менять фактическую маржу, даже если комиссия не изменилась",
        "keywords": ["logistika", "логистика", "fbo", "fbs"],
        "critical": True,
    },
    {
        "title": "5. Размещение / хранение / временное размещение",
        "why": "хранение и размещение влияют на остаток после удержаний",
        "keywords": ["размещение", "хранение", "storage", "placement"],
        "critical": False,
    },
    {
        "title": "6. Оферта / условия работы продавца",
        "why": "юридический слой: штрафы, блокировки, возвраты, обязанности продавца",
        "keywords": ["оферта", "offer"],
        "critical": False,
    },
]


def h(value):
    if value is None or value == "":
        return "не указано"
    return str(value)


def connect(path: Path):
    if not path.exists():
        return None
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    return con


def table_exists(cur, table):
    row = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def parse_dt(value):
    if not value:
        return None

    s = str(value).strip()
    s = s.replace("Z", "+00:00")

    # SQLite CURRENT_TIMESTAMP
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s[:19], fmt)
        except Exception:
            pass

    # ISO with T / timezone
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        return None


def age_days(dt):
    if not dt:
        return None
    return max(0, int((NOW - dt).total_seconds() // 86400))


def fmt_dt(dt):
    if not dt:
        return "не определено"
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def find_disk_file(file_name):
    if not file_name:
        return None

    exact = OZON_INBOX / file_name
    if exact.exists():
        return exact

    for root in (OZON_INBOX, RULES_INBOX):
        if not root.exists():
            continue
        try:
            matches = list(root.rglob(file_name))
            if matches:
                return matches[0]
        except Exception:
            pass

    return None


def get_tariff_source():
    data = {
        "error": None,
        "source_file": None,
        "source_status": None,
        "source_role": None,
        "source_note": None,
        "comment": None,
        "created_at": None,
        "valid_from_min": None,
        "valid_from_max": None,
        "standard_rows": 0,
        "select_rows": 0,
        "select_usable_rows": 0,
        "source_dt": None,
        "source_age_days": None,
        "disk_path": None,
        "disk_mtime": None,
        "imported_at": None,
        "import_rows": None,
    }

    con = connect(TARIFF_DB)
    if not con:
        data["error"] = f"не найдена тарифная база: {TARIFF_DB}"
        return data

    cur = con.cursor()

    try:
        if not table_exists(cur, "tariff_source_quality"):
            data["error"] = "в unified_tariffs.db нет таблицы tariff_source_quality"
            con.close()
            return data

        row = cur.execute("""
            SELECT
                marketplace,
                source_file,
                source_note,
                source_status,
                source_role,
                comment,
                created_at
            FROM tariff_source_quality
            WHERE marketplace = 'ozon'
            ORDER BY
                CASE WHEN source_role = 'standard_marketplace_service_rate' THEN 0 ELSE 1 END,
                CASE WHEN source_status = 'usable' THEN 0 ELSE 1 END,
                created_at DESC
            LIMIT 1
        """).fetchone()

        if not row:
            data["error"] = "в tariff_source_quality нет Ozon-источника"
            con.close()
            return data

        data.update(dict(row))

        source_file = data["source_file"]

        if table_exists(cur, "clean_commissions"):
            stats = cur.execute("""
                SELECT
                    COUNT(*) AS cnt,
                    MIN(valid_from) AS valid_from_min,
                    MAX(valid_from) AS valid_from_max,
                    MAX(created_at) AS max_created_at
                FROM clean_commissions
                WHERE marketplace = 'ozon'
                  AND fee_type = 'marketplace_service_rate'
                  AND source_file = ?
            """, (source_file,)).fetchone()

            if stats:
                data["standard_rows"] = stats["cnt"] or 0
                data["valid_from_min"] = stats["valid_from_min"]
                data["valid_from_max"] = stats["valid_from_max"]
                if stats["max_created_at"]:
                    data["source_dt"] = parse_dt(stats["max_created_at"])

            select_rows = cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM clean_commissions
                WHERE marketplace = 'ozon'
                  AND (
                    lower(COALESCE(source_file, '')) LIKE '%select%'
                    OR lower(COALESCE(source_file, '')) LIKE '%селект%'
                    OR lower(COALESCE(source_note, '')) LIKE '%select%'
                    OR lower(COALESCE(source_note, '')) LIKE '%селект%'
                  )
            """).fetchone()
            data["select_rows"] = select_rows["cnt"] if select_rows else 0

            select_usable = cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM clean_commissions c
                LEFT JOIN tariff_source_quality q
                  ON q.marketplace = c.marketplace
                 AND q.source_file = c.source_file
                WHERE c.marketplace = 'ozon'
                  AND (
                    lower(COALESCE(c.source_file, '')) LIKE '%select%'
                    OR lower(COALESCE(c.source_file, '')) LIKE '%селект%'
                    OR lower(COALESCE(c.source_note, '')) LIKE '%select%'
                    OR lower(COALESCE(c.source_note, '')) LIKE '%селект%'
                  )
                  AND q.source_status = 'usable'
            """).fetchone()
            data["select_usable_rows"] = select_usable["cnt"] if select_usable else 0

        con.close()

    except Exception as e:
        con.close()
        data["error"] = f"ошибка чтения тарифной базы: {e}"
        return data

    disk_path = find_disk_file(data["source_file"])
    if disk_path:
        data["disk_path"] = str(disk_path)
        try:
            data["disk_mtime"] = datetime.fromtimestamp(disk_path.stat().st_mtime)
        except Exception:
            pass

    con2 = connect(NEWS_DB)
    if con2:
        cur2 = con2.cursor()
        try:
            if table_exists(cur2, "rules_imported_files") and data["source_file"]:
                imp = cur2.execute("""
                    SELECT file_path, rows_imported, imported_at
                    FROM rules_imported_files
                    WHERE file_path LIKE ?
                    ORDER BY id DESC
                    LIMIT 1
                """, (f"%{data['source_file']}%",)).fetchone()
                if imp:
                    data["imported_at"] = imp["imported_at"]
                    data["import_rows"] = imp["rows_imported"]
                    imp_dt = parse_dt(imp["imported_at"])
                    if imp_dt:
                        data["source_dt"] = imp_dt
        except Exception:
            pass
        con2.close()

    # Для возраста приоритет: дата импорта, потом mtime файла, потом created_at/clean_commissions.
    if data.get("source_dt") is None and data.get("disk_mtime"):
        data["source_dt"] = data["disk_mtime"]

    if data.get("source_dt") is None:
        data["source_dt"] = parse_dt(data.get("created_at"))

    data["source_age_days"] = age_days(data.get("source_dt"))
    return data


def count_ozon_signals_after(source_dt):
    result = {
        "tariff_signals_total": 0,
        "tariff_signals_high_medium": 0,
        "rules_signals_total": 0,
        "latest": [],
    }

    con = connect(NEWS_DB)
    if not con:
        return result

    cur = con.cursor()
    after_key = "1900-01-01"
    if source_dt:
        after_key = source_dt.strftime("%Y-%m-%d")

    try:
        if table_exists(cur, "tariff_signals"):
            row = cur.execute("""
                SELECT
                    COUNT(*) AS total,
                    SUM(CASE WHEN signal_level IN ('high', 'medium') THEN 1 ELSE 0 END) AS hm
                FROM tariff_signals
                WHERE marketplace = 'ozon'
                  AND substr(detected_at, 1, 10) >= ?
            """, (after_key,)).fetchone()

            if row:
                result["tariff_signals_total"] = row["total"] or 0
                result["tariff_signals_high_medium"] = row["hm"] or 0

            rows = cur.execute("""
                SELECT detected_at AS dt, signal_level AS level, signal_type AS type, title
                FROM tariff_signals
                WHERE marketplace = 'ozon'
                  AND substr(detected_at, 1, 10) >= ?
                ORDER BY id DESC
                LIMIT 8
            """, (after_key,)).fetchall()

            for r in rows:
                result["latest"].append({
                    "dt": r["dt"],
                    "level": r["level"],
                    "type": r["type"],
                    "title": r["title"],
                    "source": "tariff_signals",
                })

        if table_exists(cur, "rules_signals"):
            row = cur.execute("""
                SELECT COUNT(*) AS total
                FROM rules_signals
                WHERE marketplace = 'ozon'
                  AND substr(created_at, 1, 10) >= ?
            """, (after_key,)).fetchone()
            result["rules_signals_total"] = row["total"] if row else 0

            rows = cur.execute("""
                SELECT created_at AS dt, signal_level AS level, signal_type AS type, title
                FROM rules_signals
                WHERE marketplace = 'ozon'
                  AND substr(created_at, 1, 10) >= ?
                ORDER BY id DESC
                LIMIT 8
            """, (after_key,)).fetchall()

            for r in rows:
                result["latest"].append({
                    "dt": r["dt"],
                    "level": r["level"],
                    "type": r["type"],
                    "title": r["title"],
                    "source": "rules_signals",
                })

    except Exception as e:
        result["error"] = str(e)

    con.close()
    return result


def imported_file_matches(keywords):
    con = connect(NEWS_DB)
    if not con:
        return []

    cur = con.cursor()
    out = []

    try:
        if not table_exists(cur, "rules_imported_files"):
            con.close()
            return []

        for kw in keywords:
            rows = cur.execute("""
                SELECT file_path, rows_imported, imported_at
                FROM rules_imported_files
                WHERE lower(file_path) LIKE lower(?)
                ORDER BY id DESC
                LIMIT 5
            """, (f"%{kw}%",)).fetchall()

            for r in rows:
                item = dict(r)
                if item not in out:
                    out.append(item)

    except Exception:
        pass

    con.close()
    return out


def rules_documents_matches(keywords):
    con = connect(NEWS_DB)
    if not con:
        return {"rows": 0, "latest_loaded": None}

    cur = con.cursor()
    total = 0
    latest = None

    try:
        if not table_exists(cur, "rules_documents"):
            con.close()
            return {"rows": 0, "latest_loaded": None}

        seen_hash = set()

        for kw in keywords:
            row = cur.execute("""
                SELECT COUNT(*) AS cnt, MAX(loaded_at) AS latest
                FROM rules_documents
                WHERE lower(COALESCE(source_url, '')) LIKE lower(?)
                   OR lower(COALESCE(document_name, '')) LIKE lower(?)
            """, (f"%{kw}%", f"%{kw}%")).fetchone()

            if row:
                total += row["cnt"] or 0
                if row["latest"] and (latest is None or row["latest"] > latest):
                    latest = row["latest"]

    except Exception:
        pass

    con.close()
    return {"rows": total, "latest_loaded": latest}


def check_wrong_ozon_offer():
    con = connect(NEWS_DB)
    if not con:
        return 0

    cur = con.cursor()
    cnt = 0

    try:
        if table_exists(cur, "rules_documents"):
            row = cur.execute("""
                SELECT COUNT(*) AS cnt
                FROM rules_documents
                WHERE marketplace = 'ozon'
                  AND lower(COALESCE(rule_text, '')) LIKE '%wildberries%'
            """).fetchone()
            cnt = row["cnt"] if row else 0
    except Exception:
        cnt = 0

    con.close()
    return cnt


def classify_status(tariff, signals):
    red = []
    yellow = []
    green = []

    if tariff["error"]:
        red.append(tariff["error"])
        return "КРАСНЫЙ", red, yellow, green

    if tariff["source_role"] != "standard_marketplace_service_rate":
        red.append("боевой Ozon-источник не помечен как standard_marketplace_service_rate")

    if tariff["source_status"] != "usable":
        red.append("боевой Ozon-источник не имеет статус usable")

    if not tariff["source_file"]:
        red.append("не найден боевой файл Ozon")

    if tariff["standard_rows"] <= 0:
        red.append("в clean_commissions нет строк Ozon marketplace_service_rate по боевому файлу")

    if tariff["select_usable_rows"] > 0:
        red.append("Ozon Select помечен как usable — это нельзя использовать как боевой источник")

    if tariff["source_age_days"] is None:
        yellow.append("возраст Ozon-файла не удалось определить")
    elif tariff["source_age_days"] >= 45:
        red.append(f"Ozon-файл старше 45 дней: {tariff['source_age_days']} дней")
    elif tariff["source_age_days"] >= 14:
        yellow.append(f"Ozon-файл старше 14 дней: {tariff['source_age_days']} дней")

    if signals["tariff_signals_high_medium"] > 0:
        yellow.append(
            f"после загрузки Ozon-файла есть Ozon-сигналы high/medium: {signals['tariff_signals_high_medium']}"
        )
    elif signals["tariff_signals_total"] > 0 or signals["rules_signals_total"] > 0:
        yellow.append(
            f"после загрузки Ozon-файла есть Ozon-сигналы: tariff_signals={signals['tariff_signals_total']}, rules_signals={signals['rules_signals_total']}"
        )

    wrong_offer = check_wrong_ozon_offer()
    if wrong_offer > 0:
        yellow.append(
            f"в rules_documents ещё есть Ozon-строки с текстом Wildberries: {wrong_offer}; lookup их может отфильтровывать, но базу лучше дочистить"
        )

    if not red and not yellow:
        green.append("боевой Ozon-источник найден, строки marketplace_service_rate есть, явных сигналов после загрузки нет")

    if red:
        return "КРАСНЫЙ", red, yellow, green
    if yellow:
        return "ЖЁЛТЫЙ", red, yellow, green
    return "ЗЕЛЁНЫЙ", red, yellow, green


def print_required_package():
    print()
    print("============================================================")
    print("КАКИЕ OZON-ФАЙЛЫ ЖЕЛАТЕЛЬНО ПРОВЕРЯТЬ / ПОДГРУЖАТЬ")
    print("============================================================")

    for item in RECOMMENDED_OZON_PACKAGE:
        imported = imported_file_matches(item["keywords"])
        docs = rules_documents_matches(item["keywords"])

        if imported:
            best = imported[0]
            status = "найден"
            if best.get("rows_imported") in (0, "0", None):
                status = "найден, но rows_imported=0 — проверить импортёр/формат"
            print(f"\n{item['title']}")
            print(f"Статус: {status}")
            print(f"Зачем: {item['why']}")
            print(f"Файл: {best.get('file_path')}")
            print(f"Импортировано строк: {best.get('rows_imported')}")
            print(f"Дата импорта: {best.get('imported_at')}")
            print(f"Строк в rules_documents по похожим ключам: {docs['rows']}")
        else:
            print(f"\n{item['title']}")
            print("Статус: не найден в rules_imported_files")
            print(f"Зачем: {item['why']}")
            print("Что сделать: проверить официальный кабинет/документацию Ozon и при наличии свежего Excel/PDF загрузить вручную.")
            print(f"Поиск по ключам: {', '.join(item['keywords'])}")
            if docs["rows"]:
                print(f"Но в rules_documents есть похожие строки: {docs['rows']}, последняя загрузка: {docs['latest_loaded']}")

        if item["critical"]:
            print("Приоритет: высокий")
        else:
            print("Приоритет: средний")


def main():
    tariff = get_tariff_source()
    signals = count_ozon_signals_after(tariff.get("source_dt"))
    status, red, yellow, green = classify_status(tariff, signals)

    print("============================================================")
    print("OZON SOURCE DIAGNOSTICS / СВЕЖЕСТЬ ИСТОЧНИКОВ OZON")
    print(f"generated_at: {NOW.strftime('%Y-%m-%d %H:%M:%S')}")
    print("============================================================")

    print()
    print("ИТОГОВЫЙ СТАТУС:")
    if status == "ЗЕЛЁНЫЙ":
        print("🟢 Ozon: источник выглядит свежим")
    elif status == "ЖЁЛТЫЙ":
        print("🟡 Ozon: требуется ручная проверка")
    else:
        print("🔴 Ozon: нужна ручная загрузка / исправление источника")

    print()
    print("ОТКУДА БЕРЁТСЯ ВЫВОД:")
    print("• tariff_source_quality — какой Ozon-файл считается боевым")
    print("• clean_commissions — есть ли строки marketplace_service_rate для расчёта")
    print("• rules_imported_files / rules_documents — какие официальные файлы реально загружались")
    print("• tariff_signals / rules_signals — были ли Ozon-сигналы после последней загрузки")

    print()
    print("БОЕВОЙ OZON-ИСТОЧНИК:")
    if tariff["error"]:
        print(f"Ошибка: {tariff['error']}")
    else:
        print(f"Файл: {h(tariff['source_file'])}")
        print(f"Статус источника: {h(tariff['source_status'])}")
        print(f"Роль источника: {h(tariff['source_role'])}")
        print(f"valid_from: {h(tariff['valid_from_min'])} — {h(tariff['valid_from_max'])}")
        print(f"Строк marketplace_service_rate: {tariff['standard_rows']}")
        print(f"Дата источника/импорта: {fmt_dt(tariff['source_dt'])}")
        print(f"Возраст источника: {h(tariff['source_age_days'])} дней")
        print(f"Путь на диске: {h(tariff['disk_path'])}")
        print(f"Импорт rows_imported: {h(tariff['import_rows'])}")
        print(f"Комментарий: {h(tariff['comment'])}")

        print()
        print("OZON SELECT:")
        print(f"Строк Select в базе: {tariff['select_rows']}")
        print(f"Строк Select со статусом usable: {tariff['select_usable_rows']}")
        if tariff["select_usable_rows"] == 0:
            print("OK: Ozon Select не используется как боевой источник.")
        else:
            print("ОШИБКА: Ozon Select нельзя использовать как боевой источник.")

    print()
    print("OZON-СИГНАЛЫ ПОСЛЕ ПОСЛЕДНЕЙ ЗАГРУЗКИ:")
    print(f"tariff_signals всего: {signals['tariff_signals_total']}")
    print(f"tariff_signals high/medium: {signals['tariff_signals_high_medium']}")
    print(f"rules_signals всего: {signals['rules_signals_total']}")

    if signals.get("latest"):
        print()
        print("Последние сигналы:")
        for i, s in enumerate(signals["latest"][:8], 1):
            title = re.sub(r"\s+", " ", s.get("title") or "").strip()
            if len(title) > 160:
                title = title[:157] + "..."
            print(f"{i}. [{s.get('source')}] {h(s.get('dt'))} · {h(s.get('level'))} · {h(s.get('type'))} · {title}")

    print()
    print("ПРИЧИНЫ СТАТУСА:")
    if red:
        print("Красные причины:")
        for x in red:
            print(f"• {x}")
    if yellow:
        print("Жёлтые причины:")
        for x in yellow:
            print(f"• {x}")
    if green:
        print("Зелёные причины:")
        for x in green:
            print(f"• {x}")

    print_required_package()

    print()
    print("============================================================")
    print("АДМИНИСТРАТОРСКАЯ ПОДСКАЗКА")
    print("============================================================")
    if status == "ЗЕЛЁНЫЙ":
        print("Сейчас срочная ручная загрузка Ozon не требуется.")
    elif status == "ЖЁЛТЫЙ":
        print("Проверьте официальный Ozon-кабинет/документацию. Если после текущего боевого файла были изменения по тарифам, возвратам, логистике, размещению, штрафам или выплатам — загрузите свежие Excel/PDF.")
    else:
        print("Нужно вручную загрузить свежие официальные Ozon-файлы и проверить, что боевым источником стал marketplace_service_rate, а не Ozon Select.")

    print()
    print("REPORT END")


if __name__ == "__main__":
    main()
