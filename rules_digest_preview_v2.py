from db import init_db, _fetch_all


def marketplace_label(value, signal_level=None):
    if signal_level == "regulatory_signal" and (not value or value == "unknown"):
        return "Все маркетплейсы / требуется проверка"

    return {
        "ozon": "Ozon",
        "wildberries": "Wildberries",
        "yandex_market": "Яндекс Маркет",
        "multiple": "Несколько площадок",
        "unknown": "Площадка не определена",
    }.get(value or "unknown", value or "Площадка не определена")


def level_label(value):
    return {
        "rule_change": "изменение правил / условий",
        "regulatory_signal": "регуляторный сигнал",
        "business_signal": "бизнес-сигнал",
    }.get(value or "unknown", value or "unknown")


def short_text(text, limit=260):
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def action_hint(signal_level, signal_type, title):
    text = (title or "").lower()

    if "фас" in text and "выплат" in text:
        return "Проверить сроки выплат, уведомления площадок и договорные условия."

    if "платформенной экономике" in text:
        return "Проверить, какие обязанности платформ могут измениться после вступления закона в силу."

    if "платёжных документов" in text or "платежных документов" in text:
        return "Проверить требования к платёжным документам и бухгалтерскому оформлению."

    if "брошенн" in text and "корзин" in text:
        return "Проверить стоимость инструмента, условия подключения и влияние на рекламный бюджет."

    if "товарный знак" in text or "бейдж" in text or "оригинал" in text:
        return "Проверить документы на бренд, товарный знак и требования к подтверждению оригинальности."

    if "витрин" in text:
        return "Проверить тарифы витрины магазина и пересчитать окупаемость платной опции."

    if "не требует проверки" in text:
        return "Проверить правила возвратов, компенсаций, проверок и спорных удержаний."

    if signal_type == "tariffs_fees":
        return "Проверить тарифы, платные опции и влияние на маржинальность."

    if signal_type == "payments":
        return "Проверить сроки выплат, удержания и порядок расчётов."

    if signal_type == "penalties_returns":
        return "Проверить правила возвратов, компенсаций, проверок и спорных удержаний."

    return "Проверить официальный документ или кабинет продавца перед применением."


def print_item(index, row, confirmed=False):
    (
        marketplace,
        signal_level,
        signal_type,
        confidence,
        title,
        source,
        link,
        confirmation_level,
        match_score,
        matched_document,
        effective_date,
    ) = row

    print(f"{index}. {marketplace_label(marketplace, signal_level)} — {level_label(signal_level)}")
    print(f"   Тема: {short_text(title)}")

    if confirmed:
        print(f"   Статус: подтверждено документами")
        print(f"   Совпадение: {match_score}")
        print(f"   Документ: {short_text(matched_document, 320)}")
        if effective_date:
            print(f"   Дата действия: {effective_date}")
    else:
        print(f"   Статус: сигнал есть, подтверждение в документах не найдено")
        print(f"   Совпадение: {match_score or 0}")

    print(f"   Тип: {signal_type}, уверенность сигнала: {confidence}")
    print(f"   Что проверить: {action_hint(signal_level, signal_type, title)}")
    print(f"   Источник: {source}")
    print(f"   Ссылка: {link}")
    print()


def main():
    init_db()

    rows = _fetch_all("""
        SELECT
            rs.marketplace,
            rs.signal_level,
            rs.signal_type,
            rs.confidence,
            rs.title,
            rs.source,
            rs.link,
            COALESCE(rc.confirmation_level, 'not_checked') AS confirmation_level,
            COALESCE(rc.match_score, 0) AS match_score,
            rc.matched_document,
            rc.effective_date
        FROM rules_signals rs
        LEFT JOIN rules_checks rc ON rc.signal_id = rs.id
        WHERE rs.is_digest_candidate = 1
        ORDER BY
            CASE COALESCE(rc.confirmation_level, 'not_checked')
                WHEN 'confirmed_by_docs' THEN 1
                ELSE 2
            END,
            rs.confidence DESC,
            rs.id DESC
        LIMIT 20
    """)

    print("⚖️ Мониторинг условий маркетплейсов")
    print()

    if not rows:
        print("За сегодня значимых сигналов об изменении условий Ozon, Wildberries и Яндекс Маркета не обнаружено.")
        print()
        print("Проверены Telegram-источники, новости и документная база.")
        return

    confirmed = [r for r in rows if r[7] == "confirmed_by_docs"]
    signal_only = [r for r in rows if r[7] != "confirmed_by_docs"]

    print(f"Всего сигналов для проверки: {len(rows)}")
    print(f"Подтверждено документами: {len(confirmed)}")
    print(f"Без подтверждения в документах: {len(signal_only)}")
    print()
    print("Важно: confirmed_by_docs означает, что бот нашёл сильное совпадение в загруженной документной базе. signal_only означает, что сигнал найден в новостях/Telegram, но точного подтверждения в документах пока нет.")
    print()

    if confirmed:
        print("✅ Подтверждено документами")
        print()
        for i, row in enumerate(confirmed, start=1):
            print_item(i, row, confirmed=True)

    if signal_only:
        print("⚠️ Есть сигнал, но подтверждение в документах не найдено")
        print()
        for i, row in enumerate(signal_only, start=1):
            print_item(i, row, confirmed=False)

    print("Следующий шаг: для signal_only догрузить недостающие документы или оставить сигнал как неподтверждённый до появления официального подтверждения.")


if __name__ == "__main__":
    main()
