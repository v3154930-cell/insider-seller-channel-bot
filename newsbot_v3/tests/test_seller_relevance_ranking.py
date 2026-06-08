from app.publisher.candidate_normalizer import normalize_v2_row_to_candidate
from app.publisher.selection_policy import dry_run_selection
from app.scoring.seller_actionability import (
    is_direct_seller_action,
    is_macro_corporate_noise,
    score_seller_actionability,
)


def _row(news_id: int, title: str, text: str, source: str = "TG:mpgo_ru") -> dict:
    return {
        "id": news_id,
        "v2_news_id": news_id,
        "title": title,
        "text": text,
        "source": source,
        "link": f"https://example.com/{news_id}",
        # Simulate generous legacy V2 scoring: deterministic V3 scoring should still reorder.
        "seller_relevance_score": 7,
        "actionability_score": 7,
    }


def _candidate(news_id: int, title: str, text: str, source: str = "TG:mpgo_ru") -> dict:
    return normalize_v2_row_to_candidate(_row(news_id, title, text, source))


def _select_id(candidates: list[dict]) -> str | None:
    result = dry_run_selection(candidates, published_today=0)
    return result["selected_candidate_id"]


def test_wb_packaging_penalties_outrank_amazon_investment() -> None:
    packaging = _candidate(
        147113,
        "Wildberries расширил штрафы за неправильную упаковку товаров",
        "Для продавцов WB меняются требования к упаковке: штрафы применяются на складах и по категориям, нужно проверить поставки.",
        "WB official seller news",
    )
    amazon = _candidate(
        152004,
        "Amazon инвестирует 10 млрд евро в роботов и логистику",
        "Иностранный маркетплейс развивает склады и роботизацию в Европе, прямых правил или тарифов для российских продавцов нет.",
        "Retail media",
    )

    assert packaging["score"] > amazon["score"]
    assert packaging["direct_action"] is True
    assert amazon["direct_action"] is False
    assert _select_id([amazon, packaging]) == "candidate-v2-147113"


def test_ozon_contract_change_outranks_sber_stake_rumor() -> None:
    contract = _candidate(
        136231,
        "Ozon меняет договор с продавцами с 18 июня",
        "В оферте Ozon меняются правила удаления отзывов и работы продавцов, нужно проверить договор и процессы в кабинете.",
        "Ozon official seller news",
    )
    rumor = _candidate(
        135007,
        "Греф заявил, что Сбер не планирует покупать долю в Ozon или Wildberries",
        "Это акционерный и банковский слух без изменения тарифов, выплат, правил кабинета или ответственности продавцов.",
        "Business media",
    )

    assert contract["score"] > rumor["score"]
    assert is_macro_corporate_noise(rumor["title"], rumor["item"].text, rumor["source"])
    assert _select_id([rumor, contract]) == "candidate-v2-136231"


def test_yandex_returns_compensation_outranks_data_insight_ranking() -> None:
    compensation = _candidate(
        120324,
        "Яндекс Маркет вводит частичную компенсацию за бракованные возвраты",
        "Продавцам нужно проверить правила возвратов, компенсации и влияние на маржу по заказам.",
        "Yandex Market official seller news",
    )
    ranking = _candidate(
        151333,
        "Wildberries, Ozon и Яндекс Маркет остались лидерами рейтинга Data Insight",
        "Исследование рынка показывает лидеров маркетплейсов, но не содержит новых тарифов, сроков или правил для продавцов.",
        "Data Insight",
    )

    assert compensation["score"] > ranking["score"]
    assert compensation["direct_action"] is True
    assert ranking["importance"] == "🔵"
    assert _select_id([ranking, compensation]) == "candidate-v2-120324"


def test_ozon_fbo_fee_change_outranks_regional_logistics_investment() -> None:
    fee = _candidate(
        130043,
        "Ozon меняет стоимость вывоза остатков FBO с 16 июня",
        "Новые тарифы FBO для продавцов влияют на хранение, забор товара со склада и логистическую маржу.",
        "Ozon official seller news",
    )
    investment = _candidate(
        135517,
        "Ozon и Чувашская Республика договорились о развитии логистики",
        "Компания подписала региональное соглашение о строительстве логистического центра без даты изменения тарифов или правил продавцов.",
        "Regional PR",
    )

    assert fee["score"] > investment["score"]
    assert investment["direct_action"] is False
    assert _select_id([investment, fee]) == "candidate-v2-130043"


def test_official_api_reporting_change_remains_publishable() -> None:
    api = _candidate(
        133898,
        "Яндекс Маркет обновил API отчетов для продавцов",
        "Официальное изменение: продавцам нужно обновить интеграцию API, отчеты и документы в кабинете продавца.",
        "Yandex Market official seller API",
    )

    scored = score_seller_actionability(api["title"], api["item"].text, source=api["source"])
    assert is_direct_seller_action(api["title"], api["item"].text, source=api["source"])
    assert api["direct_action"] is True
    assert api["actionability_score"] >= 3
    assert scored["ranking_score"] >= 0.7
    assert _select_id([api]) == "candidate-v2-133898"


def test_macro_corporate_news_is_demoted_not_deleted() -> None:
    macro = _candidate(
        135193,
        "Ozon инвестирует в новый логистический центр в регионе",
        "Корпоративная инфраструктурная новость о строительстве склада без новых комиссий, штрафов, сроков или правил для продавцов.",
        "Corporate PR",
    )

    assert macro["id"] == "candidate-v2-135193"
    assert macro["score"] < 0.5
    assert macro["seller_relevance_score"] <= 2
    assert macro["actionability_score"] <= 1
    assert macro["direct_action"] is False
    assert macro["importance"] == "🔵"
