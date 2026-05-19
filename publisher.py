import logging
import re
import html
import os
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import requests

logger = logging.getLogger(__name__)


def normalize_channel_id(channel_id):
    if channel_id is None:
        return ""
    return str(channel_id).strip()


def save_link(url, title=None):
    return url


def append_source_line(text, item_or_source=None, url=None):
    text = text or ""

    source = ""
    link = ""

    if isinstance(item_or_source, dict):
        source = item_or_source.get("source") or item_or_source.get("marketplace") or ""
        link = item_or_source.get("url") or item_or_source.get("link") or ""
    else:
        source = item_or_source or ""
        link = url or ""

    source = str(source or "").strip()
    link = str(link or "").strip()

    if not source and not link:
        return text

    lines = []
    if source:
        lines.append(f"Источник: {source}")
    if link:
        lines.append(link)

    return text.rstrip() + "\n\n" + "\n".join(lines)



def clean_url(url: str) -> str:
    url = str(url or "").strip()
    if not url:
        return url

    try:
        parts = urlsplit(url)
        query = [
            (k, v)
            for k, v in parse_qsl(parts.query, keep_blank_values=True)
            if not k.lower().startswith("utm_")
        ]
        return urlunsplit((
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment
        ))
    except Exception:
        return url



def remove_foreign_source_boilerplate(text: str) -> str:
    """
    Удаляет чужие рекламные хвосты источников:
    email-рассылки, MAX/VK-каналы, призывы читать сайт источника.
    Наши строки "Источник:" и "Ссылка:" не трогаем — они добавляются отдельно.
    """
    if not text:
        return ""

    s = str(text)

    # 1. Жёстко режем типовой хвост Oborot.ru от первой фразы до конца.
    tail_markers = [
        r"Если\s+Telegram\s+у\s+вас\s+работает\s+не\s+идеально",
        r"Подпишитесь\s+на\s+нашу\s+email[\-\s]*рассылку",
        r"Подпишитесь\s+на\s+наш\s+канал\s+в\s+MAX",
        r"Читайте\s+нас\s+в\s+VK",
        r"Ну\s+и\s+не\s+забывайте\s+про\s+наш\s+сайт\s+Oborot\.ru",
    ]

    for marker in tail_markers:
        m = re.search(marker, s, flags=re.I | re.U)
        if m:
            # Если рекламный блок начинается ближе ко второй половине текста,
            # считаем это хвостом и отрезаем всё после него.
            if m.start() > max(0, len(s) * 0.35):
                s = s[:m.start()].rstrip()
                break

    # 2. Дополнительно убираем отдельные строки/куски, если хвост пришёл не целиком.
    line_patterns = [
        r"^\s*[📩📲🪪]?\s*Подпишитесь\s+на\s+нашу\s+email[\-\s]*рассылку.*$",
        r"^\s*[📩📲🪪]?\s*Подпишитесь\s+на\s+наш\s+канал\s+в\s+MAX.*$",
        r"^\s*[📩📲🪪]?\s*Читайте\s+нас\s+в\s+VK.*$",
        r"^\s*Ну\s+и\s+не\s+забывайте\s+про\s+наш\s+сайт\s+Oborot\.ru.*$",
        r"^\s*Если\s+Telegram\s+у\s+вас\s+работает\s+не\s+идеально.*$",
    ]

    lines = []
    for line in s.splitlines():
        clean_line = line.strip()
        if not clean_line:
            lines.append(line)
            continue

        if any(re.search(pattern, clean_line, flags=re.I | re.U) for pattern in line_patterns):
            continue

        lines.append(line)

    s = "\n".join(lines)

    # 3. Убираем рекламные блоки, если они пришли одной строкой.
    inline_patterns = [
        r"\s*[📩📲🪪]?\s*Подпишитесь\s+на\s+нашу\s+email[\-\s]*рассылку\s*",
        r"\s*[📩📲🪪]?\s*Подпишитесь\s+на\s+наш\s+канал\s+в\s+MAX\s*",
        r"\s*[📩📲🪪]?\s*Читайте\s+нас\s+в\s+VK\s*",
        r"\s*Ну\s+и\s+не\s+забывайте\s+про\s+наш\s+сайт\s+Oborot\.ru\s*",
    ]

    for pattern in inline_patterns:
        s = re.sub(pattern, " ", s, flags=re.I | re.U)

    # 4. Чистим лишние пробелы и пустые строки.
    s = re.sub(r"[ \t]{2,}", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)

    return s.strip()

def clean_outgoing_text(text: str) -> str:
    text = remove_foreign_source_boilerplate(text)
    text = html.unescape(text or "")

    # Гарантируем жирное выделение ключевых строк для MAX HTML.
    lines = text.splitlines()
    non_empty = [i for i, line in enumerate(lines) if line.strip()]

    if non_empty:
        first_i = non_empty[0]
        first = lines[first_i].strip()

        # Источник канала: TG:crmmarketplace -> <b>📦 TG:crmmarketplace</b>
        if first.startswith("TG:") or first.startswith("📦 TG:"):
            clean_source = first.replace("📦 ", "", 1)
            if not clean_source.lower().startswith("<b>"):
                lines[first_i] = f"<b>📦 {clean_source}</b>"

            # Следующая непустая строка после TG — заголовок.
            for idx in non_empty[1:]:
                title = lines[idx].strip()
                if (
                    title
                    and not title.lower().startswith("<b>")
                    and not title.startswith("http://")
                    and not title.startswith("https://")
                    and not title.startswith("Источник:")
                    and "Что это значит для селлера" not in title
                ):
                    lines[idx] = f"<b>{title}</b>"
                    break

    text = "\n".join(lines)

    # Жирним только подпись, сам вывод после двоеточия остается обычным.
    text = re.sub(
        r"(?:<b>)?\s*🎯\s*Что это значит для селлера:\s*(?:</b>)?",
        "<b>🎯 Что это значит для селлера:</b> ",
        text,
        flags=re.IGNORECASE
    )

    # MAX понимает HTML, поэтому сохраняем только безопасные теги жирного.
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)

    text = re.sub(r"<\s*(b|strong)\s*>", "___B_OPEN___", text, flags=re.IGNORECASE)
    text = re.sub(r"<\s*/\s*(b|strong)\s*>", "___B_CLOSE___", text, flags=re.IGNORECASE)

    # Остальные HTML-теги убираем, чтобы не ломать отправку.
    text = re.sub(r"<[^>]+>", "", text)

    text = text.replace("___B_OPEN___", "<b>")
    text = text.replace("___B_CLOSE___", "</b>")

    # Чистим ссылки от utm-меток.
    def repl(match):
        return clean_url(match.group(0))

    text = re.sub(r"https?://\S+", repl, text)

    # Убираем лишние пробелы перед переносами и слишком много пустых строк.
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)

    return text.strip()

def send_message(token, channel_id, text, add_helper_button=False, full_article_news_id=None, add_full_article_button=False):
    token = str(token or "").strip()
    channel_id = normalize_channel_id(channel_id)
    text = text or ""

    if not token:
        raise RuntimeError("MAX_BOT_TOKEN is empty")

    if not channel_id:
        raise RuntimeError("CHANNEL_ID is empty")

    try:
        chat_id_value = int(channel_id)
    except Exception:
        chat_id_value = channel_id

    url = "https://platform-api.max.ru/messages"

    headers = {
        "Authorization": token,
        "Content-Type": "application/json"
    }

    params = {
        "chat_id": chat_id_value
    }

    text = clean_outgoing_text(text)

    payload = {
        "text": text,
        "format": "html"
    }

    buttons = []

    if add_full_article_button and full_article_news_id:
        buttons.append([
            {
                "type": "callback",
                "text": "📖 Читать полностью",
                "payload": f"full_article:{full_article_news_id}"
            }
        ])

    helper_bot_url = os.getenv("SELLER_HELPER_BOT_URL", "").strip()
    if add_helper_button and helper_bot_url:
        buttons.append([
            {
                "type": "link",
                "text": "📊 Рассчитать комиссии и маржу",
                "url": helper_bot_url
            }
        ])

    if buttons:
        payload["attachments"] = [
            {
                "type": "inline_keyboard",
                "payload": {
                    "buttons": buttons
                }
            }
        ]

    resp = requests.post(
        url,
        params=params,
        json=payload,
        headers=headers,
        timeout=30
    )

    if resp.status_code >= 400:
        raise RuntimeError(
            f"MAX send_message failed: HTTP {resp.status_code}: {resp.text[:1000]}"
        )

    logger.info("MAX message sent. channel_id=%s", channel_id)
    try:
        return resp.json()
    except Exception:
        return {"ok": True, "raw_text": resp.text}


def has_full_article(item):
    """
    True, если у новости есть текст, который можно раскрыть кнопкой
    "📖 Читать полностью".

    Важно: эта функция меняет только условие показа кнопки.
    MAX API, callback-worker, PUT /messages и CTA Seller Helper не трогаются.
    """
    if not isinstance(item, dict):
        return False

    raw = (
        item.get("raw_text")
        or item.get("full_text_clean")
        or item.get("full_text_raw")
        or ""
    )

    raw = str(raw).replace("\r", "\n").strip()
    raw_clean = " ".join(raw.split())

    if not raw_clean:
        return False

    # Короткие обрывки не раскрываем отдельной кнопкой.
    if len(raw_clean) < 300:
        return False

    return True



def send_seller_helper_cta(token, channel_id):
    """
    Sends one Seller Helper CTA after a publisher batch.
    Must be called only once after all news in the run are posted.
    """
    if os.getenv("ENABLE_SELLER_HELPER_CTA", "true").lower() not in ("1", "true", "yes", "on"):
        logger.info("Seller Helper CTA disabled by env")
        return False

    helper_bot_url = os.getenv("SELLER_HELPER_BOT_URL", "").strip()

    text = (
        "🧮 <b>Проверить комиссию и прибыль</b>\n\n"
        "Хотите понять, как комиссия, тариф и налог влияют на прибыль товара?\n\n"
        "Откройте Seller Helper и напишите:\n"
        "• WB ботинки\n"
        "• Ozon чайник\n"
        "• Яндекс косметика\n\n"
        "Сейчас идёт тестирование и предпродакшен — сравнение площадок пока доступно бесплатно."
    )

    try:
        return send_message(
            token,
            channel_id,
            text,
            add_helper_button=bool(helper_bot_url)
        )
    except Exception as e:
        logger.warning("Seller Helper CTA send failed: %s", e)
        return False
