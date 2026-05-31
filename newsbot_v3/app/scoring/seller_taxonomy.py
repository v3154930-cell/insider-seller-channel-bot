from __future__ import annotations


def classify_seller_topic(title: str, text: str, source: str | None = None, marketplace: str | None = None) -> list[str]:
    merged = " ".join([title or "", text or "", source or "", marketplace or ""]).lower()
    tags: list[str] = []

    def hit(*tokens: str) -> bool:
        return any(t in merged for t in tokens)

    if hit("комис", "тариф", "эквайринг комиссия", "fee"):
        tags.append("commission_tariff")
    if hit("логист", "хранен", "fbo", "fbs", "достав", "возврат"):
        tags.append("logistics_storage")
    if hit("возврат", "спор", "претензи"):
        tags.append("returns_disputes")
    if hit("сертифик", "декларац", "документ", "разрешитель"):
        tags.append("documents_certification")
    if hit("честный знак", "маркиров", "км", "datamatrix"):
        tags.append("marking_chestny_znak")
    if hit("фнс", "ндс", "усн", "налог", "регулятор", "закон", "постановлен"):
        tags.append("legal_tax_regulatory")
    if hit("закон о платформ", "маркетплейс закон", "platform law"):
        tags.append("platform_law")
    if hit("api", "личный кабинет", "кабинет продавца", "оферта", "процесс"):
        tags.append("api_cabinet")
    if hit("карточк", "контент", "seo", "описани", "медиа"):
        tags.append("cards_content")
    if hit("реклама", "продвижен", "ставк", "bid", "cpc"):
        tags.append("ads_promotion")
    if hit("выплат", "расчет", "платеж", "удержан", "компенсац"):
        tags.append("finance_payments")
    if hit("банк", "кредит", "факторинг", "овердрафт", "финтех", "расчетный счет"):
        tags.append("marketplace_banking_fintech")
    if hit("аналит", "исследован", "тренд", "динамик рынка"):
        tags.append("analytics_market")
    if hit("доля", "пакет акций", "приобрет", "партнерств", "интервью", "стратег"):
        tags.append("corporate_pr")

    if not tags:
        tags.append("low_value_background")

    if "corporate_pr" in tags and len(tags) == 1:
        tags.append("low_value_background")
    return list(dict.fromkeys(tags))
