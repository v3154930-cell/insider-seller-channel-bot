#!/usr/bin/env python3
import argparse
import datetime as dt
import html
import sqlite3
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SOURCE_KEY = "regulation_public_discussions"
BASE = "https://regulation.gov.ru/api/npalist"

QUERIES = [
    "маркировка",
    "НДС",
    "налоговый кодекс",
    "ФНС НДС",
    "Минфин НДС",
    "сертификация продукции",
    "декларация соответствия",
    "упаковка маркировка",
    "товары маркировка",
    "оборот товаров",
]

GOOD_DEPARTMENTS = [
    "ФНС России",
    "Минфин России",
    "Минпромторг России",
    "ФАС России",
    "Роспотребнадзор",
    "Минэкономразвития России",
    "ФТС России",
]

GOOD_WORDS = [
    "маркировк",
    "ндс",
    "налог",
    "налогового кодекса",
    "фнс",
    "минфин",
    "минпромторг",
    "фас",
    "товар",
    "продукц",
    "оборот",
    "упаков",
    "тара",
    "этикет",
    "деклараци",
    "соответств",
    "сертификац",
    "реестр",
    "электронной форме",
]

BAD_WORDS = [
    "аэродром",
    "авиац",
    "воздушн",
    "газораспредел",
    "санитарно-защитной зоны",
    "наркотическ",
    "психотроп",
    "семян сельскохозяйственных",
    "водных объектов",
    "медицинских организаций",
    "метеорологического оборудования",
]


def default_db() -> str:
    return "/opt/newsbot_v2/data/rag_store.db"


def clean(s: str | None) -> str:
    if not s:
        return ""
    return html.unescape(" ".join(s.replace("\n", " ").replace("\r", " ").split()))


def child_text(node: ET.Element, name: str) -> str:
    x = node.find(name)
    return clean(x.text if x is not None else "")


def parse_year(value: str) -> int:
    try:
        return int((value or "")[:4])
    except Exception:
        return 0


def score_project(item: dict) -> tuple[int, list[str], list[str]]:
    score = 0
    reasons = []
    negatives = []

    title_l = item["title"].lower()
    blob_l = " ".join([
        item["title"],
        item["department"],
        item["status"],
        item["problem"],
        item["project_id"],
    ]).lower()

    year = parse_year(item["publish_date"])
    if year >= 2025:
        score += 6
        reasons.append("date>=2025")
    elif year >= 2024:
        score += 5
        reasons.append("date>=2024")
    elif year >= 2023:
        score += 2
        reasons.append("date>=2023")
    else:
        score -= 6
        negatives.append("old_date")

    if item["department"] in GOOD_DEPARTMENTS:
        score += 4
        reasons.append("good_department:" + item["department"])

    matched = []
    for w in GOOD_WORDS:
        if w in blob_l:
            matched.append(w)
    if matched:
        score += min(8, len(set(matched)) * 2)
        reasons.append("keywords:" + ",".join(sorted(set(matched))[:8]))

    bad = []
    for w in BAD_WORDS:
        if w in blob_l:
            bad.append(w)
    if bad:
        score -= min(10, len(set(bad)) * 5)
        negatives.append("noise:" + ",".join(sorted(set(bad))[:6]))

    if "обсуждение завершено" in item["status"].lower():
        score += 1
        reasons.append("status_discussion_done")
    if "идет обсуждение" in item["status"].lower() or "разработка" in item["status"].lower():
        score += 2
        reasons.append("active_or_development")

    if len(title_l) < 25:
        score -= 5
        negatives.append("short_title")

    return score, reasons, negatives


def fetch_xml(url: str, timeout: int) -> ET.Element:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 InsiderSellerBot/1.0 regulation-discovery"},
    )
    raw = urllib.request.urlopen(req, timeout=timeout).read()
    return ET.fromstring(raw)


def ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
    CREATE TABLE IF NOT EXISTS analytics_source_candidates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_key TEXT NOT NULL,
        candidate_url TEXT NOT NULL,
        external_id TEXT,
        project_id TEXT,
        title TEXT,
        department TEXT,
        status TEXT,
        publish_date TEXT,
        score INTEGER DEFAULT 0,
        matched_keywords TEXT,
        negative_reasons TEXT,
        candidate_status TEXT DEFAULT 'candidate',
        raw_summary TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(source_key, candidate_url)
    )
    """)
    conn.commit()


def upsert_candidate(conn: sqlite3.Connection, item: dict) -> None:
    conn.execute("""
    INSERT INTO analytics_source_candidates (
        source_key, candidate_url, external_id, project_id, title,
        department, status, publish_date, score, matched_keywords,
        negative_reasons, candidate_status, raw_summary, updated_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(source_key, candidate_url) DO UPDATE SET
        project_id=excluded.project_id,
        title=excluded.title,
        department=excluded.department,
        status=excluded.status,
        publish_date=excluded.publish_date,
        score=excluded.score,
        matched_keywords=excluded.matched_keywords,
        negative_reasons=excluded.negative_reasons,
        raw_summary=excluded.raw_summary,
        updated_at=CURRENT_TIMESTAMP
    """, (
        item["source_key"],
        item["candidate_url"],
        item["external_id"],
        item["project_id"],
        item["title"],
        item["department"],
        item["status"],
        item["publish_date"],
        item["score"],
        item["matched_keywords"],
        item["negative_reasons"],
        item["candidate_status"],
        item["raw_summary"],
    ))


def discover(args: argparse.Namespace) -> int:
    conn = sqlite3.connect(args.db)
    ensure_table(conn)

    seen = set()
    accepted = []

    for query in QUERIES:
        url = BASE + "?limit=%d&sort=desc&search=%s" % (
            args.limit_per_query,
            urllib.parse.quote(query),
        )
        print("\nQUERY", query)
        try:
            root = fetch_xml(url, args.timeout_seconds)
        except Exception as e:
            print("ERR fetch_list", repr(e))
            continue

        projects = root.findall("project")
        print("items", len(projects), "total_attr", root.attrib.get("total"))

        for p in projects:
            external_id = p.attrib.get("id") or ""
            if not external_id or external_id in seen:
                continue
            seen.add(external_id)

            item = {
                "source_key": SOURCE_KEY,
                "external_id": external_id,
                "candidate_url": BASE + "/" + external_id,
                "project_id": child_text(p, "projectId"),
                "title": child_text(p, "title"),
                "department": child_text(p, "department"),
                "status": child_text(p, "status"),
                "publish_date": child_text(p, "publishDate"),
                "problem": child_text(p, "problem"),
            }

            score, reasons, negatives = score_project(item)
            item["score"] = score
            item["matched_keywords"] = ";".join(reasons)
            item["negative_reasons"] = ";".join(negatives)
            year = parse_year(item["publish_date"])
            if year and year < args.min_year:
                item["candidate_status"] = "rejected_old_date"
            elif score >= args.min_score:
                item["candidate_status"] = "candidate"
            else:
                item["candidate_status"] = "rejected_low_score"

            item["raw_summary"] = clean(" | ".join([
                item["title"],
                item["project_id"],
                item["department"],
                item["status"],
                item["publish_date"],
                item["problem"],
            ]))[:4000]

            if score >= args.min_score:
                accepted.append(item)

            print(
                "score=%s id=%s date=%s dept=%s status=%s title=%s" %
                (score, external_id, item["publish_date"], item["department"], item["status"], item["title"][:180])
            )
            if reasons:
                print("  +", ";".join(reasons))
            if negatives:
                print("  -", ";".join(negatives))

            if not args.dry_run:
                upsert_candidate(conn, item)

        time.sleep(args.sleep_seconds)

    if not args.dry_run:
        conn.commit()

    print("\nsummary accepted_score>=%d: %d unique_seen: %d dry_run: %s" % (
        args.min_score,
        len(accepted),
        len(seen),
        args.dry_run,
    ))

    print("\nTOP CANDIDATES")
    for item in sorted(accepted, key=lambda x: x["score"], reverse=True)[:args.top]:
        print(
            "score=%s id=%s date=%s dept=%s url=%s title=%s" %
            (
                item["score"],
                item["external_id"],
                item["publish_date"],
                item["department"],
                item["candidate_url"],
                item["title"][:220],
            )
        )

    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=default_db())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit-per-query", type=int, default=20)
    ap.add_argument("--timeout-seconds", type=int, default=30)
    ap.add_argument("--min-score", type=int, default=12)
    ap.add_argument("--min-year", type=int, default=2023)
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--sleep-seconds", type=float, default=0.2)
    args = ap.parse_args()
    return discover(args)


if __name__ == "__main__":
    raise SystemExit(main())
