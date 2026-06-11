#!/usr/bin/env python3
import datetime as dt
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path("/opt/newsbot_v2")
DB = ROOT / "data" / "rag_store.db"
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
SOURCE_KEY = "regulation_public_discussions"

DISCOVER = ROOT / "newsbot_v3" / "tools" / "discover_regulation_api_candidates_v1.py"
INGEST = ROOT / "newsbot_v3" / "tools" / "ingest_regulation_approved_candidates_v1.py"

AUTO_MIN_SCORE = 17
AUTO_MIN_YEAR = 2024
AUTO_LIMIT_PER_QUERY = 30
AUTO_INGEST_LIMIT = 30

GOOD_DEPARTMENTS = {
    "ФНС России",
    "Минфин России",
    "Минпромторг России",
    "ФАС России",
    "ФТС России",
    "Роспотребнадзор",
}

BAD_TITLE_WORDS = [
    "аэродром",
    "авиац",
    "воздушн",
    "мчс",
    "аварийно-спасат",
    "наркотическ",
    "психотроп",
    "семеноводств",
    "семян сельскохозяйственных",
    "медицинских организаций",
    "санитарно-защитной зоны",
]

GOOD_TITLE_WORDS = [
    "ндс",
    "налогового кодекса",
    "федеральной налоговой службы",
    "фнс",
    "маркировк",
    "перечень товаров",
    "групп товаров",
    "оборот",
    "упаков",
    "деклараци",
    "соответств",
    "сертификац",
    "реестр",
]


def log(msg: str) -> None:
    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)


def run(cmd: list[str]) -> None:
    log("RUN: " + " ".join(cmd))
    subprocess.run(cmd, cwd=str(ROOT), check=True)


def year_from_date(value: str) -> int:
    try:
        return int((value or "")[:4])
    except Exception:
        return 0


def auto_approve() -> int:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row

    rows = con.execute("""
    SELECT id, external_id, score, publish_date, department, title, candidate_url
    FROM analytics_source_candidates
    WHERE source_key=?
      AND candidate_status='candidate'
    ORDER BY score DESC, publish_date DESC
    """, (SOURCE_KEY,)).fetchall()

    approved = 0
    rejected = 0

    for r in rows:
        title_l = (r["title"] or "").lower()
        department = r["department"] or ""
        year = year_from_date(r["publish_date"])
        score = int(r["score"] or 0)

        bad_hit = any(w in title_l for w in BAD_TITLE_WORDS)
        good_hit = any(w in title_l for w in GOOD_TITLE_WORDS)
        good_department = department in GOOD_DEPARTMENTS

        if (
            score >= AUTO_MIN_SCORE
            and year >= AUTO_MIN_YEAR
            and good_department
            and good_hit
            and not bad_hit
        ):
            con.execute("""
            UPDATE analytics_source_candidates
            SET candidate_status='approved', updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """, (r["id"],))
            approved += 1
            log(f"AUTO_APPROVED external_id={r['external_id']} score={score} year={year} dept={department} title={r['title'][:160]}")
        else:
            rejected += 1
            log(f"KEEP_CANDIDATE external_id={r['external_id']} score={score} year={year} dept={department} good_hit={good_hit} bad_hit={bad_hit} title={r['title'][:120]}")

    con.commit()
    return approved


def rebuild_fts() -> None:
    con = sqlite3.connect(DB)
    con.execute("INSERT INTO rag_documents_fts(rag_documents_fts) VALUES('rebuild')")
    con.commit()
    log("FTS rebuilt")


def summary() -> None:
    con = sqlite3.connect(DB)

    log("candidate statuses:")
    for row in con.execute("""
    SELECT candidate_status, COUNT(*)
    FROM analytics_source_candidates
    WHERE source_key=?
    GROUP BY candidate_status
    ORDER BY candidate_status
    """, (SOURCE_KEY,)):
        log(str(row))

    log("latest regulation official_api docs:")
    for row in con.execute("""
    SELECT id, title, source_type, rag_layer, trust_level, source_url, length(clean_text)
    FROM rag_documents
    WHERE source_key=?
    ORDER BY id DESC
    LIMIT 10
    """, (SOURCE_KEY,)):
        log(str(row))


def main() -> int:
    log("regulation auto pipeline started")

    if not DISCOVER.exists():
        raise SystemExit(f"missing discover script: {DISCOVER}")
    if not INGEST.exists():
        raise SystemExit(f"missing ingest script: {INGEST}")

    backup = ROOT / "data" / f"rag_store.db.bak_before_regulation_auto_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run(["cp", str(DB), str(backup)])
    log(f"backup created: {backup}")

    run([
        str(ROOT / "venv" / "bin" / "python"),
        str(DISCOVER),
        "--limit-per-query", str(AUTO_LIMIT_PER_QUERY),
        "--min-score", "12",
        "--min-year", str(AUTO_MIN_YEAR),
        "--top", "50",
    ])

    approved = auto_approve()
    log(f"auto_approved_count={approved}")

    if approved > 0:
        run([
            str(ROOT / "venv" / "bin" / "python"),
            str(INGEST),
            "--limit", str(AUTO_INGEST_LIMIT),
        ])
        rebuild_fts()
    else:
        log("nothing approved, ingest skipped")

    summary()
    log("regulation auto pipeline finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
