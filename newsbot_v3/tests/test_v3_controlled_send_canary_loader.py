import sqlite3

from tools.v3_controlled_send_canary import _load_candidate


def _make_db(path: str) -> None:
    con = sqlite3.connect(path)
    con.execute(
        """
        CREATE TABLE news(
            id INTEGER PRIMARY KEY,
            title TEXT,
            text TEXT,
            link TEXT,
            source TEXT,
            created_at TEXT,
            seller_decision TEXT,
            seller_relevance_score INTEGER,
            actionability_score INTEGER,
            is_published INTEGER,
            max_message_id TEXT
        )
        """
    )
    con.commit()
    con.close()


def test_loader_selects_unpublished_publish_candidate(tmp_path):
    db = tmp_path / "v2.db"
    _make_db(str(db))
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO news VALUES(90045, 'WB тариф для продавцов', 'body', 'https://example.com/1', 'TG:mpgo_ru', '2026-05-27T10:00:00', 'publish', 6, 6, 0, '')"
    )
    con.execute(
        "INSERT INTO news VALUES(90046, 'digest post', 'body', 'https://example.com/2', 'TG:mpgo_ru', '2026-05-27T10:01:00', 'digest', 7, 7, 0, '')"
    )
    con.execute(
        "INSERT INTO news VALUES(90047, 'published post', 'body', 'https://example.com/3', 'TG:mpgo_ru', '2026-05-27T10:02:00', 'publish', 7, 7, 1, '')"
    )
    con.commit()
    con.close()

    candidate, reason, diag = _load_candidate(str(db), limit=50)
    assert reason == "quality_gate_passed_with_source_link"
    assert candidate is not None
    assert candidate["id"] == "candidate-v2-90045"
    assert int(diag["v2_publish_candidates_seen"]) == 2
    assert int(diag["v2_publish_candidates_eligible"]) == 1


def test_loader_respects_v2_id_filter(tmp_path):
    db = tmp_path / "v2.db"
    _make_db(str(db))
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO news VALUES(90045, 'Ozon изменения для продавцов', 'body', 'https://example.com/1', 'TG:mpgo_ru', '2026-05-27T10:00:00', 'publish', 6, 6, 0, '')"
    )
    con.execute(
        "INSERT INTO news VALUES(90046, 'WB изменения для продавцов', 'body', 'https://example.com/2', 'TG:mpgo_ru', '2026-05-27T11:00:00', 'publish', 7, 7, 0, '')"
    )
    con.commit()
    con.close()

    candidate, _, _ = _load_candidate(str(db), v2_id="90045")
    assert candidate is not None
    assert candidate["id"] == "candidate-v2-90045"


def test_loader_rejects_native_ad_leadgen(tmp_path):
    db = tmp_path / "v2.db"
    _make_db(str(db))
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO news VALUES(90039, 'Работаете на WB/Ozon, а деньги приходят, не те которые были запланированы?', 'проведём аудит и вернём деньги, оставьте заявку, напишите нам', 'https://example.com/ad', 'TG:ad', '2026-05-27T10:00:00', 'publish', 7, 7, 0, '')"
    )
    con.commit()
    con.close()

    candidate, reason, diag = _load_candidate(str(db), limit=50)
    assert candidate is None
    assert reason == "skipped_no_unpublished_v2_publish_candidate"
    assert diag["selection_reason"] == "skipped_native_ad_leadgen"
    assert diag["canary_editorial_gate_reason"] == "native_ad_leadgen"
    assert int(diag["native_ad_leadgen_candidates_skipped"]) == 1


def test_loader_rejects_russian_webinar_leadgen_patterns(tmp_path):
    db = tmp_path / "v2.db"
    _make_db(str(db))
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO news VALUES(90106, 'Круглый стол для селлеров', 'Приглашаем на вебинар 13 мая в 12:00, разберём как торговать на маркетплейсах, регистрация открыта', 'https://example.com/event', 'TG:event', '2026-05-27T10:03:00', 'publish', 7, 7, 0, '')"
    )
    con.commit()
    con.close()

    candidate, reason, diag = _load_candidate(str(db), limit=50)
    assert candidate is None
    assert reason == "skipped_no_unpublished_v2_publish_candidate"
    assert diag["selection_reason"] == "skipped_native_ad_leadgen"
    assert diag["canary_editorial_gate_reason"] == "native_ad_leadgen"
    assert int(diag["native_ad_leadgen_candidates_skipped"]) == 1


def test_loader_keeps_clean_platform_rule_news(tmp_path):
    db = tmp_path / "v2.db"
    _make_db(str(db))
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO news VALUES(91001, 'Ozon изменил комиссию за размещение FBO', 'Официальное обновление тарифов Ozon FBO для продавцов', 'https://example.com/ozon-fbo', 'TG:ozon', '2026-05-27T12:00:00', 'publish', 7, 7, 0, '')"
    )
    con.commit()
    con.close()

    candidate, reason, diag = _load_candidate(str(db), limit=50)
    assert candidate is not None
    assert reason == "quality_gate_passed_with_source_link"
    assert candidate["id"] == "candidate-v2-91001"
    assert int(diag["native_ad_leadgen_candidates_skipped"]) == 0


def test_loader_keeps_clean_wb_logistics_tariff_rules(tmp_path):
    db = tmp_path / "v2.db"
    _make_db(str(db))
    con = sqlite3.connect(db)
    con.execute(
        "INSERT INTO news VALUES(91002, 'WB изменил тарифы логистики для FBS', 'Официальное обновление правил логистики и тарифной сетки для продавцов', 'https://example.com/wb-logistics', 'TG:wb', '2026-05-27T12:10:00', 'publish', 7, 7, 0, '')"
    )
    con.commit()
    con.close()

    candidate, reason, diag = _load_candidate(str(db), limit=50)
    assert candidate is not None
    assert reason == "quality_gate_passed_with_source_link"
    assert candidate["id"] == "candidate-v2-91002"
    assert int(diag["native_ad_leadgen_candidates_skipped"]) == 0
