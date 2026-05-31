#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from digest_text_cleaner import clean_digest_item_text
from audio_digest_story_builder import (
    build_human_audio_digest,
    final_voice_cleanup,
    AUDIO_CLOSING_LINE,
    SOFT_AUDIO_JOKES_NO_NEWS,
)

import types
sys.modules.setdefault("libsql", types.SimpleNamespace(connect=lambda *a, **k: None))
from digest_v2 import format_item_line


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)


def test_title_body_duplicated():
    title = "Ozon сам говорит, что отзывы — решающий фактор"
    body = "Ozon сам говорит, что отзывы — решающий фактор при покупке онлайн. Для половины пользователей рейтинг важен."
    _, cleaned = clean_digest_item_text(title, body)
    check(cleaned.count("Ozon сам говорит") == 0, "duplicate lead not removed")
    check("Для половины пользователей" in cleaned, "important second sentence lost")


def test_truncated_title():
    title = "Ozon сам говорит, что отзывы - решающие факторы при онлайн-покупке Ozon опросил больше тысячи покупателей..."
    body = "Ozon сам говорит, что отзывы - решающие факторы при онлайн-покупке. Для половины пользователей рейтинг важен. Для селлера это важный сигнал."
    _, cleaned = clean_digest_item_text(title, body)
    check("айн-покупке" not in cleaned, "broken word fragment appeared")
    check("Для половины пользователей" in cleaned, "middle sentence dropped")
    check("Для селлера" in cleaned, "seller sentence dropped")


def test_audio_human_format():
    news = [
        {"title": "На маркетплейсах инфляция ниже", "body": "На маркетплейсах инфляция ниже. Для селлера это сигнал.", "source": "s1", "link": "https://example.com/1"},
        {"title": "Отзывы и рейтинг влияют на вид товара", "body": "Отзывы и рейтинг влияют на вид товара. Для селлера важно проверить карточки.", "source": "s2", "link": "https://example.com/2"},
        {"title": "ФАС выдала предупреждение площадкам", "body": "ФАС выдала предупреждение площадкам. Для селлера это регуляторный сигнал.", "source": "s3", "link": "https://example.com/3"},
    ]
    raw_text = build_human_audio_digest(news, digest_date="2026-05-25")
    text = final_voice_cleanup(raw_text)
    check("Коротко по новостям, на которые стоит обратить внимание за" in raw_text, "new intro missing")
    check("маркетплэйсам" not in raw_text.lower(), "old awkward intro wording remains")
    check("Первое." not in text and "Второе." not in text and "Третье." not in text, "audio numbering leaked")
    check(not re.search(r"\n\n[^\n]+\n[^\n]+", text), "title duplicated as standalone line before body")
    check("\n\n" in raw_text or "..." in raw_text, "no pauses between news")
    check(AUDIO_CLOSING_LINE in raw_text, "missing mandatory closing line")
    check("Удивительно, но нет." in text or "не скучали." in text or "ожидали." in text, "soft joke missing")
    check("http://" not in text and "https://" not in text, "links leaked to audio")
    check("Источник:" not in text, "source markers leaked to audio")
    check("t.me/" not in text, "telegram links leaked to audio")
    check("Seller Helper" not in text and "СЭллер ХЭлпер" not in text, "cta leaked to audio")
    check("Проверить комиссию" not in text and "Рассчитать комиссии" not in text, "helper cta leaked to audio")
    check("Если у вас плохо прогружаются файлы" not in text, "bad phrase remains")
    check("все посты также доступны в MAX" not in text, "max phrase remains")
    blocks = [b.strip() for b in raw_text.split("\n\n") if b.strip()]
    item_blocks = blocks[1:1 + len(news)]
    for block in item_blocks:
        check(len(block) <= 420, "audio item too long")


def test_audio_no_news_format():
    raw_text = build_human_audio_digest([], digest_date="2026-05-25")
    text = final_voice_cleanup(raw_text)
    check("Коротко по новостям, на которые стоит обратить внимание за" in raw_text, "new intro missing in no-news case")
    check("Значимых новостей на сегодня нет." in raw_text, "no-news phrase missing")
    check(AUDIO_CLOSING_LINE not in raw_text, "closing line must be absent with no news")
    check("опять что-то поменяли" not in text, "contradictory no-news joke leaked")
    check("маркетплэйсы" not in text.lower(), "wrong spelling leaked")
    check(any(joke in raw_text for joke in SOFT_AUDIO_JOKES_NO_NEWS), "no-news soft joke missing")
    check("Первое." not in text and "Второе." not in text and "Третье." not in text, "audio numbering leaked in no-news case")
    check("http://" not in text and "https://" not in text and "t.me/" not in text, "links leaked in no-news case")
    check("Источник:" not in text, "source leaked in no-news case")


def test_text_digest_numbering():
    item = {
        "source": "Oborot",
        "title": "Ozon сам говорит, что отзывы — решающий фактор",
        "raw_text": "Ozon сам говорит, что отзывы — решающий фактор при покупке онлайн. Для половины пользователей рейтинг важен.",
        "link": "https://example.com",
    }
    line = format_item_line(item, 1)
    check(line.startswith("1."), "text numbering missing")
    check("Источник:" in line and "Ссылка:" in line, "source/link missing in text digest")
    check(line.count("Ozon сам говорит") == 1, "title/body duplicate not removed in text digest")


if __name__ == "__main__":
    test_title_body_duplicated()
    test_truncated_title()
    test_audio_human_format()
    test_audio_no_news_format()
    test_text_digest_numbering()
    print("OK: digest quality regression checks passed")
