from __future__ import annotations

SELLER_HELPER_CTA = """🧮 Селлер хелпер

Бесплатный калькулятор для селлера:
считает маржу, комиссии, логистику и примерную прибыль по товару.

Главное — сравнивает экономику на разных площадках:
Ozon, Wildberries и Яндекс Маркет.

Помогает понять, где товар выгоднее продавать, какую цену ставить и стоит ли запускать рекламу.

Нажмите кнопку ниже и рассчитайте экономику товара перед закупкой или запуском.
"""
SELLER_HELPER_BUTTON_TEXT = "📊 Рассчитать маржу"


def plan_helper_cta(enabled: bool = True, force_mock_error: bool = False) -> dict:
    if not enabled:
        return {
            "seller_helper_cta_planned": False,
            "seller_helper_cta_present": False,
            "seller_helper_cta_mode": "separate_message",
            "seller_helper_cta_text": SELLER_HELPER_BUTTON_TEXT,
            "seller_helper_cta_url_present": False,
            "seller_helper_cta_send_attempted": False,
            "seller_helper_cta_send_status": "skipped",
            "seller_helper_cta_message_id": "",
            "seller_helper_cta_error": "",
            "seller_helper_cta_visible_delivery_confirmed": False,
            "separate_seller_helper_message_sent": False,
            "keyboard_contract_valid": True,
            "source_url_button_used": False,
            "external_url_button_forbidden": True,
            "main_post_rollback": False,
        }
    return {
        "seller_helper_cta_planned": True,
        "seller_helper_cta_present": True,
        "seller_helper_cta_mode": "separate_message",
        "seller_helper_cta_text": SELLER_HELPER_BUTTON_TEXT,
        "seller_helper_cta_url_present": True,
        "seller_helper_cta_send_attempted": False,
        "seller_helper_cta_send_status": "error" if force_mock_error else "dry_run",
        "seller_helper_cta_message_id": "",
        "seller_helper_cta_error": "mock_error" if force_mock_error else "",
        "seller_helper_cta_visible_delivery_confirmed": False,
        "separate_seller_helper_message_sent": False,
        "keyboard_contract_valid": True,
        "source_url_button_used": False,
        "external_url_button_forbidden": True,
        "main_post_rollback": False,
    }
