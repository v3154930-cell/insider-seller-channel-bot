#!/usr/bin/env python3
import argparse
import hashlib
import html
import sqlite3
import urllib.request
import xml.etree.ElementTree as ET

SOURCE_KEY = "regulation_public_discussions"


def default_db() -> str:
    return "/opt/newsbot_v2/data/rag_store.db"


def clean(s: str | None) -> str:
    if not s:
        return ""
    return html.unescape(" ".join(str(s).replace("\n", " ").replace("\r", " ").split()))


def child_text(node: ET.Element, name: str) -> str:
    x = node.find(name)
    return clean(x.text if x is not None else "")


def fetch_xml(url: str, timeout: int) -> ET.Element:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 InsiderSellerBot/1.0 regulation-approved-ingest"},
    )
    raw = urllib.request.urlopen(req, timeout=timeout).read()
    return ET.fromstring(raw)


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def ensure_rag_documents_columns(conn: sqlite3.Connection) -> None:
    existing = columns(conn, "rag_documents")
    additions = {
        "source_key": "TEXT",
        "source_url": "TEXT",
        "raw_text": "TEXT",
        "ingest_status": "TEXT DEFAULT 'ingested'",
        "error_reason": "TEXT",
        "skip_reason": "TEXT",
        "rag_layer": "TEXT DEFAULT 'news_signal'",
        "trust_level": "TEXT DEFAULT 'medium'",
    }
    for name, decl in additions.items():
        if name not in existing:
            conn.execute(f'ALTER TABLE rag_documents ADD COLUMN "{name}" {decl}')
    conn.commit()


def build_document_from_project(project: ET.Element, candidate: sqlite3.Row) -> dict:
    title = child_text(project, "title") or clean(candidate["title"])
    project_id = child_text(project, "projectId") or clean(candidate["project_id"])
    publish_date = child_text(project, "publishDate") or clean(candidate["publish_date"])
    date = child_text(project, "date")
    stage = child_text(project, "stage")
    status = child_text(project, "status") or clean(candidate["status"])
    regulatory_impact = child_text(project, "regulatoryImpact")
    procedure_result = child_text(project, "procedureResult")
    kind = child_text(project, "kind")
    department = child_text(project, "department") or clean(candidate["department"])
    procedure = child_text(project, "procedure")
    responsible = child_text(project, "responsible")
    problem = child_text(project, "problem")
    objective = child_text(project, "objective")
    solution = child_text(project, "solution")
    effect = child_text(project, "effect")
    start_discussion = child_text(project, "startDiscussion")
    end_discussion = child_text(project, "endDiscussion")

    parts = [
        f"Источник: Федеральный портал проектов нормативных правовых актов",
        f"URL API: {candidate['candidate_url']}",
        f"Внутренний ID проекта: {candidate['external_id']}",
        f"Номер проекта: {project_id}",
        f"Название: {title}",
        f"Ведомство: {department}",
        f"Тип: {kind}",
        f"Стадия: {stage}",
        f"Статус: {status}",
        f"Дата проекта: {date}",
        f"Дата публикации: {publish_date}",
        f"Начало обсуждения: {start_discussion}",
        f"Окончание обсуждения: {end_discussion}",
        f"Оценка регулирующего воздействия: {regulatory_impact}",
        f"Результат процедуры: {procedure_result}",
        f"Процедура: {procedure}",
        f"Ответственный: {responsible}",
        f"Проблема: {problem}",
        f"Цель: {objective}",
        f"Решение: {solution}",
        f"Ожидаемый эффект: {effect}",
    ]

    clean_text = "\n".join(p for p in parts if p and not p.endswith(": "))
    content_hash = hashlib.sha256((candidate["candidate_url"] + "\n" + clean_text).encode("utf-8")).hexdigest()

    return {
        "title": title,
        "clean_text": clean_text,
        "markdown_text": clean_text,
        "source": "regulation.gov.ru API",
        "source_type": "official_api",
        "marketplace": "all",
        "document_type": "legal_official_project",
        "topic": "regulation_project",
        "impact_level": "medium",
        "published_at": publish_date,
        "source_url": candidate["candidate_url"],
        "source_key": SOURCE_KEY,
        "raw_text": ET.tostring(project, encoding="unicode"),
        "content_hash": content_hash,
        "rag_layer": "legal_official",
        "trust_level": "high",
        "ingest_status": "ingested",
        "rag_eligible": 1,
        "eligibility_reason": "approved regulation.gov.ru API candidate",
    }


def source_exists(conn: sqlite3.Connection, source_url: str) -> bool:
    row = conn.execute(
        "SELECT id FROM rag_documents WHERE source_url=? AND COALESCE(ingest_status, '')='ingested' LIMIT 1",
        (source_url,),
    ).fetchone()
    return row is not None


def insert_document(conn: sqlite3.Connection, doc: dict) -> int:
    available = columns(conn, "rag_documents")
    keys = [k for k in doc if k in available]
    sql = "INSERT INTO rag_documents (%s) VALUES (%s)" % (
        ", ".join('"%s"' % k for k in keys),
        ", ".join("?" for _ in keys),
    )
    cur = conn.execute(sql, [doc[k] for k in keys])
    return int(cur.lastrowid)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=default_db())
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--timeout-seconds", type=int, default=30)
    args = ap.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    ensure_rag_documents_columns(conn)

    candidates = conn.execute("""
    SELECT *
    FROM analytics_source_candidates
    WHERE source_key=?
      AND candidate_status='approved'
    ORDER BY score DESC, publish_date DESC
    LIMIT ?
    """, (SOURCE_KEY, args.limit)).fetchall()

    print("approved_candidates_selected=%d dry_run=%s" % (len(candidates), args.dry_run))

    stats = {"would_ingest": 0, "ingested": 0, "duplicate": 0, "error": 0}

    for c in candidates:
        url = c["candidate_url"]
        external_id = c["external_id"]

        if source_exists(conn, url):
            print(f"external_id={external_id} status=skipped reason=duplicate_source_url url={url}")
            stats["duplicate"] += 1
            continue

        try:
            root = fetch_xml(url, args.timeout_seconds)
            project = root.find("project")
            if project is None:
                print(f"external_id={external_id} status=error reason=missing_project_node url={url}")
                stats["error"] += 1
                continue

            doc = build_document_from_project(project, c)
            if len(doc["clean_text"]) < 500:
                print(f"external_id={external_id} status=error reason=short_clean_text len={len(doc['clean_text'])} url={url}")
                stats["error"] += 1
                continue

            if args.dry_run:
                print(f"external_id={external_id} status=dry_run reason=would_ingest len={len(doc['clean_text'])} title={doc['title'][:160]}")
                stats["would_ingest"] += 1
            else:
                doc_id = insert_document(conn, doc)
                conn.execute("""
                UPDATE analytics_source_candidates
                SET candidate_status='ingested', updated_at=CURRENT_TIMESTAMP
                WHERE id=?
                """, (c["id"],))
                conn.commit()
                print(f"external_id={external_id} status=ingested rag_document_id={doc_id} len={len(doc['clean_text'])} title={doc['title'][:160]}")
                stats["ingested"] += 1

        except Exception as e:
            print(f"external_id={external_id} status=error reason={type(e).__name__}:{e} url={url}")
            stats["error"] += 1

    print("summary=" + ",".join(f"{k}:{v}" for k, v in stats.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
