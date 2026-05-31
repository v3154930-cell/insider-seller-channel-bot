#!/usr/bin/env python3
from __future__ import annotations

from app.scoring.seller_relevance import evaluate_seller_relevance


def run_fixture(title: str, text: str) -> dict:
    return evaluate_seller_relevance(title, text, marketplace=None, source="fixture")


def main() -> int:
    fixtures = [
        ("wb_tariff", "WB меняет комиссии FBO с 1 июня", "Комиссия увеличена, дедлайн внедрения обязателен."),
        ("ozon_logistics", "Ozon обновил хранение и возвраты", "Новые тарифы логистики и правила возвратов с дедлайном."),
        ("marking", "Честный знак: новый дедлайн", "Маркировка обязательна до 1 июля."),
        ("tax", "ФНС изменила порядок НДС для маркетплейсов", "Нужна проверка налогового режима УСН/НДС."),
        ("corporate_stake", "ВТБ получит 5% в WB Банке", "Сделка по доле без изменений условий для продавцов."),
        ("generic_pr", "Интервью топ-менеджера маркетплейса", "Стратегия роста компании на 3 года."),
        ("banking", "Маркетплейс-банк меняет график выплат", "Новые сроки выплат продавцам и изменения расчетного окна."),
    ]
    seen = len(fixtures)
    passed = 0
    corporate_ok = True
    margin_ok = True
    legal_tax_ready = False
    marking_ready = False
    importance_ready = True

    for name, title, text in fixtures:
        r = run_fixture(title, text)
        if name == "wb_tariff":
            ok = r["importance_indicator"] == "🔴" and (not r["no_direct_action"])
        elif name == "ozon_logistics":
            ok = r["importance_indicator"] == "🔴"
        elif name == "marking":
            ok = r["importance_indicator"] == "🔴"; marking_ready = "marking_chestny_znak" in r["topics"]
        elif name == "tax":
            ok = r["importance_indicator"] in {"🔴", "🟡"}; legal_tax_ready = "legal_tax_regulatory" in r["topics"]
        elif name == "corporate_stake":
            ok = r["importance_indicator"] in {"🔵", "🟡"} and r["no_direct_action"]; corporate_ok = ok
        elif name == "generic_pr":
            ok = r["importance_indicator"] == "🔵"
        else:
            ok = r["importance_indicator"] in {"🟡", "🔴"}
        margin_ok = margin_ok and ("маржу" not in str(r).lower())
        importance_ready = importance_ready and r["importance_indicator"] in {"🔴", "🟡", "🔵"}
        passed += 1 if ok else 0

    status = "OK" if passed == seen else "FAIL"
    print(f"V3_SELLER_FRAMEWORK_STATUS={status}")
    print(f"fixtures_seen={seen}")
    print(f"fixtures_passed={passed}")
    print(f"corporate_pr_low_action_ok={'true' if corporate_ok else 'false'}")
    print(f"no_fake_margin_advice={'true' if margin_ok else 'false'}")
    print(f"legal_tax_topic_ready={'true' if legal_tax_ready else 'false'}")
    print(f"marking_topic_ready={'true' if marking_ready else 'false'}")
    print(f"importance_rules_ready={'true' if importance_ready else 'false'}")
    print("production_mutation=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
