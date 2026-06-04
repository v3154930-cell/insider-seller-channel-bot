#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Редакторская очистка сценария аудиодайджеста перед TTS.

Что чистим:
- повторы одинаковых фраз;
- обрывки и недоговорённые предложения;
- мусорные фрагменты из сырого текста;
- эмодзи и спецсимволы, которые плохо звучат в TTS;
- слишком длинные предложения;
- фонетические подсказки для SaluteSpeech.
"""

import os
import re
import sys
from pathlib import Path


SCRIPTS_DIR = Path("/opt/newsbot_v2/audio_digest/scripts")


BAD_EXACT_PHRASES = {
    "Нет че.",
    "Нет че",
    "нет че.",
    "нет че",
}

BAD_ENDINGS = {
    "за", "и", "в", "во", "на", "по", "с", "со", "к", "ко",
    "от", "до", "для", "при", "без", "под", "над", "через",
    "или", "а", "но", "что", "как", "если",
}

EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002700-\U000027BF"
    "\U00002600-\U000026FF"
    "]+",
    flags=re.UNICODE,
)


AUDIO_SECTION_LABEL_RE = re.compile(
    r"^(Первая новость|Вторая новость|Третья новость|Четвёртая новость|Пятая новость|Ещё один сигнал|И коротко ещё|Следующий сигнал)\.?$",
    flags=re.IGNORECASE,
)


def is_audio_section_label(text: str) -> bool:
    return bool(AUDIO_SECTION_LABEL_RE.match((text or "").strip()))



def latest_script_path() -> Path:
    files = sorted(SCRIPTS_DIR.glob("audio_digest_script_*.txt"))
    if not files:
        raise SystemExit("ERROR: no audio_digest_script_*.txt files found")
    return files[-1]


def normalize_spaces(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    # Preserve intentional paragraph breaks for TTS pauses.
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def phonetic_prepare(text: str) -> str:
    # Уже используемые фонетические подсказки оставляем, но приводим частые варианты.
    replacements = [
        (r"\bИнсайдер Селлер\b", "Инсайдер СЭллер"),
        (r"\bSeller Helper\b", "СЭллер ХЭлпер"),
        (r"\bселлеры\b", "сЭллеры"),
        (r"\bселлеров\b", "сЭллеров"),
        (r"\bселлера\b", "сЭллера"),
        (r"\bселлер\b", "сЭллер"),
        (r"\bмаркетплейсов\b", "маркетплэйсов"),
        (r"\bмаркетплейсами\b", "маркетплэйсами"),
        (r"\bмаркетплейсы\b", "маркетплэйсы"),
        (r"\bмаркетплейс\b", "маркетплэйс"),
        (r"\bFBS\b", "эф-би-эс"),
        (r"\bFBO\b", "эф-би-о"),
        (r"\bFBY\b", "эф-би-вай"),
        (r"\bDBS\b", "ди-би-эс"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text


def sentence_split(text: str):
    # Разбиваем аккуратно по концу предложения.
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]


def is_bad_sentence(sentence: str) -> bool:
    s = sentence.strip()
    if not s:
        return True

    if is_audio_section_label(s):
        return False

    if s in BAD_EXACT_PHRASES:
        return True

    # Убираем одиночные мусорные короткие фразы.
    clean = re.sub(r"[^А-Яа-яA-Za-z0-9%₽ёЁ\- ]+", "", s).strip()
    words = clean.split()

    if len(words) <= 2 and len(clean) < 14:
        return True

    # Недоговорённые фразы, заканчивающиеся на предлог/союз.
    last = words[-1].lower().replace("ё", "е") if words else ""
    if last in BAD_ENDINGS:
        return True

    # Фразы, которые явно обрезались после чисел/предлогов.
    if re.search(r"(₽|руб\.?|процент|литр|за)\s*\.?$", s, flags=re.IGNORECASE):
        # "14 ₽ за." точно плохо, но нормальная сумма "201 ₽." тоже может быть нормальной.
        if re.search(r"\bза\s*\.?$", s, flags=re.IGNORECASE):
            return True

    # Слишком короткий обрывок без смысла.
    if len(words) < 4 and not re.search(r"\d|Ozon|Вайлдберриз|Wildberries|Яндекс|МАКС", s, flags=re.IGNORECASE):
        return True

    return False


def dedupe_sentences(sentences):
    result = []
    seen = set()

    # Эту фразу не даём повторять много раз подряд в одном выпуске.
    repeated_editorial_phrase = "главный вопрос для"

    editorial_phrase_used = False

    for s in sentences:
        key = re.sub(r"\s+", " ", s.lower().replace("ё", "е")).strip()

        if key in seen:
            continue

        if repeated_editorial_phrase in key:
            if editorial_phrase_used:
                continue
            editorial_phrase_used = True

        seen.add(key)
        result.append(s)

    return result



def fix_audio_repetitions(text: str) -> str:
    text = text or ""

    # Fix broken years like "2. 025".
    text = re.sub(r"\b([12])\.\s*(\d{3})\b", r"\1\2", text)

    # Fix broken word fragments.
    text = re.sub(r"\bт\.\s*овар\b", "товар", text, flags=re.IGNORECASE)

    # Remove exact repeated sentence-like chunks.
    text = re.sub(
        r"(\b[^.!?\n]{18,180}?[.!?])\s+\1",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )

    # Remove repeated opening phrase in logistics/tariff blocks.
    text = re.sub(
        r"\b(По\s+подготовке\s+товара\s+к\s+вывозу[^.!?\n]{0,90}[.!?,])\s*По\s+подготовке\s+товара\s+к\s+вывозу",
        r"\1",
        text,
        flags=re.IGNORECASE,
    )

    # Remove neighbouring duplicated words.
    text = re.sub(r"\b([А-Яа-яA-Za-zЁё]{4,})\s+\1\b", r"\1", text, flags=re.IGNORECASE)

    # Common glued fragments from marketplace/RSS texts.
    text = re.sub(r"\bRВайлдберриз\b", "Рэ-вэ-бэ", text)
    text = re.sub(r"\bRWB\b", "Рэ-вэ-бэ", text, flags=re.IGNORECASE)
    text = re.sub(r"(сэллере)\s+(Подписчик)", r"\1. \2", text, flags=re.IGNORECASE)
    text = re.sub(r"(считать)\s+(Замгендира)", r"\1. \2", text, flags=re.IGNORECASE)
    text = re.sub(r"(ответственность\s+[—-]\s+на\s+сэллере)\s+(Подписчик)", r"\1. \2", text, flags=re.IGNORECASE)

    # Clean ugly punctuation.
    text = re.sub(r",\s*\.", ".", text)
    text = re.sub(r"\.\s*,", ".", text)
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)

    return text


def clean_text(text: str) -> str:
    text = normalize_spaces(text)
    text = fix_audio_repetitions(text)
    text = EMOJI_RE.sub("", text)

    # Убираем декоративные маркеры, которые в аудио не нужны.
    text = text.replace("🔘", "")
    text = text.replace("🛒", "")
    text = text.replace("—", " — ")

    text = normalize_spaces(text)
    text = phonetic_prepare(text)

    sentences = sentence_split(text)
    sentences = [s for s in sentences if not is_bad_sentence(s)]
    sentences = dedupe_sentences(sentences)

    # Keep soft paragraph breaks for TTS instead of one breathless wall of text.
    cleaned_parts = []
    for sent in sentences:
        cleaned_parts.append(sent)
        if re.search(r"^(Первая новость|Вторая новость|Третья новость|Ещё один сигнал|И коротко ещё|Подробности|На сегодня|Дайджест|Финиш|Итоги)", sent, flags=re.IGNORECASE):
            cleaned_parts.append("\n\n")
        elif re.search(r"(Вывод простой|Для селлера|Главное|Это скорее рыночный сигнал)", sent, flags=re.IGNORECASE):
            cleaned_parts.append("\n\n")
        else:
            cleaned_parts.append(" ")

    cleaned = "".join(cleaned_parts)
    cleaned = normalize_spaces(cleaned)

    # Финальная редакторская полировка склеек после RSS/TG-текста:
    # "BusinessLamoda", "товара Озон проводит", "товара Вайлдберриз сообщил".
    glue_fixes = [
        (r"(Business)(Lamoda)", r"\1. \2"),
        (r"(товара)\s+(Озон\s+проводит)", r"\1. \2"),
        (r"(товара)\s+(Озон\s+тестирует)", r"\1. \2"),
        (r"(товара)\s+(Вайлдберриз\s+сообщил)", r"\1. \2"),
        (r"(склейке)\s+(Для\s+сЭллера)", r"\1. \2"),
        (r"(конверсии)\s+(Озон\s+тестирует)", r"\1. \2"),
    ]

    for pattern, repl in glue_fixes:
        cleaned = re.sub(pattern, repl, cleaned)


    # Audio boundary fixes: title/body often come glued from TG/RSS.
    cleaned = re.sub(r"(прямых продажах)\s+(Нагрузка)", r"\1. \2", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(через «Госуслуги»)\s+(Роспотребнадзор)", r"\1. \2", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(год назад)\s+(Схемы)", r"\1. \2", cleaned, flags=re.IGNORECASE)

    # Финальная подчистка двойных пробелов вокруг тире.
    cleaned = re.sub(r"\s+—\s+", " — ", cleaned)


    # Final audio wording polish.
    cleaned = re.sub(r"\bканал прода\b", "канал продаж", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\.\s*как привлекать трафик на сайт так, чтобы это было окупаемо\?",
        ".\n\nГлавный вопрос — как привлекать трафик на сайт так, чтобы это было окупаемо.",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"Если упростить, обычно всё сводится к двум направлениям:\s*—\s*органика\s*\(SEO и контент, чтобы находили через поиск и соцсети\)\s*—\s*платный трафик\s*\(контекст и реклама для быстрых тестов и первых продаж\)\.",
        "Если упростить, есть два пути: органика для долгой игры и платный трафик для быстрых тестов.",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Restore TTS-friendly pauses. Do this after other glue fixes.
    cleaned = re.sub(r"\s+(Первая новость\.)", r"\n\n\1", cleaned)
    cleaned = re.sub(r"\s+(Вторая новость\.)", r"\n\n\1", cleaned)
    cleaned = re.sub(r"\s+(Третья новость\.)", r"\n\n\1", cleaned)
    cleaned = re.sub(r"\s+(Четвёртая новость\.)", r"\n\n\1", cleaned)
    cleaned = re.sub(r"\s+(Пятая новость\.)", r"\n\n\1", cleaned)
    cleaned = re.sub(r"\s+(Ещё один сигнал\.)", r"\n\n\1", cleaned)
    cleaned = re.sub(r"\s+(И коротко ещё\.)", r"\n\n\1", cleaned)
    cleaned = re.sub(r"\s+(Подробности —)", r"\n\n\1", cleaned)
    cleaned = re.sub(r"\s+(Вывод простой:)", r"\n\n\1", cleaned)
    cleaned = re.sub(r"\s+(Для селлера)", r"\n\n\1", cleaned)
    cleaned = re.sub(r"\s+(Главное —)", r"\n\n\1", cleaned)

    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()

    cleaned = fix_audio_repetitions(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()

    return cleaned


def main():
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = latest_script_path()

    if not path.exists():
        raise SystemExit(f"ERROR: script file not found: {path}")

    original = path.read_text(encoding="utf-8", errors="ignore")
    cleaned = clean_text(original)

    # Short but valid evening digests are allowed.
    # Some days have no strong news/signals, and the script can be concise.
    # We still keep a hard safety floor to avoid overwriting with broken/empty text.
    min_clean_chars = int(os.getenv("AUDIO_DIGEST_MIN_CLEAN_CHARS", "180") or "180")
    if len(cleaned) < min_clean_chars:
        raise SystemExit(
            f"ERROR: cleaned text is too short ({len(cleaned)} chars < {min_clean_chars}); refusing to overwrite"
        )

    if len(cleaned) < 300:
        print(f"WARNING: cleaned text is short but accepted: {len(cleaned)} chars")

    backup = path.with_suffix(path.suffix + ".before_cleaner")
    backup.write_text(original, encoding="utf-8")

    path.write_text(cleaned + "\n", encoding="utf-8")

    print("OK: audio script cleaned")
    print("path:", path)
    print("backup:", backup)
    print("chars_before:", len(original))
    print("chars_after:", len(cleaned))
    print()
    print(cleaned[:1500])


if __name__ == "__main__":
    main()
