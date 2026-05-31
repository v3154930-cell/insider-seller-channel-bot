import argparse
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from publisher import send_message

GOOD_MARKERS = ["ozon", "озон", "wildberries", "wb", "вайлдберриз", "яндекс маркет", "маркетплейс", "селлер", "продавец", "отзывы", "рейтинг", "тариф", "комиссия", "логистика", "маркировка", "карточк", "api", "кабинет"]
BAD_MARKERS = ["нефть", "epharma", "аптеки", "бараны", "отели", "usdt"]
FALLBACK_DECISIONS = ("digest", "ignore", "duplicate", "pending")

IMPORTANCE_RULES = [
    ("🔴 Важно для селлера", ["комис", "тариф", "логист", "маркиров", "штраф", "блокир", "карточ", "отзыв", "рейтинг", "выплат", "правил", "оферт", "fbo", "fbs"]),
    ("🟡 Общая информация", ["рынок", "исследован", "статист", "динамик", "спрос", "аналит", "тренд"]),
]



def load_env_file(env_path: str = ".env") -> None:
    p = Path(env_path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        if k.strip() and k.strip() not in os.environ:
            os.environ[k.strip()] = v.strip().strip('"').strip("'")


def norm(text: Any) -> str:
    return str(text or "").lower().replace("ё", "е")


def contains_phrase(text: str, phrase: str) -> bool:
    p = norm(phrase).strip()
    return bool(p and ((p in text) if " " in p else re.search(r"(?<![a-zа-я0-9])" + re.escape(p) + r"(?![a-zа-я0-9])", text)))


def safe_trim_post(text: str, limit: int = 1200) -> tuple[str, bool]:
    text = (text or "").strip()
    if len(text) <= limit:
        return text, False
    cut = text[:limit]
    boundaries = [cut.rfind(x) for x in (". ", "! ", "? ", "\n")]
    best = max(boundaries)
    if best > 500:
        cut = cut[:best + 1].strip()
    else:
        cut = cut.rsplit(" ", 1)[0].strip()
    return cut + "\n\nПодробнее — по кнопке ниже.", True


def build_read_more_button(item: Dict[str, Any]) -> Dict[str, str]:
    link = str(item.get("link") or "").strip()
    if link:
        return {"type": "link", "text": "📖 Читать полностью", "url": link}
    full_article_news_id = item.get("full_article_news_id") or item.get("id")
    if full_article_news_id:
        return {"type": "callback", "text": "📖 Читать полностью", "payload": f"full_article:{full_article_news_id}"}
    return {}


def _importance_indicator(text: str) -> str:
    t = norm(text)
    for label, keys in IMPORTANCE_RULES:
        if any(k in t for k in keys):
            return label
    return "🔵 Просто интересно"




def _is_strong_yellow(text: str) -> bool:
    t = norm(text)
    strong_keys = ["маркетплейс", "селлер", "продав", "комис", "тариф", "логист", "карточ", "fbo", "fbs", "wb", "wildberries", "ozon", "яндекс"]
    return any(k in t for k in strong_keys)


def _candidate_skip_reason_after_min(item: Dict[str, Any], daily_min_target: int, published_today: int, selected_reason: str) -> tuple[bool, str, str]:
    importance_probe = " ".join([str(item.get("title") or ""), str(item.get("seller_analysis") or item.get("processed_text") or item.get("raw_text") or ""), str(item.get("source") or "")])
    importance = _importance_indicator(importance_probe)
    if selected_reason != "emergency_fallback" or published_today < daily_min_target:
        return False, importance, ""
    if importance.startswith("🔵"):
        return True, importance, "skipped_low_value_after_min"
    if importance.startswith("🟡") and not _is_strong_yellow(importance_probe):
        return True, importance, "skipped_weak_yellow_after_min"
    return False, importance, ""

def _short_summary(text: str, limit: int = 360) -> str:
    cleaned = re.sub(r"https?://\S+", "", str(text or "")).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return "Вышла новая публикация по рынку и маркетплейсам."
    return cleaned[:limit].rstrip(" ,;:-") + ("." if cleaned and cleaned[:limit][-1] not in ".!?" else "")


def _seller_conclusion(title: str, body: str, importance: str) -> str:
    t = norm(" ".join([title, body]))
    if importance.startswith("🔴"):
        if any(k in t for k in ["комис", "тариф", "логист", "выплат"]):
            return "Проверьте экономику по ключевым SKU и заранее оцените влияние изменений на цены, сроки и прибыль."
        if any(k in t for k in ["маркиров", "правил", "штраф", "блокир"]):
            return "Сверьте новые требования с текущими процессами, чтобы избежать штрафов, ограничений и просадок по продажам."
        return "Новость влияет на операционные решения: оцените риски и внесите точечные изменения в процессы."
    if importance.startswith("🟡"):
        return "Это фоновый сигнал рынка: используйте его для планирования ассортимента, бюджета и сезонных гипотез."
    return "Прямого действия не требуется: сохраните как контекст и вернитесь к новости при изменении вашей категории."


def _pick_image_url(item: Dict[str, Any]) -> str:
    for key in ("image_url", "media_url", "picture", "thumbnail"):
        val = str(item.get(key) or "").strip()
        if val:
            return val
    return ""

def build_seller_post(item: Dict[str, Any]) -> str:
    title = str(item.get("title") or "Обновление для селлеров").strip()
    body = str(item.get("seller_analysis") or item.get("processed_text") or item.get("raw_text") or "").strip()
    source = str(item.get("source") or "Источник не указан").strip()
    link = str(item.get("link") or "").strip()
    if title and body and norm(body).startswith(norm(title)):
        body = body[len(title):].strip("\n :-")

    summary = _short_summary(body)
    importance = _importance_indicator(" ".join([title, body, source]))
    seller_conclusion = _seller_conclusion(title, body, importance)

    lines = [
        f"<b>{title}</b>",
        "",
        summary,
        "",
        "Вывод для селлера:",
        seller_conclusion,
        "",
        importance,
        f"Источник: {source}",
    ]
    if link and not build_read_more_button(item):
        lines.append(f"Ссылка на источник: {link}")
    return "\n".join(lines).strip()

def _daily_min_target(now_local: datetime) -> int:
    return 3 if now_local.weekday() >= 5 else 10


def _time_window_open(now_local: datetime) -> bool:
    return 6 <= now_local.hour < 23


def published_today_count(conn: sqlite3.Connection) -> int:
    return int(conn.execute("SELECT COUNT(*) FROM news WHERE is_published = 1 AND DATE(COALESCE(full_article_published_at, created_at)) = DATE('now', 'localtime')").fetchone()[0])


def fetch_direct_publish(conn):
    row = conn.execute("SELECT * FROM news WHERE is_published = 0 AND seller_decision = 'publish' ORDER BY COALESCE(seller_relevance_score,0) DESC, COALESCE(actionability_score,0) DESC, id ASC LIMIT 1").fetchone()
    return dict(row) if row else None


def fetch_emergency_candidates(conn):
    placeholders = ",".join("?" for _ in FALLBACK_DECISIONS)
    rows = conn.execute(f"SELECT * FROM news WHERE is_published = 0 AND seller_decision IN ({placeholders})", FALLBACK_DECISIONS).fetchall()
    scored = []
    for row in rows:
        item = dict(row)
        t = norm(" ".join([item.get("title", ""), item.get("raw_text", ""), item.get("source", "")]))
        score = sum(1 for m in GOOD_MARKERS if contains_phrase(t, m)) * 3 - sum(1 for m in BAD_MARKERS if contains_phrase(t, m)) * 4
        item["_emergency_score"] = score
        scored.append(item)
    return scored


def _fallback_priority(item: Dict[str, Any]) -> int:
    importance_probe = " ".join([str(item.get("title") or ""), str(item.get("seller_analysis") or item.get("processed_text") or item.get("raw_text") or ""), str(item.get("source") or "")])
    importance = _importance_indicator(importance_probe)
    seller_relevance = int(item.get("seller_relevance_score") or 0)
    actionability = int(item.get("actionability_score") or 0)
    if importance.startswith("🔴"):
        return 4
    if importance.startswith("🟡") and _is_strong_yellow(importance_probe):
        return 3
    if seller_relevance >= 2 and actionability >= 2:
        return 2
    if importance.startswith("🟡"):
        return 1
    return 0



def build_post(item: Dict[str, Any]) -> str:
    return build_seller_post(item)

def build_seller_helper_cta_text() -> str:
    return "🧮 <b>Проверить комиссию и прибыль</b>\n\nХотите понять, как комиссия, тариф и налог влияют на прибыль товара?\n\nОткройте Seller Helper и напишите:\n• WB ботинки\n• Ozon чайник\n• Яндекс косметика\n\nСейчас идёт тестирование и предпродакшен — сравнение площадок пока доступно бесплатно."


def get_seller_helper_url() -> str:
    for k in ("SELLER_HELPER_BOT_URL", "HELPER_BOT_URL", "MAX_HELPER_BOT_URL", "SELLER_HELPER_URL", "SELLER_HELPER_BOT_LINK"):
        if os.getenv(k, "").strip():
            return os.getenv(k, "").strip()
    return ""


@contextmanager
def _temp_helper_env(url: str):
    prev = os.environ.get("SELLER_HELPER_BOT_URL")
    os.environ["SELLER_HELPER_BOT_URL"] = url
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("SELLER_HELPER_BOT_URL", None)
        else:
            os.environ["SELLER_HELPER_BOT_URL"] = prev


def send_seller_helper_cta(token: str, channel_id: str):
    url = get_seller_helper_url()
    if not url:
        return "skipped_no_url"
    with _temp_helper_env(url):
        send_message(token, channel_id, build_seller_helper_cta_text(), add_helper_button=True)
    return "ok"


def extract_message_id(result: Any) -> str:
    if not isinstance(result, dict):
        return ""

    nested_paths = [
        ("message", "body", "mid"),
        ("message", "id"),
        ("body", "mid"),
    ]
    for path in nested_paths:
        cur = result
        for key in path:
            if not isinstance(cur, dict):
                cur = None
                break
            cur = cur.get(key)
        if cur not in (None, ""):
            return str(cur)

    for k in ("message_id", "id", "mid"):
        if result.get(k) not in (None, ""):
            return str(result.get(k))
    return ""


def main() -> int:
    load_env_file()
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=1)
    args = parser.parse_args()
    print(f"batch_size={max(1,int(args.batch_size or 1))}")
    db_path = os.getenv("NEWS_DB_PATH") or os.getenv("DB_PATH") or "news_queue.db"
    print(f"DB_PATH={db_path}")
    print("daily_cap_applied=false")
    now_local = datetime.now().astimezone()
    print(f"daily_min_target={_daily_min_target(now_local)}")
    print(f"time_window_open={str(_time_window_open(now_local)).lower()}")
    print("publish_window=06:00-23:00")
    conn = sqlite3.connect(db_path); conn.row_factory = sqlite3.Row
    print(f"published_today={published_today_count(conn)}")
    print(f"pending_publish_before={int(conn.execute("SELECT COUNT(*) FROM news WHERE is_published=0 AND seller_decision=\'publish\'").fetchone()[0])}")
    direct_item = fetch_direct_publish(conn)
    fallback_candidates = fetch_emergency_candidates(conn) if not direct_item else []
    fallback_candidates_seen = 0
    fallback_candidates_skipped_low_value = 0
    fallback_publishable_candidates = 0
    selected_candidate_id = ""
    selected_candidate_score = ""
    item = direct_item
    selected_reason = "direct_publish" if direct_item else "none"
    published_today = published_today_count(conn)
    low_value_after_min_skipped = False
    candidate_importance = ""
    candidate_skip_reason = ""
    if not item and fallback_candidates:
        daily_min_target = _daily_min_target(now_local)
        allow_weak_blue = published_today < daily_min_target
        candidates_ranked = sorted(fallback_candidates, key=lambda c: (_fallback_priority(c), int(c.get("_emergency_score", 0)), -int(c.get("id", 0))), reverse=True)
        best = None
        for cand in candidates_ranked:
            fallback_candidates_seen += 1
            rank = _fallback_priority(cand)
            if rank >= 2:
                fallback_publishable_candidates += 1
            if not allow_weak_blue and rank == 0:
                fallback_candidates_skipped_low_value += 1
                continue
            if best is None:
                best = cand
        if best:
            item = best
            selected_reason = "emergency_fallback"
            selected_candidate_id = str(best.get("id") or "")
            selected_candidate_score = str(best.get("_emergency_score") if best.get("_emergency_score") is not None else "")
        elif fallback_candidates_seen > 0 and fallback_candidates_skipped_low_value == fallback_candidates_seen and not allow_weak_blue:
            selected_reason = "skipped_low_value_after_min"
    if item:
        low_value_after_min_skipped, candidate_importance, candidate_skip_reason = _candidate_skip_reason_after_min(item, _daily_min_target(now_local), published_today, selected_reason)
    print(f"selected_reason={selected_reason}")
    print(f"low_value_after_min_skipped={str(low_value_after_min_skipped).lower()}")
    print(f"candidate_importance={candidate_importance}")
    print(f"candidate_skip_reason={candidate_skip_reason}")
    print(f"fallback_candidates_seen={fallback_candidates_seen}")
    print(f"fallback_candidates_skipped_low_value={fallback_candidates_skipped_low_value}")
    print(f"fallback_publishable_candidates={fallback_publishable_candidates}")
    print(f"selected_candidate_id={selected_candidate_id}")
    print(f"selected_candidate_score={selected_candidate_score}")
    if not item:
        print("read_more_button_present=false")
        print("read_more_url_present=false")
        print("image_present=false")
        print("image_attach_attempted=false")
        print("importance_indicator=")
        print("post_length=0")
        print("post_was_trimmed=false")
        print("helper_cta_button_url_present=" + str(bool(get_seller_helper_url())).lower())
        print("send_status=skipped_no_candidate")
        return 0
    post, was_trimmed = safe_trim_post(build_seller_post(item), 1200)
    read_more = build_read_more_button(item)
    image_url = _pick_image_url(item)
    print(f"read_more_button_present={str(bool(read_more)).lower()}")
    print(f"read_more_url_present={str(bool(read_more.get('url') or item.get('link'))).lower()}")
    print(f"image_present={str(bool(image_url)).lower()}")
    print(f"image_attach_attempted={str(bool(image_url)).lower()}")
    print(f"importance_indicator={candidate_importance}")
    print(f"post_length={len(post)}")
    print(f"post_was_trimmed={str(was_trimmed).lower()}")
    print("---POST_PREVIEW_START---\n" + post + "\n---POST_PREVIEW_END---")
    print("helper_cta_preview_start\n" + build_seller_helper_cta_text() + "\nhelper_cta_preview_end")
    print(f"helper_cta_button_url_present={str(bool(get_seller_helper_url())).lower()}")
    if args.dry_run:
        print("send_status=dry_run")
        print("db_update_status=dry_run")
        print("helper_cta_status=dry_run")
        return 0
    token = os.getenv("MAX_BOT_TOKEN", "").strip(); channel_id = os.getenv("CHANNEL_ID", "").strip()
    kwargs = {}
    if read_more.get("type") == "callback":
        kwargs = {"add_full_article_button": True, "full_article_news_id": str(item.get("id"))}
    elif read_more.get("type") == "link":
        kwargs = {"button": read_more}
    if image_url:
        kwargs["image_url"] = image_url
    try:
        send_result = send_message(token, channel_id, post, **kwargs)
    except Exception:
        kwargs.pop("image_url", None)
        send_result = send_message(token, channel_id, post, **kwargs)
    cur = conn.cursor(); cur.execute("UPDATE news SET is_published=1, max_message_id=?, full_article_published_at=? WHERE id=?", (extract_message_id(send_result), datetime.now(timezone.utc).isoformat(), item["id"])); conn.commit()
    try:
        print(f"helper_cta_status={send_seller_helper_cta(token, channel_id)}")
    except Exception as e:
        print(f"helper_cta_status=error:{e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
