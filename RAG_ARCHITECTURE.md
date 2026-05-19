# RAG architecture for Insider Seller / Seller Helper

## Purpose

RAG Store is not the main tariff calculation database.

RAG Store stores:
- official marketplace rules and help pages;
- offers and seller terms;
- news signals;
- regulator signals;
- court cases;
- explanations and legal context.

Helper Bot tariff database remains the source of truth for numeric commissions and margin calculations.

## Main sources of truth

### Numeric tariffs and margin calculations

Path:

/opt/helperbot

Role:

- exact marketplace commission rates;
- category matching;
- margin calculation;
- tax nuance calculation;
- marketplace comparison.

Do not duplicate all numeric tariff rows into rag_documents.

### RAG Store

Path:

/opt/newsbot_v2/data/rag_store.db

Tables:

- rag_sources: source registry;
- rag_documents: imported documents and news;
- rag_documents_fts: full-text search index.

## Trust levels

Priority for answers:

1. official / high
2. internal_db / high
3. media / medium
4. telegram / medium

News and Telegram are signals, not final proof.

## RAG layers

Official tariff documents:

tariff_official

Official legal documents:

legal_official

News and analytics:

news_signal

Internal Helper Bot tariff source:

tariff_calculation_source

## Current safe point: 2026-04-29

Current RAG DB:

- rag_documents: 68 rows
- rag_documents_fts: 68 rows
- rag_sources: 13 rows


Current internal calculation sources:

- Helper Bot Ozon tariff database
- Helper Bot Wildberries tariff database
- Helper Bot Yandex Market tariff database

Internal calculation source path:

/opt/helperbot/data/unified_tariffs.db#clean_commissions

Current official imported documents:

- Yandex Market rates
- Yandex Market seller docs

Current news signal documents:

- Telegram: 51
- Media: 15

FTS index was rebuilt after importing official documents.

Backup before rebuild:

data/rag_store.db.bak_20260429_115101

## Current known limitations

- Ozon official pages do not load reliably via simple urllib.
- Wildberries docs and seller terms may require special import or manual files.
- Yandex Market official pages currently load partially.
- Some documents have marketplace = unknown and must not be treated as marketplace-specific proof.
- Promo/general items must stay in news_signal and should not override official data.
- source_type should later be normalized: tg -> telegram.

## Rule for Seller Helper

- Numbers come from Helper Bot tariff DB.
- Explanations and legal context come from RAG.
- News signals only trigger checks and warnings.

## Safe point: 2026-04-29 — RAG + Helper bridge

A diagnostic bridge was created:

/opt/helperbot/rag_bridge.py

Purpose:

- read numeric tariffs from Helper Bot tariff DB;
- read official/news/legal context from RAG Store;
- build a debug answer with tariff rows, RAG context and tax warning;
- test architecture without changing the production Helper Bot.

Production Helper Bot was not changed:

- /opt/helperbot/max_bot_polling.py was not modified for this bridge;
- helperbot.service was not restarted;
- the bridge is diagnostic only.

Correct tariff source of truth:

/opt/newsbot_v2/data/unified_tariffs.db#clean_commissions

Old/local copy must not be treated as source of truth:

/opt/helperbot/data/unified_tariffs.db

RAG Store:

/opt/newsbot_v2/data/rag_store.db

Important Ozon rule:

- Ozon main answer must use fee_type = marketplace_service_rate;
- Ozon Select / commission_only must not be used as the main answer;
- Select can remain as test/reference data only.

Confirmed Ozon standard source:

- source_file: 20260426_141844_marketplace-services-rates-01-04-2026.xlsx
- valid_from: 2026-04-01
- source_note: Ozon marketplace services rates, standard tariff table from 01.04.2026

Bridge improvements added:

- tariff DB path fixed to /opt/newsbot_v2/data/unified_tariffs.db;
- internal rag_sources path fixed to /opt/newsbot_v2/data/unified_tariffs.db#clean_commissions;
- marketplace mapping added:
  - wildberries -> wb
  - yandex_market -> yandex
  - ozon -> ozon
- soft Russian term forms added:
  - чайник походный -> Чайники походные
- Ozon fee_type filter added:
  - fee_type = marketplace_service_rate

Control tests:

1. Ozon:

Command:

python3 /opt/helperbot/rag_bridge.py "чайник походный" --marketplace ozon

Result:

- Чайники походные / FBY / 40%
- Чайники походные / FBS / 47%
- Чайники походные / EXPRESS / 40%
- Чайники походные / DBS / 47%

All rows came from marketplace_service_rate, not Select.

2. Wildberries:

Command:

python3 /opt/helperbot/rag_bridge.py "ботинки" --marketplace wildberries

Result:

- tariffs found via marketplace mapping wildberries -> wb.

Known limitation:

- special WB schemes such as express/self-delivery must not be shown as the main "from %" benchmark without explanation.

3. Yandex Market:

Command:

python3 /opt/helperbot/rag_bridge.py "косметика" --marketplace yandex_market

Result:

- tariffs found via marketplace mapping yandex_market -> yandex.

Known limitation:

- ranking is still rough; query "косметика" may match "автокосметика".
- future ranking should prefer beauty/cosmetics categories over auto-cosmetics when the user likely means cosmetics.

Next steps before production integration:

- do not integrate rag_bridge.py into max_bot_polling.py yet;
- improve ranking and scheme prioritization;
- filter noisy RAG news when official/high context exists;
- prepare a clean user-facing answer format;
- then integrate carefully with timestamp backup and py_compile checks.
