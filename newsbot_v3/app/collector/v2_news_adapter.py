from __future__ import annotations
import sqlite3
from pathlib import Path

TITLE_FIELDS = ("title", "summary", "text")
BODY_FIELDS = ("full_text", "raw_text", "content", "text", "summary", "title")
LINK_FIELDS = ("link", "url")
SOURCE_FIELDS = ("source", "source_name")
DATE_FIELDS = ("published_at", "published", "created_at", "collected_at")


def _db_uri(db_path: str | Path) -> str:
    return f"file:{Path(db_path)}?mode=ro"


def _connect_ro(db_path: str | Path) -> sqlite3.Connection:
    return sqlite3.connect(_db_uri(db_path), uri=True)


def get_news_columns(db_path: str | Path) -> list[str]:
    with _connect_ro(db_path) as con:
        rows = con.execute("PRAGMA table_info(news)").fetchall()
    return [str(r[1]) for r in rows]


def _first_available(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    cols = {c.lower(): c for c in columns}
    for item in candidates:
        if item.lower() in cols:
            return cols[item.lower()]
    return None


def normalize_v2_row(row: sqlite3.Row | tuple, columns: list[str]) -> dict:
    values = dict(zip(columns, row))
    rid = values.get("id")
    title_col = _first_available(columns, TITLE_FIELDS)
    body_col = _first_available(columns, BODY_FIELDS)
    link_col = _first_available(columns, LINK_FIELDS)
    source_col = _first_available(columns, SOURCE_FIELDS)
    date_col = _first_available(columns, DATE_FIELDS)
    status = values.get("status", values.get("published"))
    title = values.get(title_col) if title_col else None
    body = values.get(body_col) if body_col else None

    return {
        "id": f"v2-{rid}",
        "v2_news_id": str(rid) if rid is not None else None,
        "title": str(title or f"v2 news {rid}"),
        "text": str(body or title or ""),
        "link": str(values.get(link_col)) if link_col and values.get(link_col) else None,
        "source": str(values.get(source_col) or "v2") if source_col else "v2",
        "published_at": str(values.get(date_col)) if date_col and values.get(date_col) else None,
        "status": str(status) if status is not None else None,
        "raw": values,
    }


def _build_select(columns: list[str], limit: int, unpublished_only: bool) -> tuple[str, tuple]:
    order_col = _first_available(columns, ("published_at", "created_at", "collected_at", "id")) or "id"
    where = ""
    if unpublished_only:
        if "status" in columns:
            where = "WHERE (status IS NULL OR lower(status) NOT IN ('published','done','sent'))"
        elif "published" in columns:
            where = "WHERE (published IS NULL OR published = 0 OR lower(CAST(published as text)) IN ('false','no'))"
    q = f"SELECT {', '.join(columns)} FROM news {where} ORDER BY {order_col} DESC LIMIT ?"
    return q, (limit,)


def _load_rows(db_path: str | Path, limit: int, unpublished_only: bool) -> list[dict]:
    cols = get_news_columns(db_path)
    if not cols:
        return []
    query, params = _build_select(cols, limit, unpublished_only)
    with _connect_ro(db_path) as con:
        rows = con.execute(query, params).fetchall()
    return [normalize_v2_row(r, cols) for r in rows]


def load_recent_news(db_path: str | Path, limit: int = 10) -> list[dict]:
    return _load_rows(db_path, limit=limit, unpublished_only=False)


def load_unpublished_news(db_path: str | Path, limit: int = 10) -> list[dict]:
    return _load_rows(db_path, limit=limit, unpublished_only=True)
