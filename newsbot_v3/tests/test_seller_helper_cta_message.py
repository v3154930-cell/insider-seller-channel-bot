from app.publisher.cta import SELLER_HELPER_BUTTON_TEXT, SELLER_HELPER_CTA, plan_helper_cta


def test_separate_seller_helper_cta_text_explains_value_for_new_subscribers():
    assert "Селлер хелпер" in SELLER_HELPER_CTA
    assert "Инсайдер Helper" not in SELLER_HELPER_CTA
    assert "Бесплатный калькулятор для селлера" in SELLER_HELPER_CTA
    for token in (
        "маржу",
        "комиссии",
        "логистику",
        "примерную прибыль",
        "сравнивает экономику",
        "Ozon",
        "Wildberries",
        "Яндекс Маркет",
        "где товар выгоднее продавать",
    ):
        assert token in SELLER_HELPER_CTA


def test_margin_button_text_is_exactly_required():
    assert SELLER_HELPER_BUTTON_TEXT == "📊 Рассчитать маржу"


def test_seller_helper_is_still_separate_message_and_sent_only_with_real_message_id_contract():
    planned = plan_helper_cta(enabled=True)
    assert planned["seller_helper_cta_mode"] == "separate_message"
    assert planned["separate_seller_helper_message_sent"] is False
    assert planned["seller_helper_cta_message_id"] == ""


def test_main_news_and_full_article_texts_do_not_include_margin_button_cta_text():
    from app.models import NewsItem
    from app.publisher.post_builder import build_post
    import full_article_callback_worker as worker

    item = NewsItem(
        news_id="90045",
        title="Заголовок",
        text="Короткий пост",
        link="https://example.com/source",
        source_name="example.com",
    )
    item.raw_text = "x" * 2000
    post = build_post(item)
    assert SELLER_HELPER_BUTTON_TEXT not in post["text"]

    full_article_message = worker.build_full_article_message((1, "t", "raw body", "https://link", "https://source", "5"))
    assert SELLER_HELPER_BUTTON_TEXT not in full_article_message
