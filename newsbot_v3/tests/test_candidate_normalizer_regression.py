from app.publisher.candidate_normalizer import normalize_v2_row_to_candidate
from app.publisher.selection_policy import dry_run_selection
from app.publisher.native_ad_filter import detect_native_ad_leadgen_reason


def test_deviantart_fine_is_low_value_background_and_skipped() -> None:
    row = {
        "id": 89294,
        "v2_news_id": 89294,
        "title": "Сайт для художников DeviantArt получил штраф за запрещенный контент",
        "source": "RBC",
        "text": "Таганский районный суд Москвы оштрафовал компанию DeviantArt Inc.",
        "link": "https://example.com/deviantart-fine",
    }
    cand = normalize_v2_row_to_candidate(row)
    assert cand["seller_relevance_score"] == 1
    assert cand["actionability_score"] == 1
    assert cand["direct_action"] is False
    assert "low_value_background" in cand["topic_tags"]

    sel = dry_run_selection([cand], published_today=0)
    assert sel["selected_candidate_id"] is None
    assert sel["selection_reason"] == "skipped_low_action_background"


def test_native_ad_leadgen_candidate_is_blocked_before_publish() -> None:
    row = {
        "id": 90039,
        "v2_news_id": 90039,
        "title": "Работаете на WB/Ozon, а деньги приходят, не те которые были запланированы?",
        "source": "TG:ad",
        "text": "Проведём аудит кабинета, вернём деньги, оставьте заявку.",
        "link": "https://example.com/native-ad",
    }
    cand = normalize_v2_row_to_candidate(row)
    sel = dry_run_selection([cand], published_today=0)
    assert sel["selected_candidate_id"] is None
    assert sel["selection_reason"] == "skipped_native_ad_leadgen"
    assert int(sel["native_ad_leadgen_blocked"]) == 1


def test_native_ad_event_webinar_patterns_are_blocked() -> None:
    reason = detect_native_ad_leadgen_reason(
        "Вебинар для селлеров: как торговать на маркетплейсах",
        "Приглашаем на эфир 22 мая в 13:00 мск, зарегистрируйтесь для участия.",
    )
    assert reason == "native_ad_leadgen"


def test_clean_marketplace_policy_news_stays_unblocked() -> None:
    reason = detect_native_ad_leadgen_reason(
        "WB обновил правила логистики для продавцов",
        "Официальное изменение тарифов и SLA без рекламного призыва к регистрации.",
    )
    assert reason is None
