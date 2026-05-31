import re
from typing import Tuple


SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _normalize_spaces(text: str) -> str:
    text = str(text or "").replace("\xa0", " ")
    text = text.replace("…", ".")
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _norm_for_compare(text: str) -> str:
    text = _normalize_spaces(text).lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _split_sentences(text: str):
    text = _normalize_spaces(text)
    if not text:
        return []
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]


def _tokens(text: str):
    return [t for t in _norm_for_compare(text).split() if len(t) > 1]


def _is_duplicate_lead(title: str, first_sentence: str) -> bool:
    tt = _tokens(title)
    fs = _tokens(first_sentence)
    if len(tt) < 4 or len(fs) < 4:
        return False

    n = min(len(tt), len(fs), 12)
    overlap = sum(1 for i in range(n) if tt[i] == fs[i])
    if n >= 6 and overlap / n >= 0.75:
        return True

    t_head = " ".join(tt[:8])
    f_head = " ".join(fs[:8])
    return bool(t_head and (f_head.startswith(t_head) or t_head.startswith(f_head)))


def clean_digest_item_text(title: str, body: str) -> Tuple[str, str]:
    clean_title = _normalize_spaces(title)
    clean_body = _normalize_spaces(body)

    if not clean_body:
        return clean_title, clean_body

    sentences = _split_sentences(clean_body)
    if not sentences:
        return clean_title, clean_body

    first = sentences[0]

    # Безопасно удаляем только цельное первое предложение body, если оно дублирует title.
    if clean_title and _is_duplicate_lead(clean_title, first) and len(sentences) > 1:
        clean_body = " ".join(sentences[1:]).strip()

    return clean_title, clean_body
