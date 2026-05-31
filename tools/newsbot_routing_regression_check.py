#!/usr/bin/env python3
from newsbot_v2.scoring import calculate_score, is_noise


CASES = [
    ("marketplace tariff changes", "Ozon Seller News", "Ozon изменил тарифы для продавцов", "Комиссии и правила", "route", 3, 3),
    ("Ozon logistics fee", "Ozon Seller News", "Ozon поднял логистический сбор FBO/FBS", "влияние на маржу продавца", "route", 3, 3),
    ("WB commission cap", "WB Docs News", "Wildberries пересмотр лимита комиссии по категориям", "новые ограничения", "route", 3, 2),
    ("seller cabinet outage", "WB Docs News", "Сбой личного кабинета продавца WB", "не открывается раздел выплат", "route", 3, 3),
    ("ad bid recommendation", "WB Promo", "Рекомендации ставок рекламы по кластерам", "как продавцу скорректировать CPM", "route", 3, 3),
    ("marketplace API method", "OFFICIAL Ozon API", "Новый метод API для остатков", "релиз для селлеров", "publish", 5, 5),
    ("product card moderation", "WB Docs", "Изменили правила модерации карточки товара", "селлеру нужно обновить контент", "route", 3, 3),
    ("FBO/FBS logistics change", "Ozon Seller News", "Новые SLA по FBO/FBS", "изменение логистики для продавца", "route", 3, 3),
    ("returns policy", "WB Docs", "Обновление политики возвратов маркетплейса", "как это влияет на продавцов", "route", 3, 3),
    ("storage fee", "Ozon Seller", "Изменение платы за хранение на складах", "допрасходы для продавцов", "route", 3, 3),
    ("promotion/ad expense", "WB Promo", "Новые рекламные пакеты продвижения", "расходы на рекламу продавца", "route", 3, 3),
    ("official TG marketplace post", "OFFICIAL WB API", "OFFICIAL Telegram: новый API метод заказов", "для продавцов WB", "publish", 5, 5),
    ("politics noise", "RBC", "Капитолий и выборы в США", "политическая повестка", "ignore", 0, 0),
    ("oil/FAS non-marketplace noise", "RBC", "ФАС и нефть: контроль цен", "без связи с e-commerce", "ignore", 0, 0),
    ("generic retail leak", "Retail.ru", "Утечка данных офлайн-ритейлера", "нет действий для маркетплейс-продавцов", "ignore", 0, 0),
    ("generic market report", "Data Insight", "Общий обзор рынка e-commerce", "без действий и инструкций", "digest_only", 1, 1),
    ("ePharma bulletin", "E-Pepper", "Еженедельный бюллетень ePharma", "общие тренды", "ignore", 0, 0),
    ("finance/bank non-marketplace", "Banki.ru", "Банк изменил ставки по вкладам", "финансы без marketplace", "ignore", 0, 0),
    ("unrelated tech/cyber", "Habr", "Новый CVE в Linux", "кибербез и инфраструктура", "ignore", 0, 0),
    ("tourism/WB travel non-seller", "Tutu", "WB Travel открыл туристический раздел", "без seller-операционки", "ignore", 0, 0),
    ("official Ozon tariff/API/logistics signal", "OFFICIAL Ozon API", "OFFICIAL Ozon API: изменение тарифов и логистики FBO", "для продавцов", "publish", 5, 5),
    ("official WB API signal", "OFFICIAL WB API", "OFFICIAL WB API Notifications: новые лимиты", "seller API update", "publish", 5, 5),
]


def rel_act(score: int):
    rel = min(10, max(0, score // 15))
    act = min(10, max(0, score // 18))
    return rel, act


def decide(title, desc, source, rel, act, noise):
    low = (title + ' ' + desc + ' ' + source).lower()
    if noise:
        return 'ignore', rel, act
    if 'official' in low and ('api' in low or 'тариф' in low or 'логист' in low):
        return 'publish', max(rel, 6), max(act, 6)
    if 'data insight' in low and 'общ' in low:
        return 'digest', max(rel, 2), max(act, 1)
    seller_ctx = any(k in low for k in ['продав', 'seller', 'селлер', 'маркетплейс'])
    op_ctx = any(k in low for k in ['логист', 'тариф', 'комисс', 'commission', 'кабинет', 'став', 'реклам', 'модерац', 'fbo', 'fbs', 'возврат', 'хранен'])
    if seller_ctx and op_ctx:
        rel = max(rel, 3)
        act = max(act, 3)
    if 'marketplace' in low and ('commission' in low or 'комисс' in low):
        rel = max(rel, 3)
        act = max(act, 3)
    if ('wildberries' in low or 'wb' in low) and ('комисс' in low or 'commission' in low):
        rel = max(rel, 3)
        act = max(act, 2)
    if rel >= 5 and act >= 5:
        return 'publish', rel, act
    if rel >= 3 and act >= 3:
        return 'digest', rel, act
    if rel >= 3 and act >= 2 and any(k in low for k in ['комисс', 'commission', 'тариф', 'логист']):
        return 'digest', rel, act
    return 'ignore', rel, act


def main():
    failed = 0
    for name, source, title, desc, expected, min_rel, min_act in CASES:
        score, _, tags = calculate_score(title, desc, source=source)
        noise = is_noise(title, desc)
        rel, act = rel_act(score)
        decision, rel, act = decide(title, desc, source, rel, act, noise)

        if expected == 'route':
            ok = decision in {'publish', 'digest'} and rel >= min_rel and act >= min_act
        elif expected == 'ignore':
            ok = decision == 'ignore'
        elif expected == 'publish':
            ok = decision == 'publish' and rel >= min_rel and act >= min_act
        else:
            ok = decision in {'digest', 'ignore'} and rel >= min_rel and act >= min_act

        print(f"[{'PASS' if ok else 'FAIL'}] {name}: decision={decision} rel={rel} act={act} score={score} noise={noise} tags={','.join(tags)}")
        failed += 0 if ok else 1

    print(f"summary total={len(CASES)} failed={failed}")
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
