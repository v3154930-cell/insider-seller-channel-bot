import sqlite3
from pathlib import Path

import tools.v3_digest_send as v3_digest_send


def make_db(path: Path):
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE news(id INTEGER PRIMARY KEY, title TEXT, raw_text TEXT, link TEXT, source TEXT, seller_decision TEXT, is_published INTEGER, in_digest INTEGER, score REAL, priority_bucket TEXT, seller_relevance_score REAL, actionability_score REAL, created_at TEXT)')
    con.executemany('INSERT INTO news(id,title,raw_text,link,source,seller_decision,is_published,in_digest,score,priority_bucket,seller_relevance_score,actionability_score,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,datetime("now"))', [
        (1,'Ozon обновил тариф FBO','операционная новость по комиссии','https://a','official','publish',0,0,1,'p1',0.9,0.8),
        (2,'Вебинар для селлеров','leadgen event','https://b','tg','publish',0,0,1,'p1',0.8,0.8),
        (3,'Ежедневный дайджест','подборка','https://c','tg','publish',0,0,1,'p1',0.7,0.7),
        (4,'Уже опубликовано','x','https://d','official','publish',1,0,1,'p1',0.7,0.7),
    ])
    con.commit(); con.close()


def test_filters_exclude_native_and_low_value(tmp_path):
    db = tmp_path / 'v2.db'
    make_db(db)
    rows = v3_digest_send.load_candidates(str(db), 24, 20)
    selected, counters = v3_digest_send.select_candidates(rows, limit=20)
    assert [x['id'] for x in selected] == [1]
    assert counters['native_ad_leadgen_skipped'] >= 1
    assert counters['low_value_skipped'] >= 1


def test_digest_excludes_event_episode_and_social_but_keeps_actionable():
    rows = [
        {'id': 1, 'title': 'Круглый стол «Селлеры и маркетплейсы»', 'raw_text': 'регистрация открыта', 'link': '', 'source': 'tg', 'is_published': 0, 'in_digest': 0},
        {'id': 2, 'title': 'В новом выпуске обсудили комиссии Ozon', 'raw_text': 'подкаст', 'link': '', 'source': 'tg', 'is_published': 0, 'in_digest': 0},
        {'id': 3, 'title': 'Морковки по вайбу — поддерживаем? 👍 / 👎', 'raw_text': 'кто для вас топ?', 'link': '', 'source': 'tg', 'is_published': 0, 'in_digest': 0},
        {'id': 4, 'title': 'Ozon обновил FBO тарифы для селлеров', 'raw_text': 'изменение комиссии с 1 июня', 'link': 'https://ozon', 'source': 'official', 'is_published': 0, 'in_digest': 0},
        {'id': 5, 'title': 'WB изменил логистический тариф', 'raw_text': 'новые правила отгрузки FBS', 'link': 'https://wb', 'source': 'official', 'is_published': 0, 'in_digest': 0},
    ]
    selected, counters = v3_digest_send.select_candidates(rows, limit=10)
    assert [x['id'] for x in selected] == [4, 5]
    assert counters['digest_event_leadgen_skipped'] == 1
    assert counters['low_value_skipped'] == 1
    assert counters['digest_social_low_value_skipped'] == 1


def test_digest_excludes_non_actionable_generic_brand_post():
    rows = [
        {'id': 6, 'title': 'Как развивать бренд в соцсетях', 'raw_text': 'советы по контенту и комьюнити', 'link': '', 'source': 'tg', 'is_published': 0, 'in_digest': 0},
        {'id': 7, 'title': 'Yandex Market обновил комиссию для FBS', 'raw_text': 'изменения тарифов для селлеров', 'link': '', 'source': 'official', 'is_published': 0, 'in_digest': 0},
    ]
    selected, counters = v3_digest_send.select_candidates(rows, limit=10)
    assert [x['id'] for x in selected] == [7]
    assert counters['digest_non_actionable_skipped'] == 1


def test_build_morning_and_final_text():
    txt1 = v3_digest_send.build_digest([{'title':'T1','link':'https://x'}], 'morning')
    txt2 = v3_digest_send.build_digest([{'title':'T2','link':'https://y'}], 'final')
    assert 'УТРЕННИЙ' in txt1
    assert 'ВЕЧЕРНИЙ' in txt2


def test_digest_excludes_non_actionable_brand_development_item():
    rows = [
        {'id': 1, 'title': 'Маркетплейсы постепенно становятся средой для развития брендов', 'raw_text': 'аналитика по трендам', 'link': '', 'source': 'tg', 'is_published': 0, 'in_digest': 0},
    ]
    selected, counters = v3_digest_send.select_candidates(rows, limit=10)
    assert selected == []
    assert counters['digest_non_actionable_skipped'] == 1


def test_digest_excludes_live_like_brand_background_item_and_counts_skip():
    rows = [
        {
            'id': 16,
            'title': 'Маркетплейсы постепенно становятся средой для развития брендов, а не только каналом продаж. Если раньше продавцу было достаточно работать с карточкой товара, ценой, отзывами...',
            'raw_text': '',
            'processed_text': '',
            'link': '',
            'source': 'tg',
            'is_published': 0,
            'in_digest': 0,
        },
    ]
    selected, counters = v3_digest_send.select_candidates(rows, limit=10)
    assert selected == []
    assert counters['digest_non_actionable_skipped'] == 1


def test_digest_excludes_non_actionable_ai_search_interface_item():
    rows = [
        {'id': 2, 'title': 'Только ИИ и нейросети! Китайские маркетплейсы полностью отказываются от обычной поисковой выдачи', 'raw_text': 'новые интерфейсы поиска', 'link': '', 'source': 'tg', 'is_published': 0, 'in_digest': 0},
    ]
    selected, counters = v3_digest_send.select_candidates(rows, limit=10)
    assert selected == []
    assert counters['digest_non_actionable_skipped'] == 1


def test_digest_excludes_non_actionable_labor_legal_item():
    rows = [
        {'id': 3, 'title': 'Суд запретил Яндекс Маркету искать кладовщика-мужчину', 'raw_text': 'дело о трудовой дискриминации', 'link': '', 'source': 'media', 'is_published': 0, 'in_digest': 0},
    ]
    selected, counters = v3_digest_send.select_candidates(rows, limit=10)
    assert selected == []
    assert counters['digest_non_actionable_skipped'] == 1


def test_digest_includes_ozon_removal_placement_fee_item():
    rows = [
        {'id': 4, 'title': 'Ozon перестанет брать плату за размещение после заявки на вывоз', 'raw_text': 'правила FBO для продавцов', 'link': '', 'source': 'official', 'is_published': 0, 'in_digest': 0},
    ]
    selected, _ = v3_digest_send.select_candidates(rows, limit=10)
    assert [x['id'] for x in selected] == [4]




def test_digest_includes_ozon_fbo_no_placement_fee_item():
    rows = [
        {'id': 14, 'title': 'Ozon обещает не брать с FBO-селлеров деньги за размещение', 'raw_text': 'изменения условий для продавцов', 'link': '', 'source': 'official', 'is_published': 0, 'in_digest': 0},
    ]
    selected, _ = v3_digest_send.select_candidates(rows, limit=10)
    assert [x['id'] for x in selected] == [14]


def test_digest_includes_wildberries_offer_suspension_payments_item():
    rows = [
        {'id': 15, 'title': 'Новая оферта Wildberries расширит основания для приостановки выплат продавцам', 'raw_text': 'изменения условий оферты', 'link': '', 'source': 'official', 'is_published': 0, 'in_digest': 0},
    ]
    selected, _ = v3_digest_send.select_candidates(rows, limit=10)
    assert [x['id'] for x in selected] == [15]
def test_digest_includes_wb_logistics_tariff_item():
    rows = [
        {'id': 5, 'title': 'WB обновил тарифы обратной логистики', 'raw_text': 'изменения для FBS', 'link': '', 'source': 'official', 'is_published': 0, 'in_digest': 0},
    ]
    selected, _ = v3_digest_send.select_candidates(rows, limit=10)
    assert [x['id'] for x in selected] == [5]


def test_digest_includes_wb_fas_payment_complaint_item():
    rows = [
        {'id': 6, 'title': '250 селлеров пожаловались в ФАС на невыплату WB', 'raw_text': 'жалоба по выплатам', 'link': '', 'source': 'media', 'is_published': 0, 'in_digest': 0},
    ]
    selected, _ = v3_digest_send.select_candidates(rows, limit=10)
    assert [x['id'] for x in selected] == [6]


def test_digest_includes_ozon_copied_cards_complaint_sku_item():
    rows = [
        {'id': 7, 'title': 'Ozon усложнил порядок подачи жалоб на скопированные карточки', 'raw_text': 'по SKU теперь другой порядок', 'link': '', 'source': 'official', 'is_published': 0, 'in_digest': 0},
    ]
    selected, _ = v3_digest_send.select_candidates(rows, limit=10)
    assert [x['id'] for x in selected] == [7]


def test_digest_excludes_non_actionable_pochta_support_item_without_operational_terms():
    rows = [
        {'id': 8, 'title': 'Маркетплейсы запускают проект по поддержке Почты России', 'raw_text': 'новости партнерства', 'link': '', 'source': 'media', 'is_published': 0, 'in_digest': 0},
    ]
    selected, counters = v3_digest_send.select_candidates(rows, limit=10)
    assert selected == []
    assert counters['digest_non_actionable_skipped'] == 1


def test_digest_non_actionable_skipped_increments_for_multiple_hard_deny_rows():
    rows = [
                {'id': 11, 'title': 'Только ИИ и нейросети! Китайские маркетплейсы полностью отказываются от обычной поисковой выдачи', 'raw_text': 'интерфейсы', 'link': '', 'source': 'tg', 'is_published': 0, 'in_digest': 0},
        {'id': 12, 'title': 'Суд запретил Яндекс Маркету искать кладовщика-мужчину', 'raw_text': 'трудовой спор', 'link': '', 'source': 'media', 'is_published': 0, 'in_digest': 0},
        {'id': 13, 'title': 'Маркетплейсы запустили проект по поддержке Почты России', 'raw_text': 'пилот', 'link': '', 'source': 'media', 'is_published': 0, 'in_digest': 0},
    ]
    selected, counters = v3_digest_send.select_candidates(rows, limit=10)
    assert selected == []
    assert counters['digest_non_actionable_skipped'] == 3

def test_digest_visual_diagnostics_disabled_by_default(monkeypatch, tmp_path, capsys):
    db = tmp_path / 'v2.db'
    make_db(db)
    monkeypatch.setattr('sys.argv', ['v3_digest_send.py', '--kind', 'morning', '--v2-db', str(db)])
    rc = v3_digest_send.main()
    out = capsys.readouterr().out
    assert rc == 0
    assert 'visual_assets_enabled=false' in out
    assert 'mascot_send_status=skipped' in out
