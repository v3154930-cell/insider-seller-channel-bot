# PROJECT PASSPORT — Insider Seller / NEWSBOT / Seller Helper

## v7.3 operational update — 2026-06-04

Этот файл восстанавливает полную структуру паспорта v7.2 как baseline. Предыдущий компактный `PROJECT_PASSPORT.md` на сервере был полезен как оперативная памятка, но не должен заменять полный паспорт: в v7.2 сохранены инфраструктура, правила, roadmap, Seller Helper, Docobrazec, OfferDoctor, RAG, тарифная база, official pipeline, audio digest и Definition of Done.

### Что сделано после v7.2

- Подключён реальный LLM-контур для редакторской обработки постов NEWSBOT.
- Основной LLM-провайдер: GitHub Models.
- Резервный LLM-провайдер: GigaChat-2.
- Третий контур: template/rules fallback.
- LLM enhanced text сохраняется в `news.processed_text`.
- Восстановлены светофор и маскоты для LLM-постов.
- Исправлен дубль блока «Вывод для селлера».
- Восстановлен форматный контракт поста: LLM пишет смысл, `formatters.py` отвечает за HTML, жирный блок `<b>🎯 Что это значит для селлера:</b>`, светофор и очистку технического мусора.
- Добавлен `EDITOR_PROFILE_V1` как постоянный редакторский профиль для LLM seller summaries.
- Улучшен аудиодайджест: сохранение пауз, чистка повторов/склеек, более читаемый сценарий.
- Проведена серверная чистка: удалены устаревшие tracked backup-файлы, старые архивы, WAV, старые DB-бэкапы; `.git` сжат через `git gc`; активный проект уменьшен примерно с 14G до 1.6G.
- Обновлён короткий оперативный паспорт, но этот полный паспорт должен оставаться главным baseline.

### Коммиты после v7.2 safe point

- 59e1918 Enable LLM preprocessing for publisher posts
- f764d3f Restore traffic light and mascot images for LLM posts
- a627f38 Save final LLM enhanced text for published posts
- 09ec8a6 Avoid duplicate seller conclusions in LLM posts
- 66d245a Improve audio digest script readability and pauses
- bf57654 Update project passport after LLM and audio digest improvements
- 270ce61 Restore editor markup contract for LLM posts
- 84620db Add editor profile for LLM seller summaries
- a0fbaaf Remove obsolete tracked backup files

### Актуальный статус задач v7.3

DONE:
- LLM-контур NEWSBOT работает в бою через GitHub Models/GigaChat/template.
- Редакторский профиль добавлен в код.
- Формат постов возвращён под контроль `formatters.py`.
- Аудиодайджест первично приведён в порядок.
- Серверный мусор очищен, Git сжат.

ACTIVE / P0:
- Наблюдать 1–2 дня реальные LLM-посты: качество выводов, релевантность, светофор, маскоты, отсутствие технической разметки.
- Проверить свежие MP3 аудиодайджеста на слух.
- Ротировать засвеченные GitHub/MAX/GigaChat токены и проверить, что новые токены не выводятся в чат/логи.
- Сохранить полный паспорт v7.3 на сервере как baseline, а компактный паспорт оставить только как quick status, если нужен.
- Не ломать текущий working regular publisher.

ACTIVE / P1:
- Нормализовать GitHub/Codex repository state.
- Добавить лёгкую наблюдаемость LLM: provider used, fallback rate, errors, template fallback count.
- Улучшить `EDITOR_PROFILE_V1` на реальных плохих постах: не в тему, общие выводы, слабая конкретика, рыночный фон.
- Улучшить title normalizer: не резать смысл, API endpoints, числа, названия площадок.
- Продолжить узкую чистку дублей и нативной рекламы без глобального ужесточения фильтров.
- Вернуться к Seller Helper product roadmap: `calculation_result JSON` → deterministic infographic renderer → PNG/PDF.

ACTIVE / P2:
- Admin/source dashboard: freshness TG JSON, official JSON, raw items, inserted, decisions, published today, LLM provider usage, audio status.
- Official signal quality tuning.
- Docobrazec / Legal RAG API bridge только после расчётного ядра и privacy-by-design.
- OfferDoctor как маркетинговый модуль внутри Seller Helper после подтверждения спроса.

### Важное правило дальнейшей работы

Полный паспорт v7.2/v7.3 — источник архитектурной правды. Компактный `PROJECT_PASSPORT.md` не должен выкидывать инфраструктуру. Если нужен короткий файл для сессии, он должен называться вроде `PROJECT_STATUS.md` и ссылаться на полный паспорт, а не заменять его.

---



---

# BASELINE v7.2 FROM UPLOADED DOCX


## ПАСПОРТ И ТЗ ЭКОСИСТЕМЫ
«Инсайдер Селлер» / NEWSBOT v2 / Seller Helper
Версия 7.2 — контрольная точка 18.05.2026: восстановление NEWSBOT v2, official GitHub JSON, audio digest, roadmap
Safe Point: 18.05.2026; основание: v7.1 от 17.05.2026 + технический блок 18.05.2026

## 0. Правило эксплуатации паспорта v7.2
Содержание v6.7 не удаляется: оно перенесено в тематические разделы и снабжено реестром переноса.
Новые задачи добавлять в Backlog/Этапы, готовые переносить в Сделано, неудачные решения — в Устаревшее/запрещено.
Паспорт v7 — рабочий навигатор, а не хронологический дневник патчей.
v7.1 добавляет правило: dry-run допускается только как временная диагностическая проверка с датой/условием снятия и обязательным возвратом в live-режим.
Публикационный контур NEWSBOT v2 нельзя считать исправленным, пока collector пишет решения только в лог, а не в news_queue.db.
После каждой аварийной правки публикаций проверять цепочку целиком: source → collector → seller_filter_live → DB seller_decision → publisher → MAX.
v7.1 дополнена продуктовым направлением: расчётная инфографика Seller Helper и скачивание результата в PNG/PDF. Это добавляется в roadmap как отдельный поэтапный модуль, а не как случайная генерация картинок.
Для финансовых расчётов запрещён подход «AI нарисует инфографику»: цифры, проценты, таблицы и диаграммы должны строиться кодом из структурированного результата расчёта.
v7.2 добавляет контрольную точку 18.05.2026: публикационный контур NEWSBOT v2 восстановлен и усилен не временным костылём, а штатными механизмами в collector/db/publisher/watchdog/official pipeline.
Все изменения v7.2 должны читаться как структурный safe point: готовые задачи перенесены в Done, активные P0/P1/P2 уточнены, quarantine и ротация токенов оставлены как отдельные хвосты после стабилизации.
GitHub JSON теперь является основным способом обхода слепоты VPS к Telegram: обычный tg_posts.json и официальный official_marketplace_posts.json создаются одним existing GitHub Action, а не отдельными сборщиками.
Публикационная норма трактуется строго как минимум: будни 10, выходные 3. Quota fallback добирает минимум, но не останавливает публикации сверх минимума.

## 1. Текущий executive summary v7.2
Экосистема состоит из MAX-канала, NEWSBOT v2, Seller Helper, единой тарифной базы, RAG Store, будущих модулей Docobrazec и OfferDoctor.
Главная ценность — не просто новости, а прикладная аналитика: комиссии, тарифы, оферты, маржа, юридические риски и действие «что делать дальше».
Seller Helper — закрытая прикладная польза для подписчиков канала; доступ проверяется по user_id.

## 17.05.2026 закрыта авария молчания обычных новостей: проблема была не в дефиците источников, а в боевом оставленном dry-run фильтра.
Нормальная публикационная цепочка зафиксирована как collector → seller_filter_live → DB seller_decision → publisher_v2; временный promote bridge убран из run_regular_v2.sh.
Введены safeguards: hard-ignore рекламного мусора в seller_filter.py, live lookback 8 часов, stale publish guard в publisher_v2.py.
Редакционная норма канала: будни — минимум 10 публикаций, выходные/праздники — минимум 2-3 публикации; аудиодайджест не закрывает норму обычных новостей.
Новое продуктовое направление v7.1: Seller Helper должен уметь превращать расчёт в понятную инфографику: один товар/одна площадка, сравнение схем, будущий режим сравнения площадок, экспорт PNG и PDF.
Архитектурное решение: расчёт → calculation_result JSON → HTML/SVG-шаблон → Playwright/Chromium renderer → PNG/PDF → отправка или скачивание в MAX. LLM может помогать только с коротким выводом, но не является источником чисел.

## 18.05.2026 принят safe point v7.2: после аварии молчания публикационный контур восстановлен и проверен health-check: cron активен, compile OK, publish pending пустой, БД целые.
db.py получил live revive для старых неопубликованных publish-кандидатов через controlled refresh created_at; collector пишет Publish pending after write.
publisher_v2.py: duplicate guard переводит повторы в duplicate, quota fallback добирает минимум по дню недели, stale/duplicate поведение больше не маскирует проблему под digest.
Official sources: GitHub Action создаёт official_marketplace_posts.json, official_channel_collector.py читает OFFICIAL_JSON_URLS, прямой Telegram fallback пропускается при живом JSON.
official_signal_bridge.py теперь группирует несколько сигналов одного official-поста в одну grouped news item, чтобы не плодить одинаковые публикации api/logistics/tariff по одному сообщению.
Аудиодайджест v7.2: убраны навязчивые seller-check фразы, расширены концовки до 24 вариантов, короткие спокойные выпуски больше не ломают cron, добавлен preview-скрипт без публикации.

## 2. Что сделано и считается рабочим
NEWSBOT v2: collector/publisher/digest/full article/audio/signal monitor/admin работают как core.
Full article: кнопка «Читать полностью» раскрывает текст в том же MAX-посте.
Вечерний монитор: signal_monitor.py + signal_digest.py + signal_digest_runs.
Аудиодайджест: cron 22:45 после очистки текста и дублей.
Seller Helper: комиссии, маржа, НДС, налог, risk insights, кнопочный UX, subscription gate.
Яндекс API tariffs/calculate: 16282 строки FBS/FBY, valid_from=2026-05-13.
NEWSBOT v2 публикационный контур: live seller_filter пишет реальные решения publish/digest/ignore в БД через wrapper add_to_queue_batch в db.py.
run_collector_v2.sh через .env подтверждён как правильный способ проверки: TG JSON даёт 108, общий raw-поток 240, live-фильтр применяет 64 решения.
run_regular_v2.sh очищен от временного promote_publish_candidates.py; publisher_v2 снова работает штатно и сам защищён stale publish guard.
Аудиодайджест очищен от повторяющейся фразы «что проверить селлеру», получил вариативные концовки и защитную финальную очистку перед озвучкой.
Принято продуктово-техническое решение по инфографике: не использовать AI-генерацию изображений для расчётных цифр; строить карточки через детерминированный шаблонный renderer.
Зафиксированы первые целевые форматы: карточка одного расчёта, сравнение схем внутри площадки, будущая карточка сравнения площадок и PDF-отчёт для скачивания/пересылки.
v7.2 / 18.05.2026: health-check подтверждён: cron collector/publisher/signal/audio/watchdog/official active; py_compile ключевых файлов OK; news_queue.db и unified_tariffs.db integrity_check ok; active project 1.6G; quarantine 5.0G.
SELLER_FILTER_MODE переведён в keyword, SELLER_FILTER_LIVE=1; dryrun больше не остаётся в .env как опасный хвост.
PUBLISH_WEEKDAY_TARGET=10, PUBLISH_WEEKEND_TARGET=3, NEWSBOT_TZ=Europe/Moscow добавлены в .env; watchdog и publisher используют effective target по дню недели.
official_marketplace_posts.json подключён как основной official source; direct t.me fallback в official_channel_collector.py запускается только при недоступном/пустом JSON или OFFICIAL_TG_FALLBACK=1.
run_official_signals_v2.sh поставлен в cron каждый час в дневном окне; official signal bridge создан и затем обновлён до grouped-логики.
run_audio_digest_preview.sh добавлен для предпросмотра сценария без SaluteSpeech, без MP3 и без отправки в MAX.

## 3. Строгие правила проекта
Числовые комиссии и расчёты брать из clean_commissions / future fee components, не из RAG/новостей.
RAG — текстовый слой, не источник числовых ставок и не хранилище персональных данных.
user_id и chat_id в MAX не смешивать: user_id = право доступа, chat_id = адрес ответа.
Ozon Select не переводить в usable и не использовать в боевом стандартном расчёте.
Ozon marketplace_service_rate называть сервисной ставкой стандартного слоя, а не полной комиссией всех удержаний.
Любая правка кода: backup → py_compile → локальный тест → restart → journalctl.
Dry-run любого фильтра/публикационной логики запрещено оставлять в боевой цепочке collector → publisher. Dry-run должен иметь срок снятия, owner, проверочный лог и live-check.
seller_filter в production обязан писать в БД seller_decision, seller_relevance_score, actionability_score и reason_tags, а не только логировать new_decision.
Перед признанием публикационного контура исправленным проверять не только код, но и БД: есть ли свежие seller_decision=publish и видит ли их publisher_v2.
Ручной emergency bridge можно использовать только для восстановления/диагностики, но он не должен оставаться в cron или wrapper-цепочке.
Расчётная инфографика, PNG и PDF должны генерироваться только из calculation_result JSON. Запрещено подставлять цифры через промпт в image generation model.
AI может формулировать короткий редакционный вывод («экономика рабочая/рискованная»), но не должен рисовать комиссии, остатки, проценты, таблицы, графики и подписи финансовых блоков.
Каждая инфографика должна сверяться с текстовым расчётом: цена, себестоимость, комиссия, налог, НДС, остаток, лучший/худший сценарий и предупреждение о неучтённых расходах обязаны совпадать.
Quota fallback и watchdog являются механизмами минимальной нормы, а не ограничителями публикаций. Запрещено вручную переводить publish в digest только потому, что дневной минимум уже выполнен.
Official GitHub JSON — основной путь официальных каналов. Новые official fetcher-ы не плодить: existing GitHub Action должен отдавать два файла: tg_posts.json и official_marketplace_posts.json.
Если official JSON успешно прочитан и содержит посты, прямой Telegram fallback на VPS должен пропускаться, чтобы не тратить время и не шуметь ошибками No route to host.
official_signal_bridge обязан группировать несколько сигналов одного official-поста в одну новость; api/logistics/tariff/marking по одному post_id не должны создавать несколько одинаковых публикаций.
Аудиодайджест обязан иметь preview-режим без публикации. Любые правки текста сначала проверять через run_audio_digest_preview.sh.

## 4. Известные баги, риски и технический долг
max_bot_polling.py перегружен: 3923 строки, 9 build_marketplace_answer_v2, несколько guard/wrapper слоёв.
WB спецсхема kgvpSupplierExpress 3% может выглядеть как базовая ставка — надо отделить base/special.
Ozon 5/12 выглядит малым, но это стандартный marketplace_service_rate; нужна чёткая формулировка.
Category matching недостаточен: широкие запросы нужно уточнять через UX, а не считать по случайной категории.
Кнопка/индикатор «думаю / считаю» ещё не реализована.
Нужен watchdog: если 2-3 часа есть сырьё, но нет обычных публикаций, админ должен получить MAX-alert. Нельзя узнавать о молчании вечером вручную.
Нужен quota fallback в publisher: если publish нет, а дневная норма не выполнена, брать strong digest/evergreen/backlog, а не молчать.
Hard-ignore рекламного мусора пока базовый: нужно расширять список признаков рекламы, партнёрок, крипты, реферальных ссылок и бюллетеней.
Логи collector.log могут содержать старые строки seller_filter_dryrun; живой код проверять grep по файлам, а не только tail по историческому логу.
Инфографика пока не реализована: нужно выделить структурированный calculation_result JSON из текущего текстового расчёта Seller Helper, иначе renderer будет нечем надёжно кормить.
Риск AI-картинок: модели могут менять числа, путать схемы FBY/FBS/DBS/Express, искажать проценты и создавать ложную финансовую информацию. Для Seller Helper это недопустимо.
Технический риск renderer-а: нужно проверить кириллицу, шрифты, размеры PNG для MAX, PDF A4, очистку временных файлов и стабильность Playwright/Chromium на сервере.
Оставшийся риск v7.2: токены GitHub/MAX могли светиться в рабочих выводах. После стабилизации нужно ротировать токены и проверить collector/publisher/admin alert.
Quarantine /opt/newsbot_v2/_quarantine_cleanup_20260518_163308 занимает 5.0G. Удалять только после 1-2 спокойных циклов cron и дополнительной проверки backup-ов.
audio_digest_text_cleaner теперь принимает короткие выпуски от AUDIO_DIGEST_MIN_CLEAN_CHARS=180; это безопасно для тихих дней, но требует наблюдения качества финального аудио.
official_signal_monitor пока строгий: свежие official posts могут не давать сигналов. Это нормально, но качество классификации official-сигналов остаётся P1.

## 5. Устаревшее, запрещённое и изменённое
Не писать публично технические формулировки «official layer», «diff-проверка», «открой админку».
Не раскрывать доступ по chat_id.
Не использовать Ozon Select как источник пользовательского расчёта.
Не считать новость/TG-сигнал автоматическим изменением тарифа.
Не обещать точную прибыль, пока нет логистики, возвратов, хранения, рекламы и эквайринга.
Не запускать сравнение площадок без category matching.
Запрещено считать dry-run безопасным рабочим режимом публикаций. Это только временная репетиция, не production.
Запрещено оставлять temporary promoter в run_regular_v2.sh после аварийного восстановления.
Запрещено публиковать stale publish-кандидаты старше рабочего окна без повторной проверки; старые хвосты переводить в digest.
Запрещено давать рекламному/партнёрскому мусору publish только из-за слов «НДС», «тариф», «маркетплейс», «селлер».
Запрещено использовать нейросетевую генерацию изображений как финальный способ создания расчётной инфографики Seller Helper.
Запрещено отправлять в генератор картинки длинный текст расчёта и ожидать корректную финансовую таблицу. Это допустимо только как визуальный референс, не как production-контур.
Простой matplotlib-график не считается полноценной продуктовой инфографикой: нужен шаблон карточки с выводом, сценариями, предупреждениями и экспортом PNG/PDF.
Не создавать второй official JSON collector на VPS, если существующий official_channel_collector.py уже умеет читать OFFICIAL_JSON_URLS.
Не считать 10 публикаций потолком. Для будней это минимум; для выходных минимум 3. Качественные publish-кандидаты сверх минимума публикуются штатно.
Не оставлять direct Telegram fallback как обязательный шаг official pipeline при живом GitHub JSON.
Не запускать run_audio_digest.sh вручную для preview: он синтезирует и публикует. Для проверки текста использовать только run_audio_digest_preview.sh.

## 6. Идеи из внешних систем и будущие модули
MPSTATS — ориентир по ценности аналитики, но не шаблон тяжёлого интерфейса.
GitHub scouting design/card analytics — провести аудит open-source инструментов перед подключением.
OfferDoctor — маркетинговый модуль оффера, карточки, УТП и инфографики внутри Seller Helper.
Docobrazec — юридический document engine; персональные данные остаются в Docobrazec.
AI marketplace trends — копить в RAG как тренды, не смешивать с тарифами.
Infographic Renderer — новый модуль Seller Helper: HTML/CSS или SVG-шаблоны расчётных карточек, автоматические bar cards/диаграммы, экспорт PNG/PDF через Playwright/Chromium.
Сравнение площадок должно получить отдельный шаблон инфографики: один товар, одинаковая цена/себестоимость/налог, карточки WB/Ozon/Яндекс, лучший/худший остаток, риск дополнительных расходов.
GitHub/open-source scouting использовать как поиск кирпичей: Playwright examples, HTML-to-image/PDF, SVG chart libraries, invoice/report templates. Не искать готовый продукт «под Seller Helper», а собрать свой лёгкий renderer.

## 7. Поэтапный план разработки v7.1
Этап 0: стабилизировать боевое ядро, Ozon Select test_only, standard Ozon layer, stable backup.
Этап 1: вести паспорт как живую структуру Done/Active/Deprecated/Backlog.
Этап 2: безопасно рефакторить max_bot_polling.py с тестами и сохранением поведения.
Этап 3: уточнение категорий и схем, WB base/special, кнопки выбора категории.
Этап 4: полная юнит-экономика: логистика, возвраты, хранение, эквайринг, реклама.
Этап 5: админка источников и cron health.
Этап 6: Legal RAG, Docobrazec API, OfferDoctor.
Этап 7: рост, монетизация, подписка после метрик.
Этап 0.1: закрыть публикационный watchdog и quota fallback, чтобы канал не мог молчать при наличии сырья.
Этап 0.2: вынести live seller_filter и stale guard в понятные конфигурационные параметры/админский статус.
Этап 0.3: добавить dashboard здоровья источников: TG JSON freshness, raw items, inserted, publish/digest/ignore, published today.
Этап 0.4: подготовить calculation_result JSON как единый контракт между расчётом Seller Helper, текстовым ответом и будущей инфографикой.
Этап 1.1: сделать MVP инфографики по одному расчёту: одна площадка, несколько схем, PNG-карточка, сверка цифр с текстовым ответом.
Этап 1.2: добавить PDF-экспорт той же карточки в A4 и кнопку скачивания/отправки в MAX.
Этап 2.1: после category matching сделать отдельный шаблон сравнения площадок WB/Ozon/Яндекс; не запускать сравнение, пока категории по площадкам не подтверждены.

## 7.1 Актуальный план после safe point v7.2 от 18.05.2026
Эта вставка уточняет поэтапный план v7.1 после закрытия технического пожара NEWSBOT v2 и аудиодайджеста.
P0 / наблюдение: дать cron спокойно пройти вечерний signal_digest, audio_digest, ночную очистку и утренний collector/publisher/watchdog; утром проверить логи без ручного publisher.
P0 / cleanup: после 1-2 стабильных циклов удалить quarantine 5.0G, предварительно сохранив нужные backups и убедившись, что активный проект работает из /opt/newsbot_v2.
P0 / безопасность: ротировать засвеченные GitHub/MAX токены, обновить .env и проверить отправку publisher/admin alert без вывода секретов.
P0 / паспорт: сохранить v7.2 как новый рабочий документ и использовать его как baseline для следующих блоков разработки.
P1 / качество official: улучшать official_signal_monitor и reason_tags так, чтобы важные API/тарифы/логистика/штрафы шли в publish, а маркетинговые official-посты уходили в digest/ignore.
P1 / админский статус: добавить dashboard здоровья source pipeline: TG JSON freshness, official JSON freshness, raw items, inserted, decisions, published today, last publisher/watchdog status.
P1 / Seller Helper product: начать MVP infographic_renderer только после сохранения safe point: calculation_result JSON → PNG карточка → PDF → кнопки в MAX.

## 8. Backlog v7.1: P0 / P1 / P2 / P3

## 8.1 Backlog v7.2: обновление статусов после 18.05.2026
Статусы ниже дополняют таблицу Backlog v7.1 и фиксируют перенос части аварийных задач в Done.
DONE: watchdog молчания публикаций создан и добавлен в cron: run_newsbot_watchdog.sh 27,57 7-21.
DONE: quota fallback добавлен в publisher_v2.py; цели по дням недели: PUBLISH_WEEKDAY_TARGET=10, PUBLISH_WEEKEND_TARGET=3.
DONE: dry-run lifecycle частично закрыт: SELLER_FILTER_MODE=keyword, SELLER_FILTER_LIVE=1; live-write решений в БД подтверждён collector log.
DONE: official GitHub JSON подключён через OFFICIAL_JSON_URLS; GitHub Action отдаёт official_marketplace_posts.json; direct TG fallback стал fallback-only.
DONE: official_signal_bridge.py создан, поставлен в cron и обновлён до grouped logic: 4 raw official signals → 3 grouped items в dry-run.
DONE: audio digest style v7.2: seller-check cleanup, 24 endings, short safe cleaner, preview script.
P0: наблюдение cron до следующего утра и проверка logs/publisher.log, collector.log, watchdog.log, official_signals.log, signal_digest.log, audio_digest.log.
P0: ротация GitHub/MAX токенов после стабилизации, без публикации .env и секретов в логах/чатах.
P0: удалить quarantine 5.0G после подтверждения стабильности и сохранения нужных backup-ов.
P0: начать calculation_result JSON для Seller Helper как контракт для текста/PNG/PDF.
P1: MVP infographic_renderer PNG для одного расчёта, затем PDF A4 и кнопки «Инфографика / Скачать PNG / Скачать PDF».
P1: official signal quality tuning и админский health dashboard источников.
P2: сравнение площадок и расширенные PDF-отчёты только после category matching.

## 9. Definition of Done v7.1
Каждая новая задача имеет место: Done / Active / Deprecated / Backlog.
Каждая правка кода имеет backup, py_compile, тест и rollback.
Тарифные изменения указывают source_file, fee_type, source_status, valid_from и бизнес-правило.
Пользовательский ответ честно пишет источник ставки, что учтено и что не учтено.
MAX-доступ не смешивает user_id и chat_id.
Персональные данные не попадают в RAG.
Сравнение площадок не включается без подтверждения категории.
Для публикационного контура DoD: grep по живому коду не показывает seller_filter_dryrun/promote_publish_candidates.py в боевой цепочке.
DoD live-фильтра: после collector через wrapper видно seller_filter_live applied, а в БД появляются/обновляются seller_decision, seller_relevance_score, actionability_score.
DoD publisher: stale publish guard применён, старые publish-хвосты не публикуются, pending publish содержит только свежие кандидаты.
DoD качества канала: будни минимум 10 публикаций, выходные/праздники минимум 2-3 или админский alert с причиной невыполнения нормы.
DoD инфографики: PNG/PDF строятся из calculation_result JSON, а не из AI-промпта; все цифры совпадают с текстовым расчётом; тест проходит на Ozon/WB/Яндекс и на нескольких схемах.
DoD renderer-а: Playwright/Chromium или альтернативный renderer установлен, работает из сервиса, поддерживает кириллицу, создаёт PNG и PDF, очищает временные файлы и логирует ошибки без персональных данных.
DoD сравнения площадок: инфографика сравнения включается только после category matching и пользовательского подтверждения категорий; иначе показывается честное уточнение, а не ложное «где выгоднее».
DoD продуктовой ценности: у пользователя есть кнопки «Инфографика», «Скачать PNG», «Скачать PDF»; результат можно переслать, сохранить и использовать как визуальный отчёт по расчёту.
DoD v7.2 публикационного контура: health-check показывает cron active, py_compile OK, publish pending пустой или осознанный, published_today соответствует минимуму/сверх минимума, БД integrity_check ok.
DoD official JSON: official_channel_collector.py пишет json posts parsed и direct official TG fallback skipped при живом JSON; t.me errors не должны быть обязательной частью обычного cron.
DoD grouped bridge: dry-run показывает raw signals >= groups; одна official-тема не создаёт несколько одинаковых news items.
DoD audio digest: run_audio_digest_preview.sh проходит без bad phrases; cleaner не падает на коротком валидном выпуске; run_audio_digest.sh не запускать вручную как preview.
DoD weekday/weekend target: в будни daily_target=10, в выходные daily_target=3; это минимум fallback/watchdog, не публикационный cap.

## 10. Решения и диагностика 14.05.2026

## 10.1. Guard по широким запросам
«шампунь» → уточнение, не считать.
«шампунь для волос» → разрешить расчёт.
«чайник» → уточнение, не считать.
«чайник заварочный» → разрешить расчёт.
Ozon-specific shampoo guard не должен блокировать «шампун» + «волос».

## 10.2. Ozon Select и ставки
Ozon Select содержит commission_only строки вроде «Шампунь для волос» 9/11, но source_status=test_only.
Не переводить Ozon Select в usable.
Не заменять standard marketplace_service_rate на Select без отдельного подтверждённого источника.
5/12 по standard layer могут быть актуальной сервисной ставкой; текст ответа должен объяснять, что это не полный расчёт расходов.

## 10.3. Аудит max_bot_polling.py

## 10.4. Диагностика и safe point 17.05.2026: молчание новостей, dry-run и нормальная сборка публикаций
Статус: авария молчания обычных новостей закрыта. Корень проблемы — seller_filter_dryrun в боевой цепочке: фильтр видел publish-кандидаты, но не записывал seller_decision=publish в базу, поэтому publisher_v2 видел pending loaded=0 и молчал.
Причина была не в отсутствии новостей: нормальный запуск через run_collector_v2.sh с .env давал TG JSON news=108 и Fetched raw news=240.
Аварийный promote_publish_candidates.py использовался только для восстановления и доказательства причины; после проверки убран из run_regular_v2.sh.
Live seller_filter перенесён в db.py вокруг add_to_queue_batch: решения фильтра становятся боевыми полями seller_decision, seller_relevance_score, actionability_score и reason_tags.
SELLER_FILTER_LIVE_LOOKBACK_HOURS установлен в 8 часов; db.py имеет такой же безопасный default, чтобы старые новости не оживали как publish.
publisher_v2.py получил stale publish guard: перед загрузкой pending он переводит publish-кандидаты старше окна в digest.
seller_filter.py получил hard-ignore для рекламного и партнёрского мусора: «для наших резидентов», WhiteBird, signup/refid, Bybit, торговые сигналы, бюллетени и похожие паттерны.
Аудиодайджест очищен от навязчивого блока «что проверить селлеру» и получил вариативные концовки; отдельный тестовый/боевой выпуск 15.05.2026 подтвердил чистку текста и публикацию в MAX.
Главный вывод v7.1: dry-run — полезный диагностический режим, но опасен в production. Он должен жить ограниченно по времени и завершаться обязательной проверкой live-write в БД.

## 10.5. Решение 18.05.2026: инфографика Seller Helper и экспорт PNG/PDF
Статус: принято как новое продуктовое направление v7.1. Реализация ещё не сделана; задача внесена в поэтапный план и Backlog с приоритетами P0/P1/P2.
Главный вывод: расчётная инфографика должна резко повысить продуктовую ценность Seller Helper, потому что селлер видит не только текстовый расчёт, но и визуальный отчёт: цену, комиссию, себестоимость, налог, остаток, лучший и худший сценарий.
Архитектурное правило: AI-генерация изображений не используется для финальных расчётных карточек. Причина — риск искажения цифр. Production-контур должен быть детерминированным: расчёт → JSON → шаблон → renderer → PNG/PDF.

## 10.5.1. Целевая архитектура модуля

## 10.5.2. Первые шаблоны инфографики
1) Один товар / одна площадка / несколько схем: ключевые цифры, таблица схем, структура цены, лучший и худший сценарий, ограничения расчёта.
2) Один товар / сравнение схем внутри площадки: компактные карточки FBY/FBO/FBS/Express/DBS или аналогичных схем, чтобы селлер быстро видел выгодный и рискованный вариант.
3) Один товар / сравнение площадок: WB/Ozon/Яндекс по одинаковой цене, себестоимости и налоговому режиму. Включать только после category matching, чтобы не сравнивать случайные категории.
4) PDF-отчёт: версия для скачивания, пересылки партнёру или сохранения как расчётного обоснования перед закупкой.

## 10.5.3. Приоритеты реализации

## 10.5.4. Технические запреты и контроль качества
Запрещено: отправлять расчёт в генератор изображений и использовать полученную картинку как финансовый отчёт.
Запрещено: позволять LLM менять или пересчитывать комиссии, проценты, остатки и названия схем.
Обязательно: сверять PNG/PDF с calculation_result JSON и текстовым ответом; при несовпадении инфографика не отправляется.
Обязательно: хранить/логировать только технический ID расчёта и обезличенные данные; не писать персональные данные, токены и .env в файл инфографики или лог.

## 10.6 Контрольная точка v7.2 от 18.05.2026: восстановление NEWSBOT v2 и усиление official/audio контуров
Статус: технический пожар закрыт. Публикационный контур NEWSBOT v2 восстановлен штатными механизмами, проверен финальным health-check и зафиксирован как новый safe point.

## 10.6.1. Что было причиной аварии
Проблема длилась около недели из-за сочетания dry-run/guard-поведения, дублей и отсутствия нормального добора publish-кандидатов. Фильтр мог видеть publish, но publisher получал пустой pending или дубли переводились не туда.
Дополнительно была проблема «тупого guard»: дубли помечались так, что могли мешать очереди, но не очищали поток как duplicate. Это исправлено политикой duplicate вместо digest.

## 10.6.2. Сделано в NEWSBOT v2
db.py: добавлен revive старых неопубликованных publish-кандидатов через controlled refresh created_at; добавлен лог Publish pending after write; live seller_filter updates пишутся в БД.
publisher_v2.py: duplicate guard переводит повторы в seller_decision=duplicate, is_published=1; quota fallback добирает минимум до weekday/weekend target; publisher не ограничивает публикации сверх минимума.
collector_v2.py / .env: SELLER_FILTER_MODE=keyword, SELLER_FILTER_LIVE=1, SELLER_FILTER_LIVE_LOOKBACK_HOURS=8. Dry-run больше не остаётся в production-конфиге.
newsbot_watchdog.py: добавлен в cron и проверяет published_recent, published_today, pending_publish, strong_digest и silence_hours.
PUBLISH_WEEKDAY_TARGET=10, PUBLISH_WEEKEND_TARGET=3, NEWSBOT_TZ=Europe/Moscow. Выходные 2-3 публикации трактуются как минимум 3 для fallback/watchdog.

## 10.6.3. Official GitHub JSON и official bridge
Решение: не создавать второй сборщик, а расширить существующий GitHub Action: tg_posts.json для обычных TG-каналов и official_marketplace_posts.json для official sources Ozon/WB/Яндекс.
official_channel_collector.py читает OFFICIAL_JSON_URLS из .env; GitHub JSON стал основным official source; direct Telegram fallback пропускается при json_seen > 0.
official_signal_monitor.py работает как строгий фильтр: если свежие official posts маркетинговые/информационные, inserted official signals=0 — это нормальное состояние.
official_signal_bridge.py создан и поставлен в hourly cron через run_official_signals_v2.sh; затем обновлён до grouped-логики: несколько signal_type одного official-поста становятся одной news item.

## 10.6.4. Аудиодайджест v7.2
audio_digest_story_builder.py: расширены bad_seller_check_patterns, смягчены фразы про остатки/интеграции, добавлена voice cleanup для сЭллер/сЭллерская, концовки расширены до 24 вариантов.
audio_digest_text_cleaner.py: порог короткого очищенного текста стал AUDIO_DIGEST_MIN_CLEAN_CHARS=180; короткий валидный выпуск accepted with warning, а не ломает cron.
run_audio_digest_preview.sh добавлен для preview текста без SaluteSpeech, без MP3 и без отправки в MAX.

## 10.6.5. Финальный health-check
Cron active: run_collector_v2.sh, run_regular_v2.sh, run_signal_digest.sh, run_audio_digest.sh, run_newsbot_watchdog.sh, run_official_signals_v2.sh.
Compile OK: db.py, collector_v2.py, publisher_v2.py, seller_filter.py, official_channel_collector.py, official_signal_monitor.py, official_signal_bridge.py, newsbot_watchdog.py, signal_digest.py, audio_digest_story_builder.py.
Today counts на момент safe point: publish=11 опубликовано, publish pending пусто; digest=6, duplicate=3, ignore=26.
DB integrity: news_queue.db ok; unified_tariffs.db ok.
Размеры: активный /opt/newsbot_v2 около 1.6G; quarantine около 5.0G. Quarantine не удалять до подтверждения стабильности.

## 10.6.6. Что не трогать и что сделать следующим
Не гонять publisher вручную без причины; дать cron пройти полный вечерний и утренний цикл.
Не удалять quarantine сразу; удалить после стабильного цикла и проверки, что backups больше не нужны.
Следующий продуктовый блок после стабилизации: Seller Helper infographic PNG/PDF через calculation_result JSON и deterministic renderer.
Отдельный security-хвост: ротировать засвеченные GitHub/MAX токены и проверить, что новые токены не выводятся в чат/логи.

## 11. Реестр переноса v6.7 в структуру v7.0 / v7.1 / v7.2
Реестр показывает, что все крупные блоки v6.7 сохранены и перенесены в смысловые разделы. Ниже после реестра идёт полная содержательная переноска исходных блоков v6.7.

## 12. Полная содержательная переноска v6.7, разложенная по модулям
Это не хронологическое приложение, а база знаний паспорта: исходные материалы v6.7 сохранены внутри тематической структуры. При последующих версиях эти пункты можно переносить в Done/Backlog/Deprecated.

## 12.1. История safe points и вводные версии

## Источник v6.7: 0. Титульная карточка, история версий и вводные v6.7

## ПАСПОРТ И ТЗ ЭКОСИСТЕМЫ
«Инсайдер Селлер» / NEWSBOT v2 / Seller Helper
Версия 6.7. Safe Point: 13.05.2026, вечер
Важное дополнение версии 6 от 29.04.2026
Версия 5 сохраняется как базовая история проекта. В версии 6 не переписываются выполненные работы: добавлен отдельный блок уточнений, где перечислены устаревшие или изменённые пункты, а также новый roadmap после запуска RAG/Helper bridge и вечернего монитора изменений.
Ключевое правило v6: числовые комиссии и расчёты остаются в clean_commissions, а RAG Store используется для официальных текстов, оферт, кейсов, регуляторики, новостей и объяснительного контекста. Вечерний монитор публикует только строгий отфильтрованный отчёт, а не все найденные сигналы.
Короткий вывод. Проект больше не является только новостным ботом. Это экосистема для селлеров: MAX-канал «Инсайдер Селлер» собирает доверие и трафик, NEWSBOT v2 работает как data/admin core, Seller Helper превращает новости и тарифные сигналы в практическое действие — проверку комиссий, будущий расчёт прибыли и сравнение площадок.

## 12.2. Архитектура и назначение экосистемы

## Источник v6.7: 1. Назначение и границы экосистемы

## 1. Назначение и границы экосистемы
Экосистема «Инсайдер Селлер» строится как связка новостного MAX-канала, пользовательского Seller Helper Bot, единой тарифной базы, будущей админки, лендингов и RAG-базы знаний. Главная ценность — не просто новости, а прикладная аналитика для селлеров: комиссии, тарифы, изменения оферт, маржа, юридические риски и вывод «что делать дальше».
Главная точка входа. Основной вход в экосистему — новостной MAX-канал. Seller Helper — не отдельный внешний продукт на первом этапе, а прикладной инструмент внутри экосистемы, к которому ведёт CTA после новостей.

## Источник v6.7: 2. Итоговая архитектура

## 2. Итоговая архитектура

## 2.1. Data/admin core NEWSBOT v2
RSS-источники + TG JSON
↓
collector_v2.py
↓
news_queue.db / таблица news
↓
publisher_v2.py
↓
MAX-канал
↓
один CTA в Seller Helper после пачки опубликованных новостей

## 2.2. Seller Helper
MAX пользователь
↓
/opt/helperbot/max_bot_polling.py
↓
/opt/newsbot_v2/data/unified_tariffs.db
↓
ответ по комиссии / тарифу / будущему расчёту прибыли

## Источник v6.7: 15. Дополнение v5 от 28.04.2026: расширение экосистемы без отмены прежнего паспорта

## 15. Дополнение v5 от 28.04.2026: расширение экосистемы без отмены прежнего паспорта
Все положения версии 4 сохраняются. Дополнение v5 не отменяет ранее зафиксированные требования по NEWSBOT v2, Seller Helper, единой тарифной базе, мониторингу комиссий, налоговому блоку, монетизации и правилам дальнейших правок. Новые пункты уточняют архитектуру и ближайший рабочий фокус.

## 15.1. Целевая пользовательская архитектура
MAX-канал «Инсайдер Селлер»
↓
Seller Helper mini app — главный рабочий кабинет экосистемы
├─ Комиссии и маржа
├─ Юридический модуль Docobrazec
├─ Маркетинговый модуль Offer Doctor
├─ Мониторинг оферт и тарифов
└─ Будущий МАРК-разведчик

## 15.2. Веб-витрины и лендинги
Веб-лендинги не должны плодиться без необходимости. На ближайшем этапе не создаётся отдельный лендинг для новостного канала «Инсайдер Селлер» и не создаётся отдельный лендинг для Seller Helper как самостоятельной внешней точки входа. Главный вход остаётся в MAX-канале, а главный рабочий инструмент — Seller Helper mini app.

## 15.3. Docobrazec как юридический модуль внутри Seller Helper
Docobrazec.ru сохраняется как юридическая витрина и домен. Но пользовательские функции юридического конструктора должны постепенно переноситься или дублироваться внутри Seller Helper mini app, чтобы селлер решал типовые юридические задачи без выхода из общего кабинета.
Первый целевой документ для селлеров: досудебная претензия селлера к маркетплейсу.
Типовые сценарии: удержания, штрафы, спор по возврату, невыплата, блокировка товара, блокировка кабинета, изменение условий, спор по оферте.
Юридический модуль должен работать как помощник по подготовке типового документа и первичному разбору, а не как замена юристу.
RAG-слой должен опираться на оферты маркетплейсов, правовые акты, судебные кейсы, шаблоны документов и историю изменений условий.

## 15.4. Offer Doctor как маркетинговый модуль Seller Helper
Offer Doctor уже имеет готовый лендинг и mini app. Поэтому его не нужно создавать заново. Стратегическая задача — сделать его доступным внутри Seller Helper как маркетинговый модуль: пользователь посчитал маржу, увидел проблему экономики товара и может сразу перейти к улучшению оффера, карточки, УТП и текста.

## 15.5. Единая RAG-база и LLM-контур
Единая RAG-база должна быть общей для Seller Helper, юридического модуля Docobrazec, Offer Doctor и будущих модулей. DeepSeek API может использоваться как LLM-контур для классификации, генерации, анализа и RAG-ответов с учётом купленного доступа на 10 млн токенов. При этом база, документы, источники, тарифы, оферты, шаблоны и история изменений должны храниться у нас, а не в модели.

## Источник v6.7: 17. Обновлённая короткая формулировка для будущих чатов

## 17. Обновлённая короткая формулировка для будущих чатов
Мы строим экосистему «Инсайдер Селлер»: MAX-канал как главный источник трафика и доверия, NEWSBOT v2 как data/admin core, Seller Helper mini app как главный рабочий кабинет и мозг проекта. Seller Helper считает комиссии, маржу и налоговый блок, ведёт пользователя к юридическому модулю Docobrazec, маркетинговому модулю Offer Doctor и будущим аналитическим инструментам. Docobrazec.ru остаётся веб-витриной юридического конструктора, а его функции постепенно включаются в Seller Helper. Offer Doctor уже имеет лендинг и mini app, но стратегически должен быть доступен внутри Seller Helper как маркетинговый модуль. Отдельный лендинг для новостного канала или Seller Helper на ближайшем этапе не создаётся. Ближайший рабочий фокус — кнопка «Читать полностью в канале» под новостями, чтобы пользователь мог читать полный текст внутри MAX без перехода в Telegram или внешний источник.

## 12.3. NEWSBOT v2 и публикационный контур

## Источник v6.7: 3. Что изменилось 27.04.2026

## 3. Что изменилось 27.04.2026
Seller Helper подключён к NEWSBOT v2 через CTA после пачки публикаций.
CTA отправляется один раз после завершения publisher_v2.py, если опубликована хотя бы одна новость.
Кнопка CTA принята: «[кнопка] Проверить комиссию и прибыль».
Ссылка на Helper: https://max.ru/id771812324702_2_bot.
Тестовая отправка CTA прошла успешно: ENABLE_SELLER_HELPER_CTA=true, SELLER_HELPER_BOT_URL задан, channel_id=-73160979033512, sent=True.
В Seller Helper обновлён /start: теперь человек понимает, что бот умеет, как писать запрос и какие ограничения есть.
Запрос без площадки больше не раскрывает все маркетплейсы сразу, а предлагает выбрать одну площадку и объясняет бесплатный/платный слой.
Ozon переведён на правильный слой marketplace_service_rate; Ozon Select исключён из основного ответа.
Зафиксирован налоговый нюанс: налог считается с цены продажи / дохода от реализации, а не с суммы после удержаний маркетплейса.

## Источник v6.7: 4. NEWSBOT v2: текущая логика и требования

## 4. NEWSBOT v2: текущая логика и требования
NEWSBOT v2 отвечает за сбор, оценку, подготовку и публикацию новостей. После стабилизации publisher доверяет collector: collector выставляет seller_decision и score, publisher сортирует уже одобренные publish items и публикует. Это снижает риск замкнутого круга «то слишком мусорно, то ничего».

## Источник v6.7: 16. Ближайший рабочий этап: кнопка «читать полностью» в MAX-канале

## 16. Ближайший рабочий этап: кнопка «читать полностью» в MAX-канале
Работу 28.04.2026 начинаем с функции чтения полного текста новости внутри MAX-канала. Это не отменяет текущую CTA-кнопку в Seller Helper, а добавляет второй полезный сценарий под новостью.

## 16.1. Требуемые поля в базе / модели новости

## 16.2. Definition of Done для кнопки
Кнопка «Читать полностью в канале» появляется только у новостей с full_text_available=true.
Нажатие публикует полный текст в канал без перехода во внешний источник.
Повторное нажатие не дублирует полный текст.
Ссылка на источник сохраняется внизу полного текста как подтверждение происхождения материала.
Существующая кнопка «Проверить комиссию и прибыль» продолжает работать и не ломается.
Если полный текст слишком длинный, он должен быть разбит на несколько сообщений с понятной нумерацией: часть 1/2, 2/2.
В логах фиксируется успешная публикация или причина отказа: нет полного текста, уже опубликовано, ошибка API, слишком длинное сообщение.

## 16.3. Предлагаемый порядок работ на сервере
Сделать timestamp backup файлов publisher.py, publisher_v2.py, db.py и базы news_queue.db перед правками.
Проверить, какие поля с полным текстом уже есть в таблице news и какие реально заполняются collector_v2.py.
Если нужных полей нет — добавить миграцию базы без удаления существующих данных.
Добавить функцию формирования кнопки «Читать полностью в канале».
Добавить обработчик callback или другой поддерживаемый MAX-механизм раскрытия полного текста.
Добавить защиту от повторной публикации полного текста.
Протестировать на одной новости из TG-источника и одной новости из RSS-источника.
После успешного теста включить функцию в рабочий publisher_v2.py.

## Источник v6.7: 18. Техническое дополнение к версии 5: full article и чистые дайджесты

## 18. Техническое дополнение к версии 5: full article и чистые дайджесты
Статус: реализовано и проверено на сервере 28.04.2026. Версия паспорта не меняется; это структурированное дополнение к версии 5 и не отменяет ранее зафиксированные планы, архитектуру и roadmap.

## 18.1. Что реализовано в MAX-канале «Инсайдер Селлер»
Добавлена кнопка «Читать полностью» к новостям, у которых в базе есть достаточно длинный raw_text.
Кнопка относится именно к NEWSBOT v2 и MAX-каналу «Инсайдер Селлер», а не к Seller Helper Bot.
При нажатии полный текст раскрывается в том же исходном посте MAX: короткая версия заменяется расширенной версией без публикации отдельной копии.
Ссылка на источник сохраняется внизу полного текста как подтверждение происхождения материала.
Главная продуктовая ценность: пользователь может прочитать материал внутри MAX, без перехода в Telegram или внешний источник, что особенно важно при ограниченном доступе к Telegram из РФ.

## 18.2. Техническая схема full article
Рабочая логика:
publisher_v2.py публикует короткую новость → send_message() добавляет callback-кнопку «Читать полностью» → publisher_v2.py сохраняет message.body.mid в news.max_message_id → newsbot-fullarticle.service слушает callback MAX → full_article_callback_worker.py достаёт raw_text по news_id → редактирует исходный MAX-пост через PUT /messages.

## 18.3. Изменённые компоненты и их роли

## 18.4. Новые поля в news_queue.db

## 18.5. Текущий safe point по full article
newsbot-fullarticle.service активен, работает и включён в автозапуск.
full_article_callback_worker.py успешно стартует и пишет в лог: Full article callback worker started. DB=/opt/newsbot_v2/news_queue.db.
Тестовая кнопка «Читать полностью» успешно раскрыла полный текст в том же MAX-посте.
Затронутые файлы проходят py_compile: publisher.py, publisher_imports.py, publisher_v2.py, full_article_callback_worker.py, digest_v2.py.
Перед изменениями и по ходу работы созданы timestamp backup-и файлов и базы news_queue.db.

## 18.6. Дайджесты: что исправлено
Проблема: в дайджесты попадали не чистые заголовки, а заголовок плюс начало статьи, особенно у TG-источников. Это делало дайджесты грязными и менее профессиональными.
Решение: в digest_v2.py добавлена функция clean_digest_title(), которая режет технические хвосты, повтор заголовка, начало второго абзаца и слишком длинные фрагменты.
Строки дайджеста теперь используют короткий очищенный заголовок, а не начало статьи.
Источник выделяется жирным HTML-форматом: <b>[TG:mpgo_ru]</b>.
Заголовки блоков дайджеста переведены с Markdown-style **...** на HTML-bold <b>...</b>, потому что MAX-публикация работает в режиме format="html".
Утренний дайджест больше не должен дублировать одну и ту же новость в блоках «Главное за ночь» и «Сигналы по условиям / тарифам / выплатам».
Оставшиеся отдельные неидеальные TG-заголовки допустимы для MVP и могут быть дожаты отдельным правилом очистки позже.

## 18.7. Что не меняется
Версия паспорта остаётся версией 5; это дополнение не создаёт новую версию документа.
Основная точка входа остаётся MAX-канал «Инсайдер Селлер».
Seller Helper остаётся отдельным инструментом для комиссий, маржи и будущих юридических/маркетинговых сценариев. Он не участвует в раскрытии полного текста новостей.
CTA «Проверить комиссию и прибыль» после пачки публикаций сохраняется и продолжает вести в Seller Helper Bot.
Ранее зафиксированные планы по Docobrazec, Offer Doctor, единой RAG-базе и будущему модулю МАРК не отменяются.

## 18.8. Ближайшие проверки после штатного cron

## 1. Дождаться штатного cron-прогона collector/publisher, не форсируя публикацию искусственно.

## 2. Проверить, что новая боевая новость с длинным raw_text выходит с кнопкой «Читать полностью».

## 3. Нажать кнопку и подтвердить, что исходный пост раскрывается в полный текст без отдельного дубля.

## 4. Проверить journalctl -u newsbot-fullarticle.service и убедиться, что callback обработан без ошибок.

## 5. Проверить последние опубликованные записи в news_queue.db: is_published=1, max_message_id заполнен, full_article_published_at появляется после раскрытия.

## 6. После вечернего/утреннего digest cron убедиться, что дайджесты выглядят аккуратно: чистые заголовки, жирные источники, без дублей между блоками.

## 18.9. Короткая формулировка для будущих чатов по этому safe point

## 28.04.2026 в NEWSBOT v2 реализована функция чтения полного текста новости внутри MAX-канала, а 29.04.2026 условие показа кнопки уточнено: кнопка «Читать полностью» появляется у материалов с raw_text/full_text_* от 300 символов. Callback обрабатывает отдельный systemd-сервис newsbot-fullarticle.service, а полный текст раскрывается в том же MAX-посте без отдельной копии. Также очищены заголовки дайджестов: источники выделяются жирным, блоки используют HTML-bold, длинные TG-хвосты режутся через clean_digest_title(), а утренний дайджест не дублирует одну и ту же новость в «Главное» и «Сигналы».

## Источник v6.7: 19. Дополнение v6 от 29.04.2026: RAG/Helper bridge и надёжный монитор изменений

## 19. Дополнение v6 от 29.04.2026: RAG/Helper bridge и надёжный монитор изменений
Статус: реализовано и проверено на сервере 29.04.2026. Версия 6 не отменяет паспорт v5, а фиксирует новые слои архитектуры, уточнения по устаревшим пунктам и обновлённый roadmap.
Ключевой вывод: проект получил отдельный RAG Store, диагностический мост между тарифной базой и RAG, а также первый рабочий контур вечернего мониторинга изменений условий и тарифов в MAX-канале.

## 19.1. Что не менялось
• Боевой пользовательский Helper Bot не перестраивался: /opt/helperbot/max_bot_polling.py не интегрировался с rag_bridge.py.
• helperbot.service не перезапускался ради bridge и не рисковал рабочим пользовательским контуром.
• Логика NEWSBOT v2, publisher_v2, CTA в Seller Helper и full article callback не переписывались в рамках этой работы.
• Ozon Select не возвращён в основной ответ: правило v5 сохранено — Ozon в боевом расчёте использует стандартный marketplace_service_rate.

## 19.2. Новые и подтверждённые структуры

## 19.3. Блок устаревшей, неверной или изменённой логики из v5
Этот блок не удаляет историю v5, а явно показывает, какие пункты теперь нужно читать с уточнениями версии 6.

## 19.4. Проверенные тесты 29.04.2026

## 19.5. Надёжный вечерний монитор изменений
Цель монитора: каждый вечер публиковать в MAX-канал аккуратный отчёт о надёжных сигналах изменений условий, тарифов, выплат, оферт и регуляторики. Если надёжных сигналов нет, публикуется сообщение, что изменений не обнаружено, с перечислением проверенных направлений.
Текущая схема: signal_monitor.py собирает сырой radar в tariff_signals; signal_digest.py группирует, фильтрует шум, красиво форматирует и публикует только надёжный вечерний отчёт; signal_digest_runs защищает от повторной публикации за тот же день.
Канал не должен получать маркетинговый и операционный шум: витрины, акции, конкурсы, ПВЗ, брошенные корзины, банковская аналитика, обновления интерфейса кабинета, частные кейсы и прогнозные статьи отсекаются строгим фильтром.
Публикуемые типы: сильные сигналы ФАС/регуляторов по маркетплейсам, обновления оферт с датой вступления, реальные изменения тарифов/комиссий. Остальное остаётся в tariff_signals для ручной проверки.

## 19.6. Официальные каналы маркетплейсов как signal layer
Официальные Telegram/MAX-каналы маркетплейсов нужно подключать не как источник числовых комиссий, а как слой official_signal/high.
WB и Яндекс: числовые тарифы остаются в API/DB/export и clean_commissions. Официальные каналы используются только как ранний сигнал изменения оферты, API, логистики, выплат, правил и кабинета.
Ozon: числовые тарифы остаются в официальных Excel-документах и standard marketplace_service_rate. Каналы и новости Ozon используются как сигнал к проверке нового Excel/изменения слоя.
Правило: official_signal/high создаёт задачу проверки, но не меняет расчёт Seller Helper автоматически.

## 19.7. Обновлённый roadmap после safe point 29.04.2026

## 19.8. Короткая формулировка для будущих чатов по v6

## 29.04.2026 в экосистеме «Инсайдер Селлер» проведена ревизия RAG/Helper архитектуры и запущен надёжный вечерний монитор изменений. RAG Store находится в /opt/newsbot_v2/data/rag_store.db и хранит тексты, оферты, кейсы, регуляторику, новости и объяснения; числовые комиссии остаются в /opt/newsbot_v2/data/unified_tariffs.db#clean_commissions. Создан диагностический /opt/helperbot/rag_bridge.py, но он не встроен в боевой max_bot_polling.py. Для Ozon в bridge и в боевой логике используется только fee_type=marketplace_service_rate; Select остаётся test/reference. Созданы signal_monitor.py и signal_digest.py, таблицы tariff_signals и signal_digest_runs, первый монитор опубликован, cron установлен на 22:30 MSK. Старые/неверные пункты v5 не удаляются, но читаются через блок уточнений v6.

## Источник v6.7: 20. Дополнение v6.1 от 29.04.2026: операционный safe point NEWSBOT v2, MAX-правила и переход к Seller Helper

## 20. Дополнение v6.1 от 29.04.2026: операционный safe point NEWSBOT v2, MAX-правила и переход к Seller Helper
Статус: принято и зафиксировано 29.04.2026. Это точечное дополнение к паспорту v6: оно не переписывает архитектуру, а фиксирует закрытые операционные изменения NEWSBOT v2, новые правила работы с MAX API и обновляет ближайший roadmap перед переходом к полноценному Seller Helper.

## 20.1. Что сделано после safe point v6
Аудиодайджест одобрен после теста качества и поставлен в cron на ежедневный запуск в 22:45: /opt/newsbot_v2/run_audio_digest.sh >> /opt/newsbot_v2/logs/audio_digest.log 2>&1.
Цепочка аудиодайджеста зафиксирована как отдельный контур: audio_digest_story_builder.py → audio_digest_salute.py → конвертация свежего WAV в MP3 через ffmpeg → mix_audio_digest_stinger.sh с радионовостной отбивкой → audio_digest_max_publisher.py.
Радионовостная отбивка хранится в /opt/newsbot_v2/audio_digest/assets/radio_stinger.mp3. В тестовом финальном MP3 отбивка наложена фоном на первые секунды с fade-out; публикация в MAX прошла успешно после retry на attachment.not.ready.
Механизм очистки аудиофайлов создан и проверен: /opt/newsbot_v2/cleanup_audio_digest.sh. Cron установлен на 03:20 ежедневно. Лог: /opt/newsbot_v2/logs/audio_cleanup.log.
Правило хранения аудио принято: WAV старше 2 дней удаляются; временные audio_digest_salute_*.mp3 старше 7 дней удаляются; финальные audio_digest_final_*.mp3 старше 30 дней удаляются; пустые директории удаляются.
Кнопка «Читать полностью» расширена: функция has_full_article() в /opt/newsbot_v2/publisher.py теперь показывает кнопку для материалов с raw_text/full_text_* от 300 символов. Короткие обрывки меньше 300 символов кнопку не получают.
Full article механизм не перестраивался: callback-worker, newsbot-fullarticle.service, PUT /messages, max_message_id, full_article_clicks и защита от дублей остаются прежними. Полный текст раскрывается в том же MAX-посте.
CTA Seller Helper не менялся: после пачки публикаций остаётся один общий переход « Проверить комиссию и прибыль» на https://max.ru/id771812324702_2_bot.
Видеодайджест не входит в ближайший roadmap: контур признан слишком тяжёлым и хрупким для текущего этапа.

## 20.2. Новые правила MAX API и guardrails проекта
Правило: все новые правки MAX-интеграции должны сохранять совместимость с актуальной схемой MAX API и не возвращать старые небезопасные паттерны.
Использовать домен platform-api.max.ru для API-запросов.
Токен MAX передавать только через HTTP-заголовок Authorization: <token>. Передача токена через query-параметры запрещена и не должна возвращаться в код.
Не выводить токены и .env целиком в чат, логи, дампы ошибок или паспорт.
Отправку сообщений, CTA и full article раскрытие проводить через уже рабочие обёртки publisher.py / publisher_imports.py, а не через новые ad-hoc requests.
Для внутреннего чтения в канале использовать callback-кнопку «Читать полностью»; внешний URL оставлять как строку источника, а не как главный путь чтения.
PUT /messages используется только для редактирования исходного MAX-поста при раскрытии полного текста; отдельные дубли полного текста не создавать.
Не запускать второй polling/worker вручную. full article работает через newsbot-fullarticle.service; Helper — через helperbot.service.
Учитывать ограничение стабильной работы API: не разгонять публикации и callback-ответы; держать запас ниже 30 rps и использовать retry только там, где он уже нужен, например attachment.not.ready.
Все новые MAX-правки сначала проверять через py_compile и точечный тест, затем ждать штатный cron/боевую публикацию.

## 20.3. Текущий cron после safe point v6.1

## 20.4. Обновлённый roadmap на следующий этап

## 20.5. Короткая формулировка для будущих чатов по v6.1

## 29.04.2026 NEWSBOT v2 доведён до операционного safe point: включён аудиодайджест в cron на 22:45, установлен механизм очистки аудиофайлов на 03:20, расширена кнопка «Читать полностью» для материалов с raw_text/full_text_* от 300 символов, а MAX API-правила зафиксированы как guardrails: token только через Authorization header, platform-api.max.ru, callback для внутреннего раскрытия, PUT /messages для редактирования того же поста, без дублей и без токенов в логах. Видеодайджест отложен как тяжёлый и хрупкий. Следующий рабочий фокус — полноценный Seller Helper: комиссии, маржа, налоговый блок, сравнение площадок и постепенное подключение юридического/RAG слоя.

## Источник v6.7: 23. Дополнение v6.4 от 04.05.2026: официальные источники, админские уведомления и упрощение архитектуры

## 23. Дополнение v6.4 от 04.05.2026: официальные источники, админские уведомления и упрощение архитектуры
Статус: зафиксировано после работ 04.05.2026. Дополнение v6.4 не отменяет паспорт v6.3, а уточняет архитектурные решения, новые документы/скрипты, публичный язык вечернего монитора и ближайший план после выявленных рисков в Seller Helper.
Ключевой вывод: проект должен оставаться максимально простым. Raw-данные и архив официальных источников сохраняются, но боевой расчёт и пользовательские ответы не должны зависеть от хрупкой цепочки лишних витрин, промежуточных слоёв и неочевидных адаптеров.

## 23.1. Что сделано и принято 04.05.2026

## 23.2. Уточнение архитектуры: что является источником истины
Главное правило v6.4: raw-данные можно и нужно сохранять, но боевой контур должен быть простым. Обязательных прослоек должно быть минимум, а роль каждого слоя должна быть понятна.
Решение по rules_documents: таблица не удаляется немедленно, потому что уже хранит полезные фрагменты официальных документов и помогает в поиске/диагностике. Но её роль ограничена: это не обязательная расчётная витрина, а вспомогательный архивно-поисковый слой. В дальнейшем нужно либо упростить её роль, либо заменить на более прозрачный registry + raw files + компактные diff/summary-записи.

## 23.3. Вечерний монитор: новый публичный смысл
Проблема до правки: монитор мог писать «Надёжных изменений за день не обнаружено», хотя в этот день загружались или обновлялись официальные источники. Для подписчика это выглядело как противоречие, а для проекта создавало риск неверного статуса.
Решение v6.4: если официальный источник обновлялся, публичный монитор сообщает не о подтверждённом изменении тарифа, а о факте обновления источников и проверке командой канала.
Новый пример публичного сообщения:
🔎 Вечерний монитор изменений
Условия, тарифы и оферты маркетплейсов · 04.05.2026
⚠️ За день обновлялись официальные источники маркетплейсов.
Это не означает, что тарифы или условия уже изменены в расчётах. Команда канала сверяет обновления с официальными документами.
• Wildberries: оферта продавца — фрагменты: 242, новые: 242.
Если изменения действительно влияют на продавцов, релевантные тарифы и условия будут учтены в Seller Helper после проверки.
Публикуем только проверенные изменения, чтобы не вводить селлеров в заблуждение.

## 23.4. Ozon: административная свежесть и список файлов для ручной проверки
Ozon отличается от WB и Яндекса: WB и Яндекс можно в большей степени проверять через API/официальные страницы, а Ozon требует ручной загрузки официальных Excel/PDF и сверки с сигналами после последней загрузки.
Защита от Ozon Select сохраняется: Ozon Select не используется как боевой источник расчёта. Если строки Select остаются в базе, они должны иметь небоевой статус и не попадать в пользовательские ответы Seller Helper.

## 23.5. Админские уведомления: личный alert вместо публичной технической тревоги
Решение: техническое сообщение «Проверь админку» должно приходить администратору в личный MAX-чат, а не публиковаться в канале. В публичном канале остаётся спокойная редакционная формулировка о проверке официальных источников командой.

## 23.6. Качество разметки официальных документов и случайная загрузка WB-оферты
В ходе проверки выявлен важный риск: через админку можно ошибочно загрузить документ не в тот маркетплейс. Пример: оферта Wildberries была загружена как Ozon-документ. Это могло приводить к ложным совпадениям, когда Ozon-запросы находили текст Wildberries.
Принятое правило: документ должен иметь корректные marketplace, document_name и source_url. rules_lookup должен иметь marketplace guard и не подмешивать чужие оферты в ответы по другой площадке. Ошибочно размеченные документы нужно либо исправлять миграцией, либо исключать из lookup до ручной проверки.
Для админки желательно добавить защиту на этапе загрузки: предупреждение, если текст документа явно содержит маркер другого маркетплейса, например «Wildberries/Вайлдберриз» внутри Ozon-загрузки.

## 23.7. Seller Helper: что зафиксировано и что отложено
Ближайшее техническое правило по Seller Helper: сначала восстановить и подтвердить стабильный боевой helperbot.service после экспериментов с кнопками, затем отдельно проектировать кнопки уточнения категории. Не внедрять тяжёлые изменения в конце рабочего окна.

## 23.8. Блок устаревшей, неверной или изменённой логики после v6.4

## 23.9. Актуальный roadmap после v6.4

## 23.10. Короткая формулировка для будущих чатов по v6.4

## 04.05.2026 принят safe point v6.4: архитектуру NEWSBOT v2 / Seller Helper нужно упрощать, а не плодить обязательные прослойки. rules_documents остаётся вспомогательным архивно-поисковым слоем, но не источником истины для расчётов. Вечерний монитор теперь учитывает обновления официальных источников и не пишет «изменений нет», если официальный документ обновлялся. Публичный текст сообщает, что команда сверяет обновления и учитывает релевантные изменения в Seller Helper после проверки. В админке добавлен блок свежести источников, Ozon требует ручной загрузки официальных Excel/PDF, а alert «Проверь админку» приходит администратору в личный MAX-чат через Seller Helper Bot. Одиночные расчёты с НДС работают; сравнение площадок и кнопки уточнения категорий отложены до безопасной реализации.

## Источник v6.7: 24. Дополнение v6.5 от 06.05.2026: плотность новостей, CATEGORY GUARD V2 и RISK INSIGHTS V1

## 24. Дополнение v6.5 от 06.05.2026: плотность новостей, CATEGORY GUARD V2 и RISK INSIGHTS V1
Статус: зафиксировано после работ 05-06.05.2026. Дополнение v6.5 не переписывает паспорт v6.4, а продолжает его структуру: закрытые точки вынесены в выполненное, изменённая логика — в блок устаревшего, новый рабочий фокус — в roadmap.
Ключевой вывод: экосистема получила новый safe point. NEWSBOT v2 снова даёт достаточную плотность новостей за счёт исправленного внешнего TG fetcher и увеличенного лимита загрузки. Seller Helper перестал быть только калькулятором и стал прикладным помощником: он защищает от явно ошибочной категории, считает налоговый/НДС-блок и добавляет вывод по риску товара.

## 24.1. Что сделано после v6.4

## 24.2. Что закрыто из active roadmap v6.4

## 24.3. Блок устаревшей, неверной или изменённой логики после v6.5

## 24.4. Актуальный пользовательский статус для подписчиков и селлеров

## 24.5. Актуальный roadmap после v6.5

## 24.6. Новые правила дальнейших правок после v6.5

## 1. Расчётный движок Seller Helper не трогать без необходимости. Любое изменение max_bot_polling.py: timestamp backup → py_compile → локальные handle_text-тесты → systemctl restart helperbot.service → проверка journalctl и реальных MAX-сообщений.

## 2. CATEGORY GUARD V2 и RISK INSIGHTS V1 считать рабочим safe point. Следующие изменения делать поверх них, а не переписывать весь handle_text одним большим патчем.

## 3. Ручной publisher_v2.py использовать только как технический safe point. Обычная публикация должна идти через cron; перед ручной публикацией обязательно проверять дубли внутри pending и против уже опубликованных материалов.

## 4. Внешний GitHub TG fetcher считать критичным источником Telegram-потока. При падении плотности новостей сначала проверять свежесть tg_posts.json, количество items, список каналов и TG_JSON_LIMIT, а уже потом менять фильтры collector.

## 5. Ozon Select по-прежнему не использовать в боевом расчёте. Ozon reverse logistics хранить как official rule и связывать с логистическими тарифами, а не с пустым return tariffs.xlsx.

## 6. Пользовательские ответы должны быть честными: если категория ненадёжна — не считать; если логистика/возвраты/реклама не учтены — прямо написать; если товар в зоне риска — показать причину и практические варианты действий.

## 24.7. Короткая формулировка для будущих чатов по v6.5

## 06.05.2026 принят safe point v6.5: NEWSBOT v2 восстановил плотность новостей за счёт исправленного внешнего GitHub TG fetcher, расширенного списка TG-каналов и TG_JSON_LIMIT=150; ручной publisher использовался только для проверки, дальше поток должен идти через cron. Seller Helper получил CATEGORY GUARD V2 и RISK INSIGHTS V1: бот не считает по явно ошибочным категориям, показывает комиссию, налог, НДС, остаток и вывод по риску товара с практическими рекомендациями. helperbot.service после правок активен и обработал реальные MAX-запросы без ошибок. Закрыты аварийные пункты v6.4 по восстановлению Helper и наблюдению вечерних контуров; сравнение площадок, полноценный ranking категорий, Ozon logistics/returns/storage и юридический модуль остаются следующими этапами. Главный продуктовый акцент: Seller Helper — не пугающий калькулятор, а защитный инструмент для проверки товара до закупки и запуска.
Инсайдер Селлер · NEWSBOT v2 · Seller Helper · Паспорт v6.5 · 06.05.2026

## 12.4. Seller Helper, расчёт, доступ и юридический контур

## Источник v6.7: 5. Seller Helper: что уже умеет и как должен объясняться пользователю

## 5. Seller Helper: что уже умеет и как должен объясняться пользователю
Seller Helper должен быть понятен человеку, который впервые перешёл из новости. Поэтому /start теперь объясняет, что бот уже умеет: комиссии/тарифы по WB/Ozon/Яндекс, схемы работы, похожие категории, ограничения расчёта, налоговый нюанс и будущий полный расчёт прибыли.
Предпродакшен. Пока идёт тестирование и предпродакшен, сравнение WB / Ozon / Яндекс может быть доступно бесплатно. После запуска платного режима бесплатным остаётся базовый слой, а полный расчёт и сравнение тарифицируются.

## Источник v6.7: 10. Definition of Done для ближайшего MVP

## 10. Definition of Done для ближайшего MVP
Пользователь из MAX-новости переходит в Seller Helper по CTA-кнопке.
Пользователь понимает из /start, как пользоваться ботом.
Бот отвечает по комиссиям/тарифам WB, Ozon, Яндекс по одной площадке.
Ozon использует стандартный marketplace_service_rate, а не Select.
Запрос без площадки не раскрывает всё сравнение как обычную бесплатную справку.
Бот показывает бесплатный слой и будущие тарифы без агрессивной продажи.
Первый калькулятор маржи считает: цена продажи, комиссия/тариф, себестоимость, налоговая база, налог, остаток.
В ответе честно указаны неучтённые расходы: логистика, хранение, возвраты, реклама, прочие удержания.
Есть админский/технический способ проверить актуальность источников и статус тарифных слоёв.

## Источник v6.7: 11. Технический safe point 27.04.2026

## 11. Технический safe point 27.04.2026

## Источник v6.7: 21. Дополнение v6.2 от 29.04.2026: Docobrazec как юридический движок Seller Helper, защита данных и правильные приоритеты roadmap

## 21. Дополнение v6.2 от 29.04.2026: Docobrazec как юридический движок Seller Helper, защита данных и правильные приоритеты roadmap
Статус: принято и зафиксировано 29.04.2026. Это точечное дополнение к паспорту v6.1. Оно не переписывает NEWSBOT v2 и не меняет уже принятые MAX guardrails. Основная цель — правильно расставить приоритеты перед переходом к полноценному Seller Helper и зафиксировать, как именно встраивать Docobrazec в mini app.
Ключевой вывод: ближайший фокус — не новые тяжёлые фреймворки и не видеодайджест, а расчётный MVP Seller Helper. Docobrazec идёт следующим слоем как уже существующий детерминированный движок юридических документов. Legal RAG на базе законов, оферт и судебных кейсов усиливает Docobrazec, но не заменяет его шаблонную логику.

## 21.1. Что принято по Docobrazec
Селлерские юридические документы не являются новой отдельной идеей: они подразумевались в Docobrazec с самого начала, но текущая реализация ушла по B2C-логике «покупатель → продавец».
Docobrazec уже содержит полезную детерминированную основу: анкеты, ФИО, паспортные данные, ФНС, ИП, реквизиты и прочие поля для сборки документов.
Нужно не строить юридический модуль с нуля, а расширить существующую модель Docobrazec: добавить роли «селлер», «маркетплейс», «покупатель маркетплейса», новые сценарии, шаблоны и условия.
Документ по-прежнему собирается по схеме: анкета → условия → шаблон → готовый документ. LLM/RAG являются вспомогательным справочным слоем, а не заменой конструктора.
Первый целевой блок документов: селлер → маркетплейс; второй блок: ответ селлера покупателю; третий блок: селлер как покупатель товаров/услуг для бизнеса.

## 21.2. Целевая интеграция в Seller Helper mini app
Seller Helper mini app должен стать главным рабочим кабинетом экосистемы. Docobrazec встраивается внутрь него как юридический раздел/модуль, но физически может оставаться на своём сервере и в своей базе.

## 21.3. Защита данных и согласия
Серверы находятся в РФ и оформлены на российскую структуру. Это снижает инфраструктурные риски по локализации, но не отменяет privacy-by-design: персональные данные должны обрабатываться минимально, прозрачно и только там, где они действительно нужны.

## 21.4. API-мост: как связывать системы
Базы напрямую не объединять. Правильная схема — API-мост: Docobrazec остаётся детерминированным движком документов, Seller Helper является входом и кабинетом, RAG Store отдаёт справочный контекст по обезличенному запросу.

## 21.5. GitHub-базы законов и судебных кейсов
Открытые базы законов и судебных актов с GitHub потенциально являются нужным направлением для Legal RAG, но не должны сразу попадать в боевой контур и тем более заменять шаблоны Docobrazec.
Сначала провести аудит: лицензия, источник данных, актуальность, полнота, формат, размер, зависимости, качество разметки, наличие персональных данных и условия использования.
Использовать такие базы как слой поиска норм, похожих кейсов и доказательственных чек-листов, а не как автоматический генератор юридических документов.
Первый legal/RAG MVP должен быть узким: один сценарий «претензия селлера к маркетплейсу по удержанию/штрафу/невыплате/спорному возврату».
Официальные оферты Ozon/WB/Яндекс и проверенные судебные кейсы должны иметь приоритет над новостными/телеграм-сигналами.

## 21.6. Приоритетный roadmap после v6.2
Этот roadmap является приоритетным после v6.2 и уточняет порядок работ. Главный принцип: сначала расчётный Seller Helper и защита данных, затем интеграция Docobrazec, затем Legal RAG и платные сценарии.

## 21.7. Короткая формулировка для будущих чатов по v6.2

## 29.04.2026 принят safe point v6.2: Docobrazec не является новым внешним юридическим проектом, а должен стать встроенным юридическим движком Seller Helper. Его сильная сторона — уже существующая детерминированная логика: анкеты, ФИО, паспортные данные, ФНС, ИП, реквизиты, условия и шаблоны. Селлерский блок документов нужно добавить поверх этой модели: претензии селлера к маркетплейсу, ответы селлера покупателю и связанные доказательственные чек-листы. RAG Store «Инсайдер Селлер» остаётся отдельным справочным слоем для оферт, законов, судебных кейсов и сигналов; персональные данные остаются в Docobrazec. Связь систем делать через защищённый API-мост, с раздельными согласиями, функцией удаления данных и минимальной передачей обезличенного контекста. Приоритет roadmap: сначала расчётный MVP Seller Helper и privacy-by-design, затем интеграция Docobrazec, затем Legal RAG и платные сценарии.
Инсайдер Селлер · NEWSBOT v2 · Seller Helper · Docobrazec · Паспорт v6.2 · 29.04.2026

## Источник v6.7: 22. Дополнение v6.3 от 30.04.2026: MVP маржи, кнопочный UX и тест VK-рекламы

## 22. Дополнение v6.3 от 30.04.2026: MVP маржи, кнопочный UX и тест VK-рекламы
Статус: принято и зафиксировано 30.04.2026. Это точечное дополнение к паспорту v6.2: оно не меняет базовую архитектуру NEWSBOT v2, Docobrazec и RAG, а фиксирует закрытие первых пользовательских задач Seller Helper и начало внешнего теста трафика через VK Рекламу.
Ключевой вывод: экосистема перешла из внутренней сборки в первый внешний тест. Рекламируется MAX-канал «Инсайдер Селлер» как ядро экосистемы; Seller Helper остаётся прикладным инструментом внутри канала, к которому ведут CTA-кнопки после публикаций.

## 22.1. Что изменилось после v6.2
Seller Helper получил простой MVP расчёта маржи: цена продажи, себестоимость, комиссия маркетплейса, налоговая база, налог и остаток.
В расчётный сценарий добавлен НДС: пользователь может выбрать без НДС, НДС 5%, 7%, 22% или свой процент.
Пользовательский путь переведён на кнопочный UX: кнопка «Рассчитать прибыль» запускает пошаговый сценарий, без необходимости писать /calc.
В ответах сохранено честное предупреждение: логистика, хранение, возвраты, эквайринг, реклама и прочие удержания пока не включены в полный расчёт.
Решение по габаритам и весу: на текущем этапе не добавлять, чтобы не утяжелять UX и не раздувать контур.
Тестовая VK-реклама запущена не на Helper Bot, а на MAX-канал «Инсайдер Селлер» как главный источник трафика и доверия.

## 22.2. Seller Helper: текущий расчётный MVP

## 22.3. UX расчёта внутри бота

## 22.4. Что пока не входит в расчёт

## 22.5. VK-реклама: тестовый запуск

## 22.6. Что убрано из active roadmap как выполненное

## 22.7. Блок устаревшей, неверной или изменённой логики после v6.3

## 22.8. Актуальный roadmap после v6.3

## 22.9. Короткая формулировка для будущих чатов по v6.3

## 30.04.2026 принят safe point v6.3: MAX-канал «Инсайдер Селлер» работает как ядро экосистемы и запущен в тестовую VK-рекламу. Реклама ведёт в канал, а не напрямую в Seller Helper Bot. Seller Helper получил простой MVP расчёта маржи: комиссия, себестоимость, налог, НДС и остаток, а пользовательский путь переведён на кнопки, включая «Рассчитать прибыль». Логистика, габариты, вес, хранение, возвраты, эквайринг и реклама пока не входят в расчёт и честно указаны как ограничения. Следующий фокус — проверить рекламную воронку, сделать понятный закреп для новых подписчиков, усилить пояснения внутри Helper и собрать метрики использования расчёта.
Инсайдер Селлер · NEWSBOT v2 · Seller Helper · Docobrazec · VK Реклама · Паспорт v6.4 · 04.05.2026

## Источник v6.7: 25. Дополнение v6.6 от 06.05.2026: закрытый доступ Seller Helper для подписчиков, VK-лидформа и рекламная гипотеза через полезное действие

## 25. Дополнение v6.6 от 06.05.2026: закрытый доступ Seller Helper для подписчиков, VK-лидформа и рекламная гипотеза через полезное действие
Статус: зафиксировано после вечерних работ 06.05.2026. Дополнение v6.6 не переписывает паспорт v6.5, а продолжает его структуру: выполненное вынесено в safe point, устаревшее — в отдельный блок, рекламная кампания внесена как тестовая гипотеза и настройка, а не как подтверждённый канал привлечения.
Ключевой вывод: главная ценность для подписчиков теперь не только новости, но и доступ к Seller Helper. Для текущих подписчиков сохранён доступ к расчётам, для новых пользователей расчёт связан с подпиской на MAX-канал. VK-реклама больше не ведёт холодного пользователя напрямую в канал: сначала предлагается полезное действие — один тестовый расчёт по товару, а уже затем самостоятельное использование Seller Helper для подписчиков.

## 25.1. Что сделано для подписчиков и селлеров
Seller Helper переведён в продуктовую роль закрытой привилегии подписчиков канала «Инсайдер Селлер». Смысл для пользователя: подписка даёт доступ не только к новостям, но и к прикладному расчёту товара.
Сохранён доступ для уже существующей базы канала: текущие 36 подписчиков импортированы в локальный allowlist, чтобы не отрезать старую аудиторию при запуске gate.
Расчёт в Seller Helper подтверждён боевым тестом после всех правок: запрос «Озон шампунь 900 себестоимость 300 налог 6 ндс 5» прошёл через fresh_allowlist и получил ответ без ошибок.
В расчёте для подписчика сохраняются ключевые блоки: комиссия маркетплейса, цена продажи, себестоимость, налоговая база, налог, НДС, остаток после основных удержаний и риск-вывод Seller Helper.
В пользовательской упаковке временно убраны публичные обещания будущих платных тарифов 49/99/299 ₽. На текущем этапе акцент: Seller Helper — бесплатная польза для подписчиков канала.
Сформирован новый смысл закрепа/публичного объяснения: канал работает не просто как лента новостей, а как практический инструмент для селлеров: новости, мониторинг условий, расчёты, предупреждение о риске минусовой экономики товара.

## 25.2. Технический safe point: subscription gate v2
Создан и включён контур доступа Seller Helper через subscription gate v2: /opt/helperbot/subscription_gate.py + /opt/helperbot/helper_access.py + /opt/helperbot/helper_access.db.
В helper_access.db активирован стартовый доступ для 36 текущих подписчиков: source=channel_seed_20260506, status=active, last_verified_at выставлен на момент запуска gate.
Исправлена критичная ошибка: chat_id личного диалога MAX не равен user_id подписчика канала. Ошибочный fallback chat_id → user_id удалён и не должен возвращаться.
В max_bot_polling.py добавлена функция извлечения настоящего user_id из MAX update. Gate получает user_id, но старый handle_text продолжает получать только text и chat_id, чтобы не ломать расчётный движок.
Перепроверка подписки настроена на 17 часов: если пользователь уже в allowlist и последняя проверка свежая, расчёт доступен; если окно устарело, gate перепроверяет подписку через MAX API.
Логика отписки: если пользователь потерял подписку и это подтверждается после истечения 17-часового окна, следующий расчёт блокируется. Для старых/известных пользователей при временной ошибке API предусмотрена защита от ложной блокировки.
После чистки отладочного мусора сервис helperbot.service активен, py_compile пройден, контрольный боевой запрос после рестарта прошёл через ALLOW reason=fresh_allowlist user_id=35293352.

## 25.3. Что убрано или признано устаревшим после v6.6
Прямая VK-реклама с целью «переход по ссылке» на MAX-канал признана слабой гипотезой для текущего этапа: она оптимизируется на клики и может сливать бюджет без подписки и расчёта.
Формат «рекламируем канал как новости маркетплейсов» признан недостаточно сильным. Новый рекламный крючок — полезное действие: проверка товара и расчёт основных удержаний.
Идея кода доступа из закрепа канала отклонена: пользователь не будет вручную вводить код, это ухудшает конверсию.
Мягкая кнопка «Я подписался» не является целевым решением для боевого доступа. Целевое решение — технический gate + локальный allowlist + периодическая перепроверка.
Публичные тарифы 49/99/299 ₽ убраны из пользовательских сообщений Seller Helper до подтверждения спроса, доверия, качества расчёта и рекламной воронки.
Отладочные вставки RAW_UPDATE_DEBUG_V1 и _debug_save_update(update) не должны оставаться в боевом коде: одна такая вставка уже приводила к IndentationError и падению helperbot.service.
Ручные большие патчи в max_bot_polling.py без точечного backup/py_compile/боевого теста запрещены. После v6.6 принцип: минимальные точечные изменения поверх рабочего safe point.

## 25.4. VK-реклама: вносить ли кампанию в паспорт
Решение: рекламную кампанию нужно внести в паспорт, но не как подтверждённый источник трафика и не как уже успешный канал. Вносить её следует как тестовую рабочую гипотезу, подготовленную к запуску: VK используется не для прямого перехода в MAX, а для сбора заявки на одно полезное действие — предварительный расчёт товара.

## 25.5. Текущая структура VK-лидформы
Первый экран формы: «Инсайдер Селлер», заголовок «Сколько вы заработаете?», описание в логике «Расчёт маржи отправим в МАКС». Формат — компактный, без лишнего текста.
Фильтр по МАКС: «У вас есть аккаунт в МАКС?» Ответ «нет» ведёт на стоп-экран. Цель — не собирать лиды, которым расчёт некуда отправить.
Контакт в МАКС: если стоп-экран позволяет расширить форму, отдельным вопросом собирается способ найти пользователя в МАКС: ссылка, ID или ник.
Площадка: Ozon / Wildberries / Яндекс Маркет / Пока не знаю.
Товар: свободный ответ, пример для формы — шампунь, футболка, корм для кошек, чайник.
Цена продажи и себестоимость: либо одним вопросом, либо двумя отдельными вопросами, если лимиты формы позволяют.
Налоговый режим: УСН 6%, УСН 6% + НДС 5%, УСН 6% + НДС 7%, ОСН + НДС 22%, Не знаю.
Экран результата: «Заявка принята. Данные по товару получены. Предварительный расчёт отправим в МАКС. Для самостоятельных проверок откройте канал».
Стоп-экран для не-MAX: «Расчёт отправляем в МАКС. Сейчас тестовый расчёт Seller Helper отправляется только в МАКС. Если появится аккаунт, вы сможете вернуться и проверить товар».
Важно: лид-форма VK не должна обещать мгновенный персональный расчёт внутри самой формы. Форма собирает данные; расчёт выдаётся через наш контур Seller Helper/админский процесс и отправляется в МАКС.

## 25.6. Рекламные креативы и тексты
Подготовлены рекламные креативы в форматах 4:5 и 16:9 в едином стиле: светлый деловой фон, карточка товара, расчётный блок, акценты «Комиссия», «Налог», «НДС», «Остаток», CTA «Проверить товар».
Основной визуальный посыл: «Сколько вы заработаете?» и «Проверьте товар перед закупкой». Это проще, чем «маржа», и понятнее для начинающих селлеров.
В креативах не используются логотипы Ozon/WB/Яндекс, чтобы не создавать лишние риски модерации и не привязывать объявление к одной площадке.
В тексте рекламы не использовать формулировку «точная прибыль»: пока логистика, возвраты, хранение, реклама и прочие расходы не включены полностью, правильнее писать «предварительный расчёт» и «остаток после основных удержаний».
Рабочий текст объявления: «Укажите товар, цену и себестоимость — Seller Helper сделает один предварительный расчёт: комиссия маркетплейса, налог, НДС и остаток после основных удержаний».
Кнопка объявления: «Проверить товар».

## 25.7. Как обрабатывать первые заявки
Первые 5-20 заявок обрабатывать вручную или полуавтоматически, не строя сразу тяжёлую интеграцию VK Lead Forms API.
Из заявки брать: площадку, товар, цену продажи, себестоимость, налоговый режим и контакт в МАКС.
Собирать строку для Seller Helper в формате: «Ozon шампунь цена 900 себестоимость 300 налог 6 ндс 5».
Полученный ответ отправлять человеку в МАКС и в конце мягко указывать: самостоятельные расчёты доступны подписчикам канала «Инсайдер Селлер».
Если заявка не содержит нормальной цены/себестоимости или содержит «нет МАКС», не тратить время на ручной расчёт.
После первых заявок оценить качество: реальные ли товары, есть ли цены, понятен ли налоговый режим, появляются ли новые пользователи в helper_access с source=live_subscription_check.

## 25.8. Метрики рекламной воронки после v6.6
Показы и клики больше не являются главной метрикой. Главная метрика — заполненная анкета с товаром, ценой и себестоимостью.
В VK смотреть: показы, открытия формы, завершённые анкеты, цена анкеты, доля людей с МАКС, качество товарных данных.
В MAX смотреть: прирост подписчиков канала, новые user_id в helper_access, новые ALLOW reason=live_subscription, запуски расчёта и повторные обращения.
Качество лида оценивать по практическим признакам: указана площадка, понятный товар, есть цена и себестоимость, человек оставил способ связи в МАКС.
Если анкеты идут, но в MAX/Helper не переходят — усилить пост-результат и инструкцию. Если анкет нет — менять аудиторию/креатив/оффер, а не увеличивать бюджет вслепую.

## 25.9. Актуальный roadmap после v6.6
Не трогать расчётный движок Seller Helper без необходимости: текущий safe point работает и подтверждён логами.
Дождаться первых новых пользователей/лидов, чтобы проверить ветку new user → MAX subscription check → grant_access → расчёт.
Подготовить простой шаблон ответа на тестовую VK-заявку: исходные данные, расчёт по Seller Helper, вывод риска, честное предупреждение о неучтённых расходах, ссылка на канал для самостоятельных проверок.
Если лид-форма даст качественные заявки — сделать лёгкую полуавтоматизацию: экспорт/уведомление заявки в админский MAX-чат и шаблон команды для расчёта.
Если заявок не будет или они будут мусорными — не масштабировать кампанию, а заменить аудиторию/креатив, протестировать другой заголовок и упростить форму.
Отдельно позже проверить механику снятия доступа у отписавшихся после 17-часовой перепроверки на новом неадминском аккаунте. Текущий админский аккаунт для этого теста не подходит.
После подтверждения спроса вернуться к отдельным слоям логистики, возвратов, хранения, рекламы и эквайринга в расчёте, но не раньше, чем будет подтверждена ценность простого расчёта.

## 25.10. Короткая формулировка для будущих чатов по v6.6

## 06.05.2026 принят safe point v6.6: Seller Helper стал закрытой прикладной пользой для подписчиков «Инсайдер Селлер». Текущие 36 подписчиков импортированы в allowlist, gate работает по настоящему user_id из MAX update, ошибочный chat_id → user_id fallback удалён, перепроверка подписки настроена на 17 часов. Боевой тест прошёл через ALLOW reason=fresh_allowlist и расчёт отправлен пользователю. VK-реклама переупакована: не прямой переход по ссылке в канал, а лид-форма на одно полезное действие — предварительный расчёт товара. Рекламная кампания внесена в паспорт как тестовая гипотеза, а не как подтверждённый канал привлечения. Главный пользовательский смысл: подписчик получает не только новости, но и возможность проверять товар на комиссию, налог, НДС, остаток и риск ухода в минус.
Инсайдер Селлер · NEWSBOT v2 · Seller Helper · VK лидформа · Subscription Gate · Паспорт v6.6 · 06.05.2026

## 12.5. Тарифы, маркетплейсы, Ozon/WB/Яндекс, мониторинг

## Источник v6.7: 6. Единая тарифная база и приведение маркетплейсов к общему знаменателю

## 6. Единая тарифная база и приведение маркетплейсов к общему знаменателю
Единая база: /opt/newsbot_v2/data/unified_tariffs.db. Базовый слой clean_commissions уже используется Helper. Следующий этап — нормализация всех тарифных слоёв: комиссия/тариф, логистика, возвраты, хранение/размещение, прочие удержания, налоговый блок.
Ключевой вывод по Ozon. Ранее Ozon казался “дешёвым” из-за попадания в расчёт Select-слоя 5–12%. После загрузки стандартного файла marketplace-services-rates появился нормальный слой marketplace_service_rate со ставками, сопоставимыми по смыслу с WB и Яндексом. Helper теперь должен брать по Ozon только fee_type=marketplace_service_rate.

## Источник v6.7: 8. Ежедневный монитор изменений комиссий и тарифов

## 8. Ежедневный монитор изменений комиссий и тарифов
Старый монитор изменений комиссий сейчас не считается рабочим. Его нужно сделать заново как отдельный контур NEWSBOT v2 / админки / дайджеста.
Особое правило по Ozon. Ozon нельзя стабильно парсить как полноценную комиссионную сетку. Поэтому монитор Ozon должен работать через два сигнальных канала: ручная загрузка официальных Excel-документов и отслеживание новостей/статей/сообщений об изменениях тарифов Ozon. Новость о тарифе должна создавать задачу: проверить официальный документ, обновить слой базы и пересчитать ответы Seller Helper при необходимости.
Сигнал должен показывать: что изменилось, в каком файле/слое, с какой даты действует, какие категории/схемы затронуты.
Если изменение влияет на расчёт Seller Helper — ставить флаг “нужно пересчитать ответы/кэш/справочник”.
Если изменений нет — вечерний дайджест по офертам/условиям должен честно писать, что изменений не обнаружено, и перечислять проверенные площадки.

## Источник v6.7: 26. Дополнение v6.7 от 13.05.2026: Яндекс API, качество дайджестов, RAG-расширение и рост канала

## 26. Дополнение v6.7 от 13.05.2026: Яндекс API, качество дайджестов, RAG-расширение и рост канала
Статус: зафиксировано после работ 13.05.2026. Дополнение v6.7 не переписывает паспорт v6.6, а продолжает его структуру: выполненное вынесено в safe point, устаревшее и рискованное — в отдельные правила, новый рабочий фокус — в roadmap.
Ключевой вывод: проект перешёл от отдельного калькулятора и новостной ленты к накопительной экосистеме данных. NEWSBOT v2 теперь должен не только публиковать новости, но и сохранять полезные знания для будущего Seller Helper, Legal RAG, OfferDoctor и анализа карточек товаров.

## 26.1. Что сделано и принято 13.05.2026

## 26.2. Яндекс Маркет API как новый рабочий тарифный источник

## 13.05.2026 подтверждено, что доступ к Яндекс Маркет API работает: список кампаний возвращается со статусом 200, дерево категорий отдаёт корневой объект result с children, а tariffs/calculate принимает рабочий вариант запроса с campaignId и плоскими dimensions.
Главный результат — успешный импорт тарифов в боевую чистую таблицу clean_commissions: marketplace=yandex, fee_type=commission_only, schemes FBS/FBY, valid_from=2026-05-13, source_file=yandex_market_api_tariffs_calculate.json.
Правило дальше. Яндекс API-импорт нужно сделать регулярным управляемым контуром: запуск по расписанию или вручную из админки, backup базы перед импортом, отчёт по числу строк, схемам, min/max fee и source_file. Старый yandex_commissions.db сохранять как исторический/резервный слой, но не считать самым свежим источником после успешного API-импорта.

## 26.3. MAX subscription gate: user_id и chat_id нельзя смешивать
Критичное правило MAX API для Seller Helper: user_id и chat_id — разные сущности. user_id является главным ключом доступа подписчика в helper_access.db; chat_id — только адрес диалога.
Особенность MAX callback-кнопок: message_callback может приходить с другим user_id, чем предыдущее текстовое сообщение в том же диалоге. Поэтому запрещено давать доступ просто по chat_id.
Это правило обязательно включать во все будущие MAX integration guardrails и новые версии паспорта проекта.

## 26.4. Админские предупреждения и вечерний монитор
До v6.7 админский alert мог приходить ежедневно как технический шум, даже если ничего нового для действия не было. Теперь admin_alert.py должен работать по принципу fingerprint: одна и та же причина не отправляется повторно каждый день.
Создана/используется таблица admin_alert_state в /opt/newsbot_v2/data/unified_tariffs.db. Первый dry-run создаёт состояние, повторный dry-run по тому же fingerprint возвращает «no attention required».
Правило языка: в канале не писать «открой админку» и не показывать внутренние служебные детали. Для подписчиков важен результат: подтверждённое изменение, отсутствие подтверждения или аккуратное наблюдение за официальным источником.

## 26.5. Текстовые дайджесты и publisher: новая редакционная планка
Дайджест больше не должен быть перечнем ссылок с одинаковым выводом. Главная ценность — строка «Что проверить»: конкретное действие продавца после новости.
publisher_v2 получил семантическую защиту от повторов. Пример: несколько публикаций про повышение тарифов WB на возврат и обратную логистику должны сводиться к одному topic key wb_return_tariff_logistics. Новые повторные публикации по уже раскрытой теме переводить в digest.
formatters.py теперь обязан давать приемлемый fallback при сбое LLM: чистый источник, короткий заголовок, нормальный summary без обрезка с середины слова и конкретный блок «Что это значит для селлера».

## 26.6. Аудиодайджест: что исправлено и что контролировать
Аудиодайджест был временно поставлен на паузу, потому что в сценарии накапливались плохие фрагменты: обрезанные хвосты предложений, повторы одной темы, одинаковая фраза «Главный вопрос для селлера» и склейки вроде «товара Ozon» без точки.
После тестового сценария 13.05.2026 audio cron снова включён: 45 22 * * * /opt/newsbot_v2/run_audio_digest.sh >> /opt/newsbot_v2/logs/audio_digest.log 2>&1.

## 26.7. RAG накопление: что уже есть и что нужно копить дальше
Да, RAG-накопление уже идёт: RAG Store был создан ранее и используется как текстовый/смысловой слой. Но v6.7 расширяет назначение RAG. Он должен стать общей памятью всей экосистемы, а не только архивом новостей и оферт.
Запрет: в RAG не передавать паспортные данные, полные реквизиты, личные данные из Docobrazec, необезличенные заявки VK и личные переписки пользователей. Для RAG достаточно обезличенного сценария, темы, marketplace, суммы/диапазона и итогового вывода.

## 26.8. Программы и контуры, которые подключать к RAG и аналитике

## 26.9. Инфополе и поиск MAX: что заполнить и проверить
Проблема v6.7: продукт упакован хорошо, но канал держится около 40 подписчиков. Рабочая гипотеза — люди просто не находят канал в MAX, а боты/поиск/рекомендации пока плохо видят новый канал без внешнего инфополя.
Правило: сначала проверить поиск MAX без id и заполнение инфополя. Только после этого решать, нужна ли платная внешняя поддержка аудитории.

## 26.10. Готовый текст закрепа / поста для подписчиков: патч от 13.05.2026
Патч «Инсайдер Селлер» от 13.05.2026
Что обновили в экосистеме канала.

## 1. Обновили тарифный контур Яндекс Маркета.
Теперь Seller Helper опирается на свежий API-слой Яндекса, а не только на старые справочники. Это важно для расчётов по комиссиям и будущего сравнения площадок.

## 2. Усилили вечерний монитор изменений.
Мы отделяем реальные подтверждённые изменения от новостного шума. Если тариф, оферта или официальный источник требуют проверки — это попадает в монитор и админский контроль, а не превращается в ежедневную тревогу в канале.

## 3. Улучшили дайджесты и аудиодайджесты.
Дайджест должен отвечать не «что произошло», а «что проверить селлеру»: цену, маржу, возвраты, ПВЗ, отзывы, карточку, остатки, налоги или риск ухода товара в минус.

## 4. Чистим повторы и дубли.
Если одна и та же тема разошлась по нескольким источникам, мы не должны публиковать её как новую новость каждый раз. Лучше один нормальный материал, чем пять дублей.

## 5. Расширяем базу знаний.
Копим не только тарифы и оферты, но и юридические сигналы, тренды карточек, отзывы, инфографику, AI-трафик, дизайн карточек и всё, что влияет на продажи. Это база для будущего OfferDoctor и юридического блока.
Почему Seller Helper только для подписчиков?
Потому что это уже не просто бот-калькулятор. За ним стоит база тарифов, монитор официальных источников, расчёт налогов и НДС, проверка риска товара и ежедневное сопровождение изменений маркетплейсов.
Подписчик получает не только новости, а рабочий инструмент: проверить товар до закупки, понять комиссию, увидеть предварительный остаток и не уйти в минус там, где это можно заметить заранее.
Инсайдер Селлер — меньше шума, больше прикладной пользы для продавца.

## 26.11. Блок устаревшей, неверной или изменённой логики после v6.7

## 26.12. Актуальный roadmap после v6.7

## 26.13. Короткая формулировка для будущих чатов по v6.7

## 13.05.2026 принят safe point v6.7: Яндекс Маркет переведён на рабочий API-импорт тарифов calculate; в clean_commissions загружено 16282 строки по FBS/FBY с valid_from=2026-05-13; helperbot.service после импорта активен. admin_alert.py получил dedupe через admin_alert_state и не должен ежедневно спамить одинаковыми предупреждениями. Текстовые дайджесты усилены строкой «Что проверить», аудиодайджест очищен от обрезков и повторов, cron аудио снова включён на 22:45. publisher_v2 получил semantic dedup, formatters.py даёт более чистый fallback, llm.py восстановлен после неудачной правки и компилируется. RAG должен копить не только тарифы и оферты, но и юридику, карточки, дизайн, инфографику, AI-трафик, тренды продаж и редакционные выводы для будущего OfferDoctor. MAX guardrail: user_id и chat_id не смешивать; доступ Seller Helper проверяется по user_id, а chat_id — только адрес диалога и callback fallback после подтверждённой привязки. Ближайший фокус: закреп «Патч от 13.05.2026», поиск MAX без id, инфополе/теги, регулярный Яндекс API-импорт, RAG tagging schema и GitHub scouting design analytics.
Инсайдер Селлер · NEWSBOT v2 · Seller Helper · Яндекс API · RAG · OfferDoctor · Legal · Паспорт v6.7 · 13.05.2026

## 12.6. Аналитика, RAG, MPSTATS, монетизация и рост

## Источник v6.7: 7. Что узнали на примере MPSTATS и как это учитывать

## 7. Что узнали на примере MPSTATS и как это учитывать
MPSTATS показывает мощную аналитику: рынок, карточки, продажи, конкуренцию, категории, динамику, возможности по товару. Это хороший ориентир по интерфейсу и ценности, но не прямой шаблон для первого MVP Seller Helper.
Seller Helper не должен становиться копией MPSTATS.
Для микробизнеса важнее короткий расчёт: цена продажи, комиссия, сумма к выплате, налоговая база, налог, остаток.
Расширенная аналитика может стать платным уровнем позже: спрос, конкуренция, категории, сценарии цены, риски.
Главная фишка — честное пояснение налогов: налог не с “пришло на счёт”, а с цены продажи / дохода от реализации.

## Источник v6.7: 9. Монетизация и продуктовая упаковка

## 9. Монетизация и продуктовая упаковка

## 12.7. Правила, roadmap и служебные формулировки

## Источник v6.7: 12. Правила дальнейших правок

## 12. Правила дальнейших правок
Перед правкой файлов делать timestamp backup.
Не править одновременно collector, publisher, db.py и helperbot без отдельной проверки каждого шага.
Не запускать второй polling-процесс helperbot вручную; только systemctl restart helperbot.service.
Не использовать старый /opt/newsbot.
Не выводить токены и .env целиком в чат.
Для NEWSBOT v2 использовать venv: /opt/newsbot_v2/venv/bin/python.
Для Helper учитывать, что service запускается системным python3 из /usr/bin/python3.
Платное сравнение не должно случайно раскрываться в бесплатном общем запросе.

## Источник v6.7: 13. Ближайший roadmap

## 13. Ближайший roadmap
Актуализировано v6.3: выполненные пункты по марже, НДС, кнопочному UX и тестовой рекламе перенесены в блок 22.6 как закрытые.
Доработать ranking категорий и схем: WB — отделить специальные схемы от базовых; Яндекс — улучшить смысловой ranking broad-запросов; Ozon — держать marketplace_service_rate.
Разложить Ozon logistics / returns / storage / compensation coefficient в marketplace_fee_components после подтверждения интереса к простому расчёту.
Улучшить onboarding в MAX-канале: закреплённый пост должен объяснять, зачем подписываться, где читать новости и как перейти к расчёту в Seller Helper.
Собирать метрики рекламной воронки: показы, клики, переходы в MAX, прирост подписчиков, переходы в Helper, запуски расчёта и точки отваливания.
Добавить админский экран статуса источников: WB, Яндекс, Ozon, дата обновления, source_status, source_role, RAG Store, signal_digest_runs, audio_digest.
Платные сценарии 49/99/299 ₽ готовить только после стабильного простого расчёта, понятного UX и подтверждённого спроса из рекламного теста.
Docobrazec и Legal RAG развивать после расчётного MVP и privacy-by-design; не смешивать персональные данные с RAG.

## Источник v6.7: 14. Короткая формулировка для будущих чатов

## 14. Короткая формулировка для будущих чатов
Мы строим экосистему «Инсайдер Селлер»: MAX-канал как главный источник трафика и доверия, NEWSBOT v2 как data/admin core, Seller Helper как прикладной помощник после новостей, лендинги как внешний слой продаж. Seller Helper должен давать точные комиссии по WB/Ozon/Яндекс, затем считать прибыль товара с честным налоговым блоком, сравнивать площадки и подключать юридический/RAG-слой. Ozon не парсим напрямую: используем официальные Excel-документы и новости/статьи как сигналы изменений тарифов. После каждой пачки публикаций NEWSBOT v2 отправляет один CTA в Seller Helper: «[кнопка] Проверить комиссию и прибыль».

## 13. Дополнение v7.1 от 17.05.2026: live seller_filter, запрет боевого dry-run и защита от молчания канала
Статус: зафиксировано после аварийной диагностики и нормализации публикационного контура NEWSBOT v2 17.05.2026. Дополнение v7.1 не отменяет v7.0, а уточняет production-правила для collector/publisher, аудиодайджеста, dry-run и контроля плотности публикаций.

## 13.1. Что произошло и почему канал молчал
Обычные новости не выходили несколько дней не из-за дефицита тем по маркетплейсам/e-commerce, а из-за разрыва между фильтром и базой.
Коллектор видел значительный поток сырья: RSS + TG JSON, в нормальном wrapper-запуске — TG JSON 108 и raw news 240.
seller_filter_dryrun логировал new_decision=publish, но не записывал это как seller_decision=publish в news_queue.db.
publisher_v2.py запускался по cron, но видел pending loaded=0 / No pending news и поэтому честно молчал.
Аудиодайджест жил отдельной цепочкой, поэтому мог выходить даже при молчании обычных новостей. Аудио не считается заменой обычных публикаций.

## 13.2. Dry-run: новое обязательное правило жизненного цикла
Dry-run означает: фильтр считает и логирует решение, но не применяет его к базе/публикации.
Dry-run разрешён только временно: для сравнения старой и новой логики, диагностики, безопасной проверки качества фильтра.
Любой dry-run должен иметь owner, дату/условие снятия, проверочный лог, критерий успеха и команду возврата в live.
Запрещено оставлять dry-run в цепочке collector → publisher, если от него зависит публикация. Это приводит к ситуации: фильтр видит publish, publisher видит пусто.
Перед финальным запуском обязательна проверка: grep по живому коду, live-фильтр пишет seller_decision в БД, publisher видит publish-кандидаты.

## 13.3. Норма публикаций и защита от молчания
Будние дни: целевая норма минимум 10 публикаций в день.
Выходные и праздники: целевая норма минимум 2-3 публикации.
Аудиодайджест, вечерний монитор и служебные CTA не заменяют обычные новости.
Если publish-кандидатов нет, но есть сильные digest/evergreen/backlog-материалы, publisher должен иметь quota fallback.
Если 2-3 часа есть сырьё и insert/update в базе, но нет публикаций, должен отправляться админский MAX-alert.

## 13.4. Что считается закрытым после v7.1
Причина молчания выявлена и описана: боевой dry-run фильтра не писал решения в базу.
Временный promote bridge использован только для аварийного восстановления и убран из штатной цепочки.
Live seller_filter включён в db.py; collector через wrapper применяет решения к БД.
Окно обновления старых строк снижено до 8 часов.
publisher_v2 получил stale publish guard и не должен выпускать старые хвосты.
Рекламный мусор добавлен в hard-ignore.
Аудиодайджест очищен от раздражающих универсальных фраз и однообразных концовок.

## 13.5. Что остаётся P0 после v7.1
Сделать watchdog публикаций: alert админу, если есть сырьё, но нет публикаций.
Сделать quota fallback: будни 10, выходные/праздники 2-3, без публикации мусора.
Добавить админский статус публикационной цепочки: TG JSON freshness, raw, inserted, publish/digest/ignore, published today, last errors.
Дальше расширять hard-ignore и topic dedup на реальных ложных срабатываниях.
Регулярно проверять, что dry-run не вернулся в production после будущих тестов.

## 13.6. Короткая формулировка для будущих чатов по v7.1

## 17.05.2026 принят safe point v7.1: причина молчания NEWSBOT v2 была не в нехватке новостей, а в оставленном в production seller_filter_dryrun. Фильтр видел new_decision=publish, но не записывал seller_decision=publish в news_queue.db, поэтому publisher_v2 весь день видел pending loaded=0. Временный promote bridge подтвердил диагноз и был удалён из run_regular_v2.sh. Нормальная цепочка теперь: collector через wrapper с .env → seller_filter_live в db.py → реальные поля seller_decision / seller_relevance_score / actionability_score → publisher_v2. В .env и db.py установлен lookback 8 часов; publisher_v2 получил stale publish guard; seller_filter.py получил hard-ignore рекламы и партнёрок; аудиодайджест очищен от повторяющихся фраз и получил вариативные концовки. Dry-run разрешён только как временная диагностика с обязательным сроком снятия и live-check. Следующий P0: watchdog и quota fallback, чтобы канал не мог молчать при наличии сырья.

### Таблица 1
| Параметр | Значение |
| --- | --- |
| Тип документа | Единый структурированный паспорт изделия + ТЗ + живой roadmap/backlog |
| Источник | Паспорт v7.1 от 17.05.2026 + safe point 18.05.2026 по восстановлению NEWSBOT v2, official GitHub JSON, quota/watchdog, audio digest и актуальному roadmap. |
| Принцип v7.2 | Сохранить структуру v7.1, но зафиксировать новую контрольную точку v7.2: что восстановлено, что перенесено в Done, какие P0/P1/P2 задачи остаются активными. |
| Главный контур | /opt/newsbot_v2 |
| Helper | /opt/helperbot |
| Платформа | MAX |
| Тарифная база | /opt/newsbot_v2/data/unified_tariffs.db#clean_commissions |
| RAG Store | /opt/newsbot_v2/data/rag_store.db |
| Safe point v7.2 | 18.05.2026: NEWSBOT v2 восстановлен и усилен; dry-run убран; quota fallback и watchdog работают; official GitHub JSON подключён; official bridge сгруппирован; audio digest очищен; health-check чистый. |
| Норма публикаций | Будни: минимум 10 публикаций; выходные: минимум 3 публикации как ориентир 2-3. Это минимум, не верхний лимит. При наличии качественных publish-кандидатов публиковать больше можно. |
| Инфографика Seller Helper | Решение сохраняется как P0/P1 продуктовый блок после стабилизации NEWSBOT: calculation_result JSON → HTML/SVG template → Playwright/Chromium → PNG/PDF. AI не рисует цифры. |
| Official GitHub JSON | Основной контур official sources: existing GitHub Action создаёт official_marketplace_posts.json; VPS official_channel_collector.py читает OFFICIAL_JSON_URLS. Прямой t.me fallback включается только если JSON пустой/недоступен. |
| Публикационный watchdog | newsbot_watchdog.py в cron; проверяет молчание, published_today, pending_publish, strong_digest и учитывает weekday/weekend target. |
| Quota fallback | publisher_v2.py добирает минимум: Пн–Пт 10, Сб–Вс 3; не ограничивает публикации сверху. |
| Аудиодайджест v7.2 | Расширена чистка seller-check фраз, 24 варианта финала, короткие спокойные выпуски accepted with warning, добавлен run_audio_digest_preview.sh без публикации. |
| Health-check 18.05.2026 | Cron активен, py_compile OK, today publish=11, pending publish=0, news_queue.db ok, unified_tariffs.db ok, активный проект 1.6G, quarantine 5.0G. |

### Таблица 2
| Приоритет | Задача | Комментарий |
| --- | --- | --- |
| P0 | Проверить состояние helperbot.service после Ozon/guard-правок | Не рестартить без direct test |
| P0 | Закрепить Ozon Select = test_only, standard Ozon = marketplace_service_rate | Ключевое правило источников |
| P0 | Переписать Ozon-предупреждение как «сервисная ставка, не полный расчёт» | Убрать ощущение кривой комиссии |
| P0 | Добавить индикатор «думаю / считаю» | Отдельный маленький патч |
| P0 | Опубликовать и закрепить onboarding-пост | Рост канала и объяснение ценности |
| P0 | Проверить поиск MAX без id и заполнить инфополе/теги | v6.7 growth |
| P1 | Разобрать цепочку wrappers build_marketplace_answer_v2 | Перед большой чисткой |
| P1 | WB base/special schemes ranking | Не показывать 3% как основной benchmark |
| P1 | Безопасные кнопки уточнения категории | Без агрессивного handle_text patch |
| P1 | Регулярный Yandex API import с backup/отчётом | После v6.7 |
| P1 | RAG tagging schema v1 | marketplace/source_type/trust_level/module/topic/valid_from |
| P2 | Сравнение площадок после category matching | Будущий платный сценарий |
| P2 | Legal RAG + Docobrazec API bridge | Privacy-by-design |
| P2 | OfferDoctor RAG-модуль по карточкам | После ядра расчёта |
| P3 | МАРК-разведчик | Дальний стратегический модуль |
| P0 | Добавить watchdog молчания публикаций | Если 2-3 часа есть raw/inserted новости, но нет обычных публикаций — админский alert в MAX. |
| P0 | Добавить quota fallback для нормы публикаций | Будни минимум 10; выходные/праздники минимум 2-3; аудио не считается заменой обычных новостей. |
| P0 | Закрепить dry-run lifecycle | Любой dry-run имеет срок снятия, owner, проверку live-write в БД и запрет оставлять его в production. |
| P1 | Расширить hard-ignore рекламы и партнёрок | WhiteBird/refid/Bybit/торговые сигналы/резидентские схемы/бюллетени и похожий мусор не должны становиться publish. |
| P1 | Админский статус публикационной цепочки | Показывать TG JSON, raw, inserted, publish/digest/ignore, published today, last publisher status. |
| P0 | Сформировать calculation_result JSON для Seller Helper | Единый контракт данных: marketplace, товар, категория, цена, себестоимость, налог, НДС, схемы, комиссия, payout, остаток, лучший/худший сценарий, предупреждения. |
| P0 | Сделать MVP infographic_renderer для одного расчёта | HTML/CSS или SVG-шаблон: одна площадка, несколько схем, ключевые метрики, структура цены, вывод и предупреждение. Рендер в PNG. |
| P0 | Добавить экспорт PNG/PDF и кнопки в Seller Helper | После расчёта: «Инфографика», «Скачать PNG», «Скачать PDF». Временные файлы, MAX attachment upload, логи и cleanup. |
| P1 | PDF-отчёт A4 по расчёту | Та же структура, но в формате отчёта: входные данные, таблица сценариев, лучший/худший сценарий, ограничения расчёта. |
| P1 | Шаблон сравнения схем внутри одной площадки | Для Ozon/WB/Яндекс показывать сравнение FBO/FBS/DBS/Express или эквивалентных схем без перегруза интерфейса. |
| P1 | Шаблон сравнения площадок | После category matching: WB/Ozon/Яндекс по одному товару, одинаковые входные данные, остаток, комиссия, риски и итоговая рекомендация. |
| P2 | Библиотека шаблонов и бренд Seller Helper | 2-3 лёгких визуальных шаблона: короткая карточка, полная PNG-инфографика, PDF-отчёт. Единый стиль без тяжёлых изображений. |

### Таблица 3
| Показатель | Найдено |
| --- | --- |
| Размер | 3923 строки |
| build_marketplace_answer_v2 | 9 определений: 1634, 2654, 2832, 2881, 2961, 3043, 3283, 3712, 3812 |
| improve_category_score | 3 определения: 1102, 3314, 3513 |
| _cg_guard_reason_v2 | 4 определения: 2554, 3477, 3612, 3864 |
| normalize_marketplace | 2 определения: 792, 880 |
| _route_label_v1 | 2 определения: 2270, 2360 |
| _should_send_progress_indicator_v1 | 2 определения: 2212, 2301 |
| Вывод | Нужен отдельный безопасный рефакторинг с тестами, не удалять обёртки вслепую |

### Таблица 4
| Слой | Назначение | Решение v7.1 |
| --- | --- | --- |
| calculation_result JSON | Единый структурированный результат расчёта Seller Helper. | Источник всех цифр для текста, PNG и PDF. |
| HTML/SVG-шаблон | Визуальная карточка расчёта: метрики, таблица схем, bar cards, вывод. | Заполняется данными из JSON, без AI-подстановки цифр. |
| Renderer | Экспорт шаблона в PNG/PDF. | Приоритет: Playwright/Chromium; запасные варианты: SVG→PNG/PDF, Pillow, ReportLab. |
| MAX UX | Кнопки после расчёта. | «Инфографика», «Скачать PNG», «Скачать PDF». |
| LLM | Редактор короткого вывода. | Может писать только текстовый вывод, но не рисует цифры и таблицы. |

### Таблица 5
| Приоритет | Задача | DoD |
| --- | --- | --- |
| P0 | Выделить calculation_result JSON из текущего расчёта Seller Helper. | Один и тот же JSON кормит текстовый ответ, PNG и PDF; цифры совпадают. |
| P0 | Сделать PNG-MVP карточки одного расчёта. | На примере Ozon «чайник заварочный» карточка корректно показывает цену 2900, себестоимость 570, налог 174, комиссии и остатки по схемам. |
| P0 | Добавить кнопку инфографики в Seller Helper. | Пользователь после расчёта получает PNG в MAX без ручной генерации. |
| P1 | Добавить PDF-экспорт. | PDF открывается как отчёт A4, цифры совпадают с расчётом. |
| P1 | Сделать шаблон сравнения площадок. | Запускать только после подтверждённых категорий по площадкам. |
| P2 | Библиотека шаблонов и визуальный бренд. | Несколько лёгких шаблонов без тяжёлых картинок и без зависимости от AI-image. |

### Таблица 6
| Блок v6.7 | Куда встроен |
| --- | --- |
| 0. Титул и история статусов | 12.1 |
| 1–2. Назначение/архитектура | 12.2 |
| 3–4. NEWSBOT и CTA | 12.3 |
| 5. Seller Helper | 12.4 |
| 6. Тарифная база | 12.5 |
| 7. MPSTATS | 12.6 |
| 8. Монитор изменений | 12.5 / 12.3 |
| 9. Монетизация | 12.6 / 8 |
| 10–14. DoD/rules/roadmap | 9 / 12.7 |
| 15. v5 ecosystem | 12.2 / 12.6 |
| 16–18. Full article | 12.3 |
| 19–20. RAG/monitor/audio/MAX | 12.3 / 12.6 |
| 21. Docobrazec | 12.4 / 12.6 |
| 22. Margin/VK | 12.4 / 12.6 |
| 23. Admin/Ozon | 12.3 / 12.5 |
| 24. Guard/Risk/news density | 12.3 / 12.4 |
| 25. Subscription/VK lead | 12.4 / 12.6 |
| 26. Yandex/RAG/growth | 12.5 / 12.6 |

### Таблица 7
| Параметр | Значение |
| --- | --- |
| Тип документа | Объединённый паспорт изделия + техническое задание направления |
| Основа | Паспорт NEWSBOT v2 + Seller Helper v3 и ТЗ Seller Ecosystem / Seller Helper Bot v1 |
| Главный рабочий контур | /opt/newsbot_v2 |
| Пользовательский helper-бот | /opt/helperbot |
| Платформа | MAX |
| Ссылка на Seller Helper Bot | https://max.ru/id771812324702_2_bot |
| Статус на 28.04.2026 | NEWSBOT v2 стабилизирован; Seller Helper подключён к NEWSBOT v2 через CTA; Ozon переведён на стандартный tariff layer marketplace_service_rate; добавлен план кнопки «читать полностью в канале»; зафиксировано расширение экосистемы: Seller Helper mini app как главный рабочий кабинет, Docobrazec как веб-витрина + юридический модуль, Offer Doctor как готовый лендинг/mini app и будущий модуль внутри Seller Helper. |
| Дополнение v5 | Кнопка «Читать полностью в канале»; Docobrazec внутри Seller Helper; Offer Doctor как маркетинговый модуль; отказ от отдельного лендинга для новостей/Seller Helper на ближайшем этапе. |
| Safe point 28.04.2026 | Реализована кнопка «Читать полностью» в MAX-канале: полный текст раскрывается в том же посте через callback-worker; дайджесты очищают грязные TG-заголовки и используют HTML-bold для MAX. |
| Статус на 29.04.2026 | Проведена ревизия RAG/Helper архитектуры; создан и проверен RAG Store; добавлен диагностический мост rag_bridge.py; создан надёжный вечерний монитор изменений условий и тарифов; первый монитор опубликован; cron на 22:30 MSK установлен. |
| Дополнение v6 | RAG Store + Helper bridge + надёжный сигнал-монитор: signal_monitor.py, signal_digest.py, tariff_signals, signal_digest_runs, run_signal_digest.sh. |
| Safe point 29.04.2026 | RAG: rag_documents=68, rag_documents_fts=68, rag_sources=13; источник числовых тарифов: /opt/newsbot_v2/data/unified_tariffs.db#clean_commissions; монитор изменений опубликован и защищён от дублей. |
| Статус v6.1 на 29.04.2026 | После safe point v6 закрыты операционные доработки NEWSBOT v2: аудиодайджест установлен в cron на 22:45; механизм очистки аудиофайлов установлен в cron на 03:20; логика кнопки «Читать полностью» расширена до материалов с raw_text/full_text_* от 300 символов; MAX API-правила вынесены в отдельные guardrails. |
| Дополнение v6.1 | Аудиодайджест + очистка аудио + расширенная кнопка full article + новые правила MAX API + обновлённый roadmap с фокусом на полноценный Seller Helper. |
| Safe point v6.1 29.04.2026 | signal_digest: 22:30; audio_digest: 22:45; cleanup_audio: 03:20; has_full_article(): порог 300 символов; callback-worker, PUT /messages и CTA Seller Helper не менялись; видеодайджест отложен как тяжёлый и хрупкий контур. |
| Статус v6.2 на 29.04.2026 | Приняты вводные по Docobrazec и Seller Helper; Docobrazec рассматривается как детерминированный document engine с анкетами, ФИО, паспортными данными, ФНС, ИП и реквизитами; его нужно встроить в Seller Helper mini app как юридический модуль, не смешивая персональные данные с RAG. |
| Дополнение v6.2 | Docobrazec как юридический движок Seller Helper + privacy-by-design + API-мост между Docobrazec, Seller Helper и RAG Store + правильные приоритеты roadmap перед началом полноценного Seller Helper. |
| Safe point v6.2 29.04.2026 | NEWSBOT v2 восстановлен после временного SyntaxError в has_full_article(); зависший кандидат id=32490 опубликован; full article callback подтверждён. Следующий фокус: P0 — расчётный MVP Seller Helper и защита данных; P1 — интеграция Docobrazec как юридического модуля; P2 — Legal RAG по законам/судебным кейсам. |
| Статус v6.3 на 30.04.2026 | NEWSBOT v2 и MAX-канал работают; Seller Helper получил простой расчёт маржи, кнопочный сценарий, НДС и понятный путь через кнопку «Рассчитать прибыль»; тестовая реклама VK запущена на MAX-канал «Инсайдер Селлер» как ядро экосистемы. |
| Дополнение v6.3 | MVP расчёта маржи + кнопочный UX Seller Helper + уточнение, что логистика/габариты/вес пока не входят в расчёт + тест VK-рекламы на MAX-канал, а не на Helper Bot напрямую. |
| Safe point v6.3 30.04.2026 | helperbot.service активен после правок; кнопка «Рассчитать прибыль» доступна в ответах; пошаговый расчёт проходит в бою; реклама VK запущена с тестовым бюджетом около 1600 ₽ и воронкой VK → MAX-канал → CTA → Seller Helper. |
| Статус v6.4 на 04.05.2026 | Стабилизирован контур официальных источников и админского контроля: вечерний монитор теперь учитывает обновления официальных документов и не пишет «изменений нет», если официальный источник обновлялся; в админке добавлен блок свежести источников, особенно по Ozon; административный alert приходит в личный MAX-чат через Seller Helper Bot; для Ozon создан отдельный диагностический отчёт. |
| Дополнение v6.4 | Упрощение архитектуры без лишних прослоек; rules_documents не считается обязательным боевым слоем расчётов; публичный монитор получил нормальный язык для подписчиков; Ozon имеет ручной контроль свежести файлов; Seller Helper получил исправление НДС в одиночных расчётах, но сравнение площадок и кнопки уточнения категорий остаются отложенными до безопасной реализации. |
| Safe point v6.4 04.05.2026 | get_official_updates() в signal_digest.py видит загрузки за день; preview без публикации показал official_updates=4 за 03.05 и official_updates=1 за 04.05; опубликованный текст должен говорить, что команда канала сверяет обновления и учитывает релевантные тарифы в Seller Helper после проверки. Админский alert работает из Seller Helper Bot, потому что chat_id относится к личному чату с helper-ботом. |
| Статус v6.5 на 06.05.2026 | После v6.4 закрыты ключевые стабилизационные точки: админка оформлена как systemd-сервис; вечерние контуры после правок отработали нормально; Seller Helper получил защиту категорий CATEGORY GUARD V2 и аналитический блок RISK INSIGHTS V1; исправлена проблема малого количества новостей через внешний GitHub TG fetcher и TG_JSON_LIMIT=150; подготовлен закреп для новых подписчиков канала. |
| Дополнение v6.5 | NEWSBOT v2: восстановлена плотность новостей и зафиксирована роль внешнего TG fetcher как критичного источника. Seller Helper: переход от простого калькулятора к аналитическому помощнику с выводом по риску товара. Ozon: правило обратной логистики зафиксировано как official rule, а пустой return tariffs.xlsx не считается боевым источником. Roadmap очищен: выполненное перенесено в закрытые пункты, устаревшее — в отдельный блок. |
| Safe point v6.5 06.05.2026 | helperbot.service после CATEGORY GUARD V2 и RISK INSIGHTS V1 обработал реальные MAX-запросы без Traceback; риск-блок показывает красную/зелёную зону и практические предложения. NEWSBOT после расширения TG JSON загрузил 111 items, loader работает с TG_JSON_LIMIT=150, collector добавил новые кандидаты, publisher опубликовал 2 новости и отправил один CTA Seller Helper. Оставшиеся pending не публиковались вручную и должны идти по cron. |
| Статус v6.7 на 13.05.2026 | Закрыт большой операционный патч: Яндекс Маркет переведён на API-импорт тарифов calculate; clean_commissions пополнена актуальным слоем Яндекса; админские предупреждения получили dedupe и больше не должны ежедневно спамить; улучшены текстовые и аудиодайджесты; добавлена семантическая защита от повторной публикации одинаковых тем; зафиксирован новый контур развития RAG под Legal, OfferDoctor, дизайн карточек и AI/маркетплейс-аналитику. |
| Дополнение v6.7 | Яндекс API tariffs + admin_alert_state dedupe + качество дайджестов и аудио + publisher semantic dedup + расширение RAG: юридический слой, офферы, карточки, дизайн/инфографика, AI-трафик, тренды продаж и инфополе для поиска MAX. |
| Safe point v6.7 13.05.2026 | Yandex Market API import: 16282 строк commission_only, схемы FBS/FBY по 8141 строке, fee range 0.5–61, source_file=yandex_market_api_tariffs_calculate.json, valid_from=2026-05-13; helperbot.service после импорта активен; audio cron снова включён на 22:45; llm.py, publisher_v2.py, formatters.py, audio_digest_story_builder.py и audio_digest_text_cleaner.py компилируются; MAX access guardrail: user_id и chat_id не смешивать. |

### Таблица 8
| Слой | Назначение | Текущий статус |
| --- | --- | --- |
| MAX-канал «Инсайдер Селлер» | Трафик, доверие, регулярные публикации, дайджесты, сигналы по тарифам и офертам | Работает; тестовая VK-реклама запущена на канал как ядро экосистемы |
| NEWSBOT v2 | Сбор RSS/TG, фильтрация, scoring, очередь, publisher, дайджесты, будущая админка | Стабилизирован |
| Seller Helper Bot | Прикладной помощник: комиссии, тарифы, будущий расчёт прибыли и сравнение площадок | MVP работает: комиссии/тарифы + простой расчёт маржи + НДС + кнопочный UX |
| Единая тарифная база | WB, Ozon, Яндекс; слои комиссий, логистики, возвратов, хранения, источников | Рабочий слой комиссий/тарифов подключён |
| Админка | Единый центр управления источниками, ключами, логами, тарифами, cron, публикациями, helper-сценариями | Направление зафиксировано |
| Лендинги/миниаппы | Внешний интернет-слой для рекламы, лидов, оплаты, SEO | Отдельный лендинг новостей/Seller Helper не создаётся; реклама ведёт в MAX-канал |
| RAG/база знаний | Оферты, юридические акты, судебные кейсы, история новостей и изменений | Первичный RAG Store создан; legal/RAG слой развивается |
| Docobrazec / юридический движок | Детерминированный конструктор документов: анкеты, реквизиты, условия, шаблоны, готовые документы; селлерский блок должен быть добавлен поверх существующей логики. | Есть B2C-база и логика; требуется селлерский блок и API-мост в Seller Helper |

### Таблица 9
| Путь | Роль | Правило |
| --- | --- | --- |
| /opt/newsbot_v2 | Главный рабочий контур NEWSBOT v2, база, тарифы, cron, publisher, digest | Все новые серверные правки NEWSBOT только здесь |
| /opt/helperbot | Пользовательский Seller Helper Bot | Запуск только через systemd helperbot.service |
| /opt/newsbot | Старый контур | Не использовать |

### Таблица 10
| Блок | Решение v5 | Что сохраняется из v4 |
| --- | --- | --- |
| MAX-канал «Инсайдер Селлер» | Остаётся главной точкой входа, источником трафика, доверия, новостей, офертных и тарифных сигналов. | Сохраняется текущая логика NEWSBOT v2, публикаций, дайджестов и CTA в Seller Helper. |
| Seller Helper mini app | Становится главным рабочим кабинетом / мозгом экосистемы. Внутри него постепенно собираются комиссии, маржа, юридический модуль, Offer Doctor и будущие инструменты. | Сохраняется задача точных комиссий, будущего расчёта маржи, сравнения WB/Ozon/Яндекс и честного налогового блока. |
| Docobrazec.ru | Остаётся отдельным веб-доменом и лендингом-витриной. Сам функционал юридического конструктора должен постепенно входить в Seller Helper mini app. | Сохраняется идея юридического/RAG-слоя и работы с документами, офертами, законами и судебными кейсами. |
| Offer Doctor | Уже имеет готовый лендинг и mini app. Стратегически должен быть доступен как маркетинговый модуль внутри Seller Helper. | Сохраняется самостоятельность бренда и существующий продуктовый контур Offer Doctor. |
| МАРК-разведчик | Фиксируется как дальний стратегический модуль AI/IP и конкурентной разведки для селлеров. | Не входит в ближайший MVP и не должен отвлекать от кнопки, комиссий, маржи и юридического слоя. |
| Отдельный лендинг Seller Helper / новостного канала | На ближайшем этапе не создаётся. Главная точка входа - MAX-канал, главный инструмент - Seller Helper mini app. | Лендинги сохраняются только там, где уже понятна роль: Offer Doctor и docobrazec.ru. |

### Таблица 11
| Веб-актив | Роль | Правило |
| --- | --- | --- |
| Offer Doctor | Готовый лендинг и mini app для маркетингового разбора оффера, карточки, УТП и текстов. | Сохраняется как отдельный продуктовый актив, но должен быть доступен из Seller Helper. |
| docobrazec.ru | Домен и заготовка под юридический лендинг / SEO-витрину. | Лендинг остаётся в вебе; функции конструктора документов встраиваются в Seller Helper. |
| Инсайдер Селлер / Seller Helper | MAX-канал + mini app, без отдельного лендинга на ближайшем этапе. | Не распылять фокус и инфраструктуру до готовности платных сценариев. |

### Таблица 12
| Сценарий | Что делает Seller Helper | Когда подключается Offer Doctor |
| --- | --- | --- |
| Товар даёт слабую маржу | Показывает экономику товара и предупреждает о риске. | Предлагает улучшить оффер, цену, УТП или карточку. |
| Новость влияет на продажи категории | Даёт вывод «что это значит для селлера». | Предлагает адаптировать позиционирование и текст карточки. |
| Селлер готовит запуск товара | Считает комиссию, маржу и налоговый блок. | Помогает сформулировать оффер и продающее описание. |

### Таблица 13
| Слой базы | Для чего нужен |
| --- | --- |
| Тарифы и комиссии | WB, Ozon, Яндекс; комиссии, логистика, возвраты, хранение, прочие удержания, налоговый блок. |
| Оферты и изменения условий | Мониторинг условий маркетплейсов, вечерние дайджесты, юридические и тарифные сигналы. |
| Юридические документы | Шаблоны, претензии, законы, судебные кейсы, справочные материалы. |
| Маркетинговые знания | Офферы, УТП, карточки, тексты, фреймворки разбора товара. |
| История новостей и действий | Связь новости с выводом, расчётом, юридическим риском и пользовательским действием. |

### Таблица 14
| Сценарий publisher_v2 | Поведение CTA |
| --- | --- |
| Опубликована 1 новость | После неё отправляется один CTA в Seller Helper |
| Опубликовано несколько новостей | CTA отправляется только один раз после последней новости |
| Опубликовано 0 новостей | CTA не отправляется |
| CTA не отправился | Публикация новостей не считается сломанной; ошибка CTA логируется отдельно |

### Таблица 15
| Файл | Назначение | Текущее правило |
| --- | --- | --- |
| collector_v2.py | Сбор RSS/TG JSON, применение seller_filter, запись в очередь | Должен быть главным местом маршрутизации publish/digest/drop |
| seller_filter.py | Единая логика отбора seller-релевантных новостей | Должен исключать рекламу, мусор, самопрезентации и пропускать важные тарифные/офертные сигналы |
| publisher_v2.py | Финальная публикация approved publish items | Доверяет collector, не переигрывает логику отбора |
| digest_v2.py | Утренний/вечерний дайджест | Должен делить условия/тарифы/выплаты/оферты и прочие важные новости |
| publisher.py | Отправка в MAX, кнопки, очистка текста | Теперь поддерживает CTA-кнопку через add_helper_button |

### Таблица 16
| Элемент | Решение |
| --- | --- |
| Название кнопки | Читать полностью в канале |
| Зачем нужна | Часть источников приходит из Telegram или других внешних площадок, куда у пользователей из РФ может не быть стабильного доступа. Пользователь должен иметь возможность прочитать материал внутри MAX. |
| Где показывать | Только под новостями, где в базе есть полный очищенный текст статьи. Если полного текста нет, кнопку не показывать. |
| Как работает MVP | По нажатию публикуется отдельное сообщение-продолжение в канал с полным текстом, заголовком, пометкой «Полный текст по материалу выше» и ссылкой на источник внизу. |
| Защита от дублей | Полный текст публикуется один раз. Повторное нажатие не должно создавать дубль. |
| Сосуществование с CTA | Под новостью могут быть две кнопки: «Проверить комиссию и прибыль» и «Читать полностью в канале». CTA в Seller Helper сохраняется. |

### Таблица 17
| Поле | Назначение |
| --- | --- |
| full_text_raw | Исходный полный текст из RSS/TG/парсера, если он доступен. |
| full_text_clean | Очищенный полный текст для публикации в канале. |
| full_text_available | Флаг, можно ли показывать кнопку «читать полностью». |
| full_text_source_type | Тип источника полного текста: RSS, TG, parser, manual, other. |
| expanded_message_id | ID сообщения с опубликованным полным текстом, чтобы не создавать дубли. |
| expanded_at | Дата/время публикации полного текста. |
| expanded_by_clicks | Счётчик кликов/попыток раскрытия. |
| source_access_restricted | Флаг для источников, где внешний переход может быть проблемным для пользователя. |

### Таблица 18
| Компонент | Что изменено | Роль в новой функции |
| --- | --- | --- |
| publisher.py | send_message() теперь поддерживает callback-кнопку и возвращает JSON-ответ MAX. | Позволяет получить message.body.mid и добавить кнопку «Читать полностью». Не ломает существующую CTA-кнопку Seller Helper. |
| publisher_v2.py | После отправки новости извлекает message.body.mid и сохраняет его в news.max_message_id. | Даёт worker-у возможность редактировать именно исходный пост. |
| full_article_callback_worker.py | Новый обработчик callback-событий MAX. | Слушает нажатия кнопки, достаёт raw_text из базы и раскрывает полный текст в том же посте. |
| newsbot-fullarticle.service | Новый systemd-сервис, включённый в автозапуск. | Постоянно держит worker запущенным, чтобы кнопки работали без ручного запуска. |
| digest_v2.py | Добавлена очистка заголовков и HTML-выделение источников/заголовков блоков. | Делает дайджесты аккуратнее и предотвращает попадание обрывков начала статьи в заголовок. |

### Таблица 19
| Поле | Тип / смысл | Назначение |
| --- | --- | --- |
| max_message_id | TEXT | ID исходного сообщения MAX, берётся из message.body.mid. Нужен для редактирования короткого поста в полный текст. |
| full_article_message_id | TEXT | Служебное поле, оставлено для совместимости с первым тестовым вариантом, где полный текст публиковался отдельным сообщением. |
| full_article_published_at | TEXT | Фиксирует момент раскрытия полного текста. Используется как защита от повторного раскрытия/дублирования. |
| full_article_clicks | INTEGER DEFAULT 0 | Счётчик нажатий по кнопке «Читать полностью». |

### Таблица 20
| Компонент | Путь / таблица | Статус на 29.04.2026 | Назначение |
| --- | --- | --- | --- |
| RAG Store | /opt/newsbot_v2/data/rag_store.db | Создан и проверен | Официальные тексты, новости, оферты, кейсы, регуляторика, объяснения. Не является расчётной тарифной базой. |
| RAG documents | rag_documents | 68 строк | Документы и новости с полями source_type, marketplace, document_type, topic, rag_layer, trust_level. |
| RAG FTS | rag_documents_fts | 68 строк, индекс пересобран | Полнотекстовый поиск по title, clean_text, markdown_text. Backup перед rebuild: data/rag_store.db.bak_20260429_115101. |
| RAG sources | rag_sources | 13 источников | Реестр official, media, telegram и internal_db источников. |
| Тарифная база Helper | /opt/newsbot_v2/data/unified_tariffs.db#clean_commissions | Source of truth | Единственный рабочий источник числовых комиссий и тарифов для расчётов. |
| Локальная старая копия | /opt/helperbot/data/unified_tariffs.db | Не source of truth | Может содержать устаревший Ozon Select слой; не использовать для боевых расчётов. |
| RAG architecture file | /opt/newsbot_v2/RAG_ARCHITECTURE.md | Создан/обновлён | Фиксирует разделение RAG Store и тарифной базы. |
| Диагностический bridge | /opt/helperbot/rag_bridge.py | Создан и протестирован | Тестирует связку clean_commissions + RAG Store + налоговый блок. Не встроен в production Helper. |
| Сигнальный радар | /opt/newsbot_v2/signal_monitor.py | Создан | Собирает потенциальные сигналы в tariff_signals. |
| Вечерний монитор | /opt/newsbot_v2/signal_digest.py | Создан, опубликован первый пост | Формирует строгий красивый отчёт и отправляет через publisher.send_message. |
| Таблица сигналов | news_queue.db / tariff_signals | new=118, published=6 на момент проверки | Хранит сигналы тарифов, оферт, выплат, регуляторики, логистики и др. |
| Защита от дублей | news_queue.db / signal_digest_runs | 2026-04-29 published, item_count=2 | Не даёт повторно публиковать монитор в тот же день. |
| Cron | /opt/newsbot_v2/run_signal_digest.sh | 30 22 * * * | Ежедневный запуск monitor + digest в 22:30 MSK. |

### Таблица 21
| Пункт / старая формулировка | Новый статус v6 | Почему важно | Правило дальше |
| --- | --- | --- | --- |
| RAG/база знаний в v5 местами указана как “планируется”. | Первичный RAG Store уже создан и проверен: rag_documents=68, rag_sources=13. | RAG теперь не абстрактный план, а рабочий SQLite-контур. | Развивать RAG как общий текстовый слой, но не смешивать его с тарифными строками. |
| Возможная путаница между /opt/helperbot/data/unified_tariffs.db и /opt/newsbot_v2/data/unified_tariffs.db. | Source of truth — только /opt/newsbot_v2/data/unified_tariffs.db#clean_commissions. | Локальная helperbot-копия показала Ozon Select и не соответствует боевому Helper. | Все новые расчётные проверки и rag_sources internal_db ведут на /opt/newsbot_v2/data/unified_tariffs.db. |
| Диагностика bridge сначала показала Ozon Select 7/9%. | Это было следствие обращения к неправильной/устаревшей базе и отсутствия fee_type фильтра. | Нельзя считать Ozon сломанным: в рабочей базе есть marketplace_service_rate. | Для Ozon всегда фильтровать fee_type=marketplace_service_rate. Select — только test/reference. |
| Автоимпорт официальных сайтов через простой urllib. | Для Ozon/WB не надёжно: Ozon дал redirect 307, WB API docs — HTTP 498, WB seller terms — слишком мало текста/JS. | Нельзя строить ingestion официального слоя на простом HTML-парсинге. | Ozon — официальные Excel; WB/Яндекс — API/DB/export; официальные каналы — signal layer. |
| legal_docs / legal_chroma внутри /opt/helperbot. | legal_docs в unified_tariffs.db пустая; legal_chroma считаем старым экспериментальным слоем. | Иначе появятся две юридические RAG-базы. | Основной legal_official слой развивать в /opt/newsbot_v2/data/rag_store.db. |
| legal_official слой кажется готовым для всех площадок. | Фактически imported official/high сейчас только по Яндекс Маркету: Yandex Market rates и Yandex Market seller docs. | Ozon/WB official legal docs ещё нужно загрузить отдельным способом. | Добавить ручной/файловый import для оферт Ozon/WB и отдельную верификацию. |
| Старый монитор комиссий/тарифов. | Старый монитор не считаем рабочим. Создан новый MVP: signal_monitor.py + signal_digest.py. | Нужен надёжный вечерний отчёт в канал, а не публикация всех совпадений по словам. | Публиковать только строгий фильтр. Сырой radar хранить в tariff_signals. |
| Прямая отправка MAX из signal_digest через access_token в URL. | Дала HTTP 401 Unauthorized. | Отправка должна быть через уже рабочий publisher.py. | Использовать publisher.send_message с Authorization header и chat_id, как в NEWSBOT v2. |
| Автоматический pretty patch signal_digest.py. | Вызвал SyntaxError: unterminated string literal line 312. | Не проблема архитектуры, а ошибка точечной вставки блока. | Файл переписан целиком чистой версией, py_compile пройден. |
| Full article MVP в раннем плане мог публиковать отдельную копию. | Реализованная логика v5/v6: полный текст раскрывается в том же MAX-посте через callback-worker. | Избегаем дублей в канале. | Считать актуальной реализацию same-post edit через newsbot-fullarticle.service. |

### Таблица 22
| Тест | Команда / объект | Результат | Вывод |
| --- | --- | --- | --- |
| FTS RAG | INSERT INTO rag_documents_fts(...) VALUES("rebuild") + поиск Yandex OR Яндекс | rag_documents=68, rag_documents_fts=68; Yandex docs находятся поиском. | FTS синхронизирован после импорта official docs. |
| RAG sources | SELECT из rag_sources | 13 источников: official, media, telegram, internal_db. | Internal DB источники Helper зарегистрированы. |
| Ozon bridge | python3 rag_bridge.py "чайник походный" --marketplace ozon | Чайники походные: FBY 40%, FBS 47%, EXPRESS 40%, DBS 47%; fee_type=marketplace_service_rate. | Ozon Select исключён из bridge-ответа. |
| WB bridge | python3 rag_bridge.py "ботинки" --marketplace wildberries | Найдены ставки WB, mapping wildberries -> wb работает. | Нужна приоритизация схем, чтобы 3% express не выглядело как главный benchmark. |
| Yandex bridge | python3 rag_bridge.py "косметика" --marketplace yandex_market | Найдены ставки, mapping yandex_market -> yandex работает. | Нужен ranking: косметика не должна первым делом давать автокосметику. |
| Signal digest dry-run | python3 signal_digest.py | После строгого фильтра осталось 2 сигнала: ФАС по выплатам и обновление оферты WB. | Формат стал пригоден для канала. |
| Signal digest publish | python3 signal_digest.py --publish | Запись signal_digest_runs: 2026-04-29 published item_count=2. | Первый монитор опубликован, защита от дублей работает. |
| Cron | crontab -l | 30 22 * * * /opt/newsbot_v2/run_signal_digest.sh ... | Ежедневный запуск установлен на 22:30 MSK. |

### Таблица 23
| Приоритет | Задача | Что сделать | Definition of Done |
| --- | --- | --- | --- |
| P0 | Проверить штатный cron монитора | После 22:30 проверить logs/signal_digest.log и signal_digest_runs. | Нет дублей; если уже опубликовано сегодня — лог пишет already published; на следующий день выходит новый монитор. |
| P0 | Добавить official_channel источники | Завести официальные TG/MAX-каналы Ozon/WB/Яндекс как source_type=official_channel, rag_layer=official_signal, trust_level=high. | Официальные каналы отделены от обычных telegram/news_signal. |
| P0 | Улучшить source status admin view | Показать в админке статусы: unified_tariffs, clean_commissions, rag_store, tariff_signals, last digest run, last source update. | Админ видит, что проверено, что обновлено, что требует ручной проверки. |
| P1 | Ozon official ingestion | Оформить полуавтоматический импорт официальных Excel Ozon: marketplace_service_rate, logistics, returns, storage, compensation coefficient. | Новый файл создаёт слой/версию; Select не попадает в основной расчёт. |
| P1 | WB schemes ranking | Разделить основные и специальные схемы WB. Не показывать 3% express/self-delivery как главный benchmark. | Ответы и сравнения не вводят селлера в заблуждение “от 3%”. |
| P1 | Yandex ranking | Улучшить поиск и ranking категорий: косметика должна предпочитать beauty/cosmetics, а не автокосметику. | На broad-запросах выдача ближе к пользовательскому смыслу. |
| P1 | Legal official import | Загрузить оферты/условия Ozon и WB через manual_file/pdf/txt import, так как простой web import не надёжен. | rag_documents получает legal_official/high по Ozon/WB. |
| P1 | Bridge user-facing format | Сделать красивый не-debug ответ bridge: ставка + схема + источник + RAG контекст + налоговый блок. | Готов формат для будущей интеграции в Helper без технических логов. |
| P2 | RAG ranking/filtering | Если есть official/high, news_signal показывать только как дополнительный сигнал, а не как основной контекст. | Ответы не смешивают официальный документ и Telegram как равные источники. |
| P2 | Монитор без изменений | Отработать сценарий “за день надёжных изменений не обнаружено” в канале. | Пост выглядит аккуратно и перечисляет Ozon/WB/Яндекс. |
| P2 | Паспорт v6 финализация | Внести этот блок v6 в основной паспорт и сохранить как новый safe point. | Документ содержит устаревшие/изменённые пункты отдельно и не путает будущую работу. |

### Таблица 24
| Контур | Расписание | Команда / лог | Статус |
| --- | --- | --- | --- |
| Вечерний монитор изменений | 22:30 ежедневно | /opt/newsbot_v2/run_signal_digest.sh >> /opt/newsbot_v2/logs/signal_digest.log 2>&1 | Работает; защита от дублей через signal_digest_runs. |
| Аудиодайджест | 22:45 ежедневно | /opt/newsbot_v2/run_audio_digest.sh >> /opt/newsbot_v2/logs/audio_digest.log 2>&1 | Включён после одобрения тестового выпуска. Отдельный контур, не смешивать с signal_digest. |
| Очистка аудиофайлов | 03:20 ежедневно | /opt/newsbot_v2/cleanup_audio_digest.sh; лог /opt/newsbot_v2/logs/audio_cleanup.log | Проверена вручную: WAV 2 дня, временные MP3 7 дней, финальные MP3 30 дней. |

### Таблица 25
| Приоритет | Задача | Что сделать | Definition of Done |
| --- | --- | --- | --- |
| P0 | Наблюдение за штатным cron NEWSBOT v2 | Проверить ближайшие прогоны signal_digest, audio_digest, cleanup_audio и публикации с кнопкой «Читать полностью». | Нет дублей; логи без критичных ошибок; новые материалы с raw_text от 300 символов получают кнопку; callback раскрывает полный текст в том же посте. |
| P0 | Начать полноценный Seller Helper MVP | Собрать первый пользовательский сценарий расчёта: маркетплейс, категория/товар, цена продажи, себестоимость, схема, комиссия, налоговый блок, остаток. | Ответ показывает цену продажи, удержания маркетплейса, сумму к выплате, налоговую базу, налог и остаток после налога; отдельно честно указаны неучтённые расходы. |
| P0 | Зафиксировать расчётный source of truth | Для Seller Helper использовать /opt/newsbot_v2/data/unified_tariffs.db#clean_commissions. Для Ozon — только fee_type=marketplace_service_rate. | Ozon Select не попадает в основной ответ; расчётные ответы не берут устаревшую /opt/helperbot/data/unified_tariffs.db. |
| P1 | Улучшить ranking категорий и схем | WB: не показывать специальные схемы 3% как главный benchmark. Яндекс: улучшить смысловой ranking, чтобы broad-запросы не уводили в нерелевантные категории. | Похожие варианты помогают уточнить товар, но не вводят селлера в заблуждение минимальной ставкой. |
| P1 | Подключить official_signal/high источники | Добавить официальные TG/MAX/документальные источники Ozon/WB/Яндекс как сигнальный слой, не как автоматическое изменение тарифов. | Официальный сигнал создаёт задачу проверки документа/тарифного слоя, но не меняет расчёт Seller Helper без подтверждения. |
| P1 | Подготовить legal/RAG основу для Seller Helper | Ручным/файловым импортом добавить оферты и условия Ozon/WB в RAG Store; official/high должен иметь приоритет над news_signal. | RAG Store помогает объяснять условия и юридические риски, но числовые комиссии остаются в clean_commissions. |
| P2 | Админский статус источников и cron | В админке показать статусы unified_tariffs, clean_commissions, rag_store, tariff_signals, signal_digest_runs, audio_digest, cleanup_audio. | Админ видит дату обновления, источник, статус слоя, последний успешный прогон и ошибки без просмотра консоли. |
| Отложено | Видеодайджест | Не делать на ближайшем этапе. | Контур не добавляется, пока NEWSBOT v2 и Seller Helper не станут устойчивыми в платных/пользовательских сценариях. |

### Таблица 26
| Блок | Что сделано / принято | Текущий статус |
| --- | --- | --- |
| Архитектура | Зафиксирован принцип минимального числа прослоек. Чем меньше обязательных промежуточных слоёв между источником, базой и ответом, тем ниже риск хрупкости. | Принято как архитектурное правило для следующей версии паспорта и разработки. |
| rules_documents | Таблица может хранить официальный текст/фрагменты и помогать в диагностике, но не должна становиться обязательным боевым слоем расчётов или ответов Seller Helper. | Оставить как вспомогательный/архивно-диагностический слой; не делать источником истины для числовых тарифов. |
| Вечерний монитор | signal_digest.py дополнен функцией get_official_updates(): если за день официальные документы/тарифные источники обновлялись, публичный отчёт не пишет «изменений нет». | Проверено локально без публикации: за 03.05 найдено 4 обновления, за 04.05 найдено 1 обновление. |
| Публичный язык монитора | Убраны внутренние формулировки «официальный слой», «diff-проверка», «фразу изменений нет писать нельзя». | В канале используется нейтральная формулировка: команда сверяет обновления с официальными документами и учитывает релевантные изменения после проверки. |
| Админка | Добавлен блок «Свежесть официальных источников» и ссылка на подробную Ozon-диагностику. | Работает в NEWSBOT v2 admin app. После патча admin_app.py был перезапущен uvicorn-процесс на 8088. |
| Админские уведомления | admin_alert.py отправляет личное сообщение «Проверь админку» при административных сигналах по официальным источникам. | Проверено: отправка через newsbot дала chat.not.found, после перевода на токен Seller Helper Bot сообщение пришло. |
| Ozon freshness | Для Ozon введён отдельный административный контроль: текущий боевой файл, valid_from, rows marketplace_service_rate, возраст файла, Ozon-сигналы после загрузки, Select-защита. | Работает как жёлтый/ручной контроль: Ozon требует ручной загрузки официальных Excel/PDF. |
| Ozon diagnostics | Создан /opt/newsbot_v2/ozon_source_diagnostics.py: отчёт объясняет, откуда берётся статус свежести и какие файлы желательно проверять/подгружать. | Сформирован отчёт /tmp/ozon_source_diagnostics.txt; нужен как основа для улучшения админского текста. |
| Seller Helper / НДС | В одиночных расчётах НДС отображается отдельной строкой и вычитается из остатка; НДС больше не должен попадать в товарный запрос. | Проверено локально на Ozon, WB и Яндекс. Но качество подбора категорий на Яндексе требует доработки. |
| Сравнение площадок | Публичное сравнение WB/Ozon/Яндекс оставлено отключённым до нормального сопоставления категорий. | Правильное решение: не вводить селлера в заблуждение ложным выводом «где выгоднее». |

### Таблица 27
| Тип данных | Источник истины | Что не должно происходить |
| --- | --- | --- |
| Числовые комиссии и тарифы для расчёта | /opt/newsbot_v2/data/unified_tariffs.db / clean_commissions и будущие нормализованные fee-components. | Не брать числа из RAG, новостей или случайных фрагментов rules_documents. |
| Официальные документы и оферты | Официальные Excel/PDF/страницы маркетплейсов, сохранённые как архив/фрагменты и проверяемые через админку. | Не превращать каждую текстовую нарезку в боевой расчётный слой. |
| Новости и TG-сигналы | news_queue.db, tariff_signals, rules_signals, official_channel_posts. | Не считать новость изменением тарифа без официального подтверждения. |
| RAG/юридический и смысловой контур | Отдельный чистый контур для объяснений, оферт, кейсов, законов и справки. | Не смешивать RAG с персональными данными и не использовать его как источник расчётных ставок. |
| Административная свежесть источников | Лёгкий registry/диагностика, админский индикатор, дата последнего файла, сигналы после загрузки. | Не создавать тяжёлую витрину, от которой зависит весь расчёт. |

### Таблица 28
| Старый язык | Новый публичный язык |
| --- | --- |
| «Официальный слой обновлялся» | «За день обновлялись официальные источники маркетплейсов» |
| «Это ещё не означает автоматическое изменение условий, но фразу “изменений нет” писать нельзя» | «Это не означает, что тарифы или условия уже изменены в расчётах. Команда канала сверяет обновления с официальными документами» |
| «Требует diff-проверки» | «Если изменения действительно влияют на продавцов, релевантные тарифы и условия будут учтены в Seller Helper после проверки» |
| «Новостные и TG-сигналы...» в техническом тоне | «Публикуем только проверенные изменения, чтобы не вводить селлеров в заблуждение» |

### Таблица 29
| Ozon-файл / слой | Зачем нужен | Статус на 04.05.2026 |
| --- | --- | --- |
| marketplace-services-rates-01-04-2026.xlsx | Главный боевой файл для расчёта комиссий/вознаграждения Ozon по схемам FBY/FBS/EXPRESS/DBS. | Найден; source_status=usable; role=standard_marketplace_service_rate; rows marketplace_service_rate=44128; valid_from=2026-04-01. |
| Полный список комиссий и тарифов.pdf | Логистика, возвраты, размещение, штрафы, услуги и дополнительные удержания. | Найден; нужен как справочный/официальный тарифный документ. |
| return tariffs 2026-04-24.xlsx | Возвраты, обратная логистика, вывозы, утилизация, обработка возвратов. | Файл найден, но rows_imported=0; требуется проверить импортёр/формат. |
| logistika-fbo-fbs-06042026.xlsx | Логистика FBO/FBS/realFBS, будущий компонент полной маржи. | Найден, но источник был в unknown; требуется аккуратно классифицировать как Ozon и нормализовать без лишних прослоек. |
| Размещение / хранение / temporary placement | Хранение и размещение влияют на остаток после удержаний. | Проверять вручную в официальном кабинете/документации Ozon и загружать свежий файл при появлении. |
| Оферта / условия работы продавца | Юридический слой: штрафы, блокировки, возвраты, обязанности продавца. | Нужна отдельная проверка официального Ozon-документа; случайно загруженная WB-оферта не должна попадать в Ozon-ответы. |

### Таблица 30
| Компонент | Решение |
| --- | --- |
| admin_alert.py | Формирует административное сообщение по официальным источникам и Ozon freshness. |
| ADMIN_ALERT_CHAT_ID | Личный чат администратора с Seller Helper Bot; chat_id 220878972 относится именно к helper-боту, а не к канальному newsbot. |
| ADMIN_ALERT_BOT_TOKEN | Отдельный токен из /opt/helperbot/.env, чтобы личное сообщение отправлялось из Seller Helper Bot. |
| run_signal_digest.sh | После signal_digest.py --publish запускает /opt/newsbot_v2/admin_alert.py --send || true. Ошибка alert не должна ломать вечерний дайджест. |
| Публичный канал | Не получает фразы «администратор должен проверить админку». Вместо этого: команда канала сверяет официальные обновления и учитывает релевантные изменения после проверки. |

### Таблица 31
| Направление | Решение / статус |
| --- | --- |
| Одиночные расчёты | Работают как MVP: показывают комиссию, сумму к выплате после комиссии, налоговую базу, налог, НДС при указании и остаток после удержаний. |
| Налоговый блок | Сохраняется ключевая фишка: налог считается с цены продажи/дохода от реализации, а не с суммы после комиссии маркетплейса. |
| НДС | В одиночных расчётах НДС отображается отдельной строкой и вычитается из остатка. |
| Подбор категорий | Остаётся проблемным, особенно на Яндексе: пример «крем для лица» может подбираться как «Пудра». Это нельзя считать боевой точностью. |
| Сравнение площадок | Отключено до доработки сопоставления категорий, чтобы не выдавать недостоверный вывод «где выгоднее». |
| Кнопки уточнения категории | Нужны, но отложены. Агрессивный патч в handle_text показал риск поломки polling-бота. Следующая реализация только через безопасную ветку/backup/локальный тест/минимальный callback без вмешательства в расчётный контур. |

### Таблица 32
| Что устарело / изменено | Новое правило |
| --- | --- |
| Публичная формулировка «официальный слой обновлялся» | В канале писать по-человечески: «обновлялись официальные источники маркетплейсов». |
| Фраза «фразу “изменений нет” писать нельзя» | Не использовать в публичном тексте. Это внутреннее правило, а не сообщение для подписчиков. |
| Фраза «требует diff-проверки» в канале | Заменить на: команда сверяет обновления с официальными документами; релевантные изменения будут учтены в Seller Helper после проверки. |
| Публикация админских инструкций в канал | Админские инструкции уходят в личный alert, публичный канал получает редакционный текст. |
| rules_documents как обязательный боевой слой | Не принимается. Таблица может быть архивом/поиском/диагностикой, но расчёты берут числа из clean_commissions и нормализованных tariff components. |
| Вечерний монитор «изменений нет», когда загружались официальные документы | Считать неверным. Если official_updates > 0, монитор должен показывать обновление источников и нейтральное пояснение. |
| Ozon Select как источник пользовательского расчёта | Не использовать. Боевой Ozon-расчёт только по standard marketplace_service_rate и подтверждённым тарифным файлам. |
| Кнопки категории через агрессивный guard в начале handle_text | Отложить. Реализовывать только безопасным отдельным контуром с тестами и без риска остановки helperbot. |
| Сравнение площадок на основе текущего автоподбора категорий | Оставить отключённым до качественного category matching и ручного UX уточнения категории. |

### Таблица 33
| Приоритет | Задача | Комментарий |
| --- | --- | --- |
| P0 | Проверить/восстановить стабильность helperbot.service после эксперимента с кнопками. | Не продолжать продуктовые правки, пока боевой бот не отвечает стабильно. Использовать последний safe backup до hard-category patch. |
| P0 | Оставить вечерний монитор в новом публичном языке и дать cron отработать штатно. | Ручной публикации не требуется; проверка уже сделана через локальный preview без MAX-отправки. |
| P0 | Дочистить админский блок свежести Ozon по-русски. | Должно быть понятно: почему статус жёлтый, откуда информация, какие именно файлы желательно проверить/подгрузить. |
| P1 | Разобрать Ozon return tariffs с rows_imported=0. | Проверить формат Excel и импортёр; возвраты важны для полной маржи. |
| P1 | Классифицировать Ozon logistics/storage файлы без создания хрупкой витрины. | Цель — future fee components, а не новый обязательный слой. |
| P1 | Сделать лёгкий контроль ошибочной загрузки документов в админке. | Например предупреждать, если Ozon-загрузка содержит Wildberries/Вайлдберриз. |
| P1 | Улучшить ranking категорий Яндекс/WB/Ozon. | Особое внимание: крем/косметика/чайник/ботинки и другие broad-запросы. |
| P2 | Вернуть кнопки уточнения категории, но безопасно. | Отдельный патч, локальные тесты, callback без тяжёлого вмешательства в handle_text. |
| P2 | Вернуть сравнение площадок только после сопоставления категорий. | Сравнение должно быть платным/ценным сценарием, но не должно врать. |
| P2 | Постепенно нормализовать logistics/returns/storage/эквайринг/прочие удержания. | Только после стабилизации простого расчёта и спроса. |

### Таблица 34
| Блок | Что сделано / принято | Текущий статус |
| --- | --- | --- |
| Админка NEWSBOT v2 | Админка переведена из ручного uvicorn-процесса в systemd-сервис newsbot-admin.service; проверены 403 без токена и 200 OK с ADMIN_TOKEN. | Выполнено. Считать задачу оформления админки как systemd-сервиса закрытой. |
| Вечерние контуры | После правок предыдущего дня вечерний монитор, cron/дайджесты и связанные публикационные изменения не показали явных сбоев по пользовательскому контролю. | Выполнено как наблюдение. Продолжать штатный мониторинг логов, но не держать как блокер. |
| Ozon обратная логистика | Правило обратной логистики Ozon зафиксировано как official rule: условия с 06.04.2026; обратная логистика включает возврат/невыкуп/отмену; тариф равен тарифу логистики без наценки за нелокальную продажу. | Выполнено как справочное правило. Отдельный пустой return tariffs.xlsx не считать боевым источником. |
| CATEGORY GUARD V2 | В max_bot_polling.py добавлен защитный слой, который не даёт считать маржу по явно ошибочным категориям: общий «чайник», Яндекс «крем для лица», общий Ozon «носки» и похожие случаи. | Выполнено. Guard защищает расчёт до полноценного ranking/уточнения категории. |
| Стабильность helperbot.service | Исправлен NameError html, вызов main() перенесён в конец файла после guard-блока; py_compile и прямые handle_text-тесты прошли; helperbot.service перезапущен и активен. | Выполнено. Старый блокер из v6.4 по восстановлению Helper закрыт. |
| RISK INSIGHTS V1 | В Seller Helper добавлен блок «Вывод Seller Helper»: зелёная/красная зона, объяснение факторов риска, рекомендации по цене, себестоимости, категории, логистике, возвратам и рекламе. | Выполнено. Боевой MAX-проверкой подтверждено: ответы уходят без Traceback. |
| Плотность новостей NEWSBOT v2 | Найдена причина малого количества новостей: внешний GitHub TG fetcher отдавал устаревший/узкий tg_posts.json, а локальный loader был ограничен limit=50. Каналы и лимиты расширены; TG_JSON_LIMIT=150. | Выполнено. Loader показал 111 items; collector добавил свежие кандидаты; publisher опубликовал 2 новости и отправил один CTA. |
| Ручная публикация после фикса | После проверки publisher вручную опубликованы только 2 новости для safe point; оставшиеся pending решено не добивать вручную. | Принятое правило: обычный поток идёт через cron, ручной publisher — только для проверки/safe point. |
| Закреп канала | Подготовлен текст закрепа для подписчиков: что уже полезно в канале, чем пользоваться, как работает Seller Helper, налоговый нюанс и риск-вывод. | Подготовлено. Следующий шаг — опубликовать и закрепить в MAX-канале. |

### Таблица 35
| Пункт v6.4 | Новый статус v6.5 | Что дальше |
| --- | --- | --- |
| Проверить/восстановить стабильность helperbot.service после эксперимента с кнопками. | Выполнено. helperbot.service активен, реальные MAX-запросы обработаны, отправка сообщений подтверждена. | Не возвращаться к агрессивным патчам handle_text. Все будущие UX-кнопки делать отдельным безопасным контуром. |
| Оставить вечерний монитор в новом публичном языке и дать cron отработать штатно. | Выполнено по пользовательскому наблюдению: вечерние контуры после правок отработали нормально. | Продолжать обычный контроль logs/signal_digest.log и signal_digest_runs, без ручной публикации без причины. |
| Дочистить админский блок свежести Ozon по-русски. | Частично выполнено: админка стала systemd-сервисом, alert работает, Ozon-диагностика есть. Полная редакционная полировка текста остаётся задачей P1. | Сделать человекочитаемую страницу/блок: текущий файл, valid_from, rows, сигналы после загрузки, что именно проверить вручную. |
| Разобрать Ozon return tariffs с rows_imported=0. | Частично снято правило: отдельный пустой return tariffs.xlsx не является боевым источником для обратной логистики. | Нормализовать возвраты через official rule + логистические тарифы Ozon; не пытаться считать возврат из пустого Excel. |
| Классифицировать Ozon logistics/storage файлы без хрупкой витрины. | Остаётся открытым. | Делать только как future fee components после стабилизации простого расчёта и интереса пользователей. |
| Улучшить ranking категорий Яндекс/WB/Ozon. | Частично выполнено через CATEGORY GUARD V2: расчёт блокируется при явно опасном подборе. | Полноценный ranking и кнопки уточнения категории остаются P1/P2. Guard — не замена ranking, а защита от вредного ответа. |
| Вернуть кнопки уточнения категории безопасно. | Не выполнено и правильно отложено. | Делать отдельным минимальным callback-сценарием: backup, py_compile, локальные handle_text-тесты, затем restart service и live-log. |
| Вернуть сравнение площадок только после сопоставления категорий. | Остаётся отложенным. | Сравнение WB/Ozon/Яндекс не включать, пока категория на каждой площадке не подтверждается пользователем или надёжным mapping. |
| Улучшить onboarding в MAX-канале. | Частично выполнено: текст закрепа подготовлен. | Опубликовать и закрепить. После публикации проверить, ведёт ли он к переходам в Helper и запускам расчёта. |

### Таблица 36
| Что устарело / изменилось | Новое правило v6.5 | Почему важно |
| --- | --- | --- |
| Seller Helper как простой калькулятор остатка. | Теперь Seller Helper должен позиционироваться как аналитический помощник: расчёт + риск-вывод + предложения, что изменить. | Простая цифра без вывода плохо помогает селлеру. Ценность проекта — предупредить о минусе до закупки и запуска. |
| Блокер «helperbot.service нужно восстановить после экспериментов». | Считать закрытым: service активен, CATEGORY GUARD V2 и RISK INSIGHTS V1 прошли боевую проверку. | Roadmap не должен держать закрытый аварийный пункт как активную задачу. |
| Искать причину малого числа новостей только в фильтрах collector/scoring. | Главная найденная причина — внешний GitHub TG fetcher и лимит локального loader. Этот контур теперь критичен для плотности новостей. | Без свежего tg_posts.json локальный collector может работать правильно, но получать мало входящих данных. |
| TG JSON limit=50 как достаточный лимит. | Использовать env-настраиваемый TG_JSON_LIMIT=150. Лимит и список каналов fetcher считать важными операционными параметрами. | Плотность MAX-канала зависит от входного TG-потока. |
| Ручным publisher добивать все pending после фикса. | Не делать. Ручной publisher использовать только для проверки safe point; обычный поток должен идти через cron. | Иначе можно обойти естественный ритм публикаций и увеличить риск дублей/шума. |
| Оставлять pending без проверки дублей перед ручной публикацией. | Перед любой ручной публикацией проверять дубли внутри pending и против уже опубликованных новостей. | После расширения источников риск дублей выше. |
| Считать отдельный пустой return tariffs.xlsx источником обратной логистики Ozon. | Не считать. Обратная логистика Ozon привязана к тарифу логистики без наценки за нелокальную продажу и хранится как official rule. | Это предотвращает ложные расчёты на пустом или неправильно импортированном файле. |
| Полагаться на CATEGORY GUARD как на полноценный подбор категорий. | CATEGORY GUARD V2 — защитный отказ, а не финальный ranking. Он нужен, чтобы не считать по явно неверной категории. | Пользователь должен получить честный отказ/уточнение, если уверенности нет. |
| Сравнивать площадки на автоподборе категорий. | Оставить отключённым до качественного category matching и пользовательского уточнения. | Ложный вывод «где выгоднее» опаснее, чем честное отсутствие сравнения. |
| Рекламу и продвижение подавать как абстрактные «новости без воды». | Позиционирование смещать к практической пользе: комиссии, маржа, оферты, изменения правил, проверка товара до запуска. | Канал должен объяснять не просто новости, а последствия для денег селлера. |

### Таблица 37
| Что уже можно использовать | Пользовательская ценность | Ограничение, которое нужно честно показывать |
| --- | --- | --- |
| MAX-канал «Инсайдер Селлер» | Новости и сигналы по Ozon, WB, Яндекс Маркету, маркировке, выплатам, комиссиям, офертам и правилам работы. | Это не юридическое заключение и не официальный источник маркетплейса; важные изменения сверяются перед выводами. |
| Кнопка «Читать полностью» | Можно читать длинные материалы внутри MAX без перехода во внешние источники. | Кнопка появляется только там, где есть достаточный raw_text/full_text. |
| Вечерний монитор изменений | Отдельный контроль тарифов, оферт, логистики, выплат, возвратов и официальных обновлений. | Если обновлялся источник, это ещё не значит, что тариф уже изменён в расчёте. |
| Seller Helper Bot | Переход по CTA после новостей: можно проверить комиссию и прибыль по товару. | Сравнение площадок пока отключено до надёжного сопоставления категорий. |
| Расчёт маржи | Цена продажи, комиссия, себестоимость, налоговая база, налог, НДС и остаток после основных удержаний. | Логистика, возвраты, хранение, реклама, эквайринг и прочие удержания пока не входят в полный расчёт. |
| Налоговый нюанс | Бот показывает, что налог считается с дохода/цены продажи, а не с суммы, пришедшей после удержаний маркетплейса. | Налоговый режим и НДС пользователь должен указывать корректно; бот не заменяет бухгалтера. |
| Риск-вывод по товару | Бот показывает зелёную/красную зону и объясняет, что давит на экономику товара. | Это предварительная аналитика, а не гарантия прибыли. Перед закупкой нужно пересчитать с логистикой, возвратами и рекламой. |
| Защита от ошибочной категории | Если категория подобрана ненадёжно, бот не считает «как попало», а просит уточнить. | Защита не решает весь ranking; нужны будущие кнопки уточнения и mapping категорий. |

### Таблица 38
| Приоритет | Задача | Комментарий / Definition of Done |
| --- | --- | --- |
| P0 | Опубликовать и закрепить подготовленный onboarding-пост в MAX-канале. | Новый подписчик за 10 секунд понимает: что даёт канал, как открыть полный текст, как перейти в Seller Helper и зачем считать товар до запуска. |
| P0 | Наблюдать следующий cron после фикса TG fetcher. | Проверить, что поток новостей стал плотнее без ручного publisher: collector получает свежий tg_posts.json, pending не превращается в мусор, дубли отсекаются. |
| P0 | Сохранять простой контур NEWSBOT: GitHub JSON → loader → collector → scoring/filter → news_queue.db → publisher/digest. | Не плодить новые прослойки ради исправления плотности новостей; контролировать лимит, список каналов, свежесть JSON и дубли. |
| P0 | Начать сбор простых метрик Seller Helper. | Логировать запуски расчёта, завершения, частые товары, маркетплейсы, красную/зелёную зону, защитные отказы по категории и ошибки поиска. |
| P1 | Сделать безопасное уточнение категории. | Не агрессивный patch handle_text. Нужен отдельный UX: найдено несколько вариантов → пользователь выбирает категорию/схему → расчёт. Перед включением: backup, py_compile, локальные тесты, restart и live-log. |
| P1 | Усилить Risk Insights V1 до V2. | Добавить более понятные предложения: какую цену поднять, какая себестоимость допустима, какой запас нужен, какие расходы проверить перед закупкой. |
| P1 | Админский индикатор TG fetcher health. | В админке желательно видеть дату tg_posts.json, количество items, список каналов, TG_JSON_LIMIT, время последней загрузки и последние ошибки fetcher/loader. |
| P1 | Нормализовать Ozon logistics/returns/storage без хрупких витрин. | Начать с логистики и official rule обратной логистики. Не строить расчёт возвратов на пустом return tariffs.xlsx. |
| P1 | Дочистить Ozon freshness в админке по-русски. | Показать текущий боевой файл, valid_from, число строк, сигналы после загрузки и простые действия: проверить файл, загрузить новый, посмотреть сигналы. |
| P2 | Сравнение WB/Ozon/Яндекс. | Возвращать только после category matching и пользовательского уточнения. Это будущий ценный/платный сценарий, но он не должен врать. |
| P2 | Docobrazec / Legal RAG. | Продолжать после стабилизации расчётного ядра, метрик, privacy-by-design и безопасной схемы API-моста. |
| P2 | Продвижение и реклама. | Не масштабировать до понимания метрик: переходы в MAX, подписки, переходы в Helper, запуски и завершения расчёта. Позиционировать не как «пугающий калькулятор», а как защиту от минуса до закупки. |

### Таблица 39
| Тип запроса | Текущее поведение |
| --- | --- |
| WB ботинки | Показывает тарифы/ставки WB по найденной категории и схемам |
| Ozon чайник | Показывает стандартный тариф Ozon marketplace_service_rate по схемам FBY/FBS/EXPRESS/DBS |
| Яндекс косметика | Показывает доступную ставку Яндекс Маркета по категории |
| чайник | Не раскрывает сравнение всех площадок сразу; предлагает выбрать площадку и показывает правила бесплатного/платного слоя |
| /start | Показывает инструкцию, возможности, ограничения и налоговый нюанс |

### Таблица 40
| Бесплатный слой после запуска | Платный слой |
| --- | --- |
| Комиссия / тариф по одной выбранной площадке | 49 ₽ — полный расчёт одного товара на одной площадке |
| Схемы работы, если есть в базе | 99 ₽ — сравнение одного товара на WB / Ozon / Яндекс |
| Предупреждение, какие расходы ещё не учтены | 299 ₽ — пакет 15 расчётов для подбора товаров |
| Налоговый нюанс: налог считается с цены продажи, а не с суммы после удержаний | Расширенный отчёт: несколько сценариев цены, риски, рекомендации |

### Таблица 41
| Контур | Состояние |
| --- | --- |
| NEWSBOT v2 | Стабилизирован; publisher доверяет collector; CTA после пачки публикаций подключён |
| Seller Helper | Работает через helperbot.service; /start обновлён; запросы по площадкам работают |
| CTA | Кнопка «[кнопка] Проверить комиссию и прибыль»; URL https://max.ru/id771812324702_2_bot; тест sent=True |
| Ozon | Стандартный marketplace_service_rate загружен и используется; Select test_only исключён из основного ответа |
| WB | commission_only usable; нужно аккуратно работать со специальными схемами в “похожие варианты” и сравнении |
| Яндекс | commission_only usable; category_id не показывать пользователю; схемы/удержания нужно разложить позже |
| Монетизация | Бесплатный слой + будущие тарифы 49/99/299 ₽ зафиксированы |
| Налоговый блок | Налог считать с цены продажи / дохода от реализации, а не с суммы после удержаний маркетплейса |

### Таблица 42
| Слой | Роль | Правило данных |
| --- | --- | --- |
| Seller Helper mini app | Главный пользовательский кабинет: комиссии, маржа, сравнение, вход в юридические сценарии. | Не хранит паспортные данные и полные реквизиты; видит только минимальные статусы и сценарии. |
| Docobrazec | Юридический document engine: анкеты, реквизиты, шаблоны, условия, генерация документов. | Остаётся владельцем персональных данных, профилей, черновиков и готовых документов. |
| RAG Store «Инсайдер Селлер» | Оферты, законы, судебные кейсы, новости, сигналы, справочный контекст. | Получает только минимальный обезличенный контекст без паспорта, адреса и полных реквизитов. |
| API-мост | Защищённая связь между Seller Helper, Docobrazec и RAG. | Токены/подписи, минимизация данных, логирование без персональных данных. |

### Таблица 43
| Правило | Как реализовать |
| --- | --- |
| Персональные данные остаются в Docobrazec | ФИО, паспорт, ИНН, адреса, реквизиты, черновики и готовые документы не передавать в RAG без крайней необходимости. |
| RAG получает обезличенный контекст | Передавать сценарий, маркетплейс, тип спора, сумму/диапазон, тип субъекта; не передавать паспорт, адрес, сканы, полное ФИО. |
| Отдельные согласия | Добавить раздельные чекбоксы: обработка ПДн; сохранение профиля; передача минимального контекста между модулями; уведомления/маркетинг отдельно; пользовательское соглашение; юридический дисклеймер. |
| Кнопка «Стереть все данные» | Сохранить и усилить: удалять профиль, анкеты, черновики, документы и историю; оставлять только обезличенный технический лог deletion_request_id/date/status. |
| Логи без ПДн | Не писать в логи паспорт, ИНН, адреса, полные реквизиты, .env, токены и содержимое документов. |
| Интеграция через API | Не подключать SQLite напрямую между серверами; использовать HTTPS/API-токен/подпись запроса, а при необходимости — VPN или allowlist. |

### Таблица 44
| Этап | Что сделать | Definition of Done |
| --- | --- | --- |
| 1. Read-only legal context | На сервере «Инсайдер Селлер» поднять минимальный legal-rag-api: /health, /api/legal/search, /api/legal/context. | Docobrazec получает нормы/оферты/кейсы по обезличенному сценарию; персональные данные не передаются. |
| 2. Docobrazec session API | На стороне Docobrazec сделать API запуска документа: /api/documents/session/start, /draft, /generate, /delete-profile. | Seller Helper может открыть юридический сценарий и передать только scenario/marketplace/problem/amount. |
| 3. Единый пользовательский вход | Связать MAX user_id с внутренним user_id/hash; Seller Helper видит только has_legal_profile и тип профиля. | Пользователь ощущает единый кабинет, но персональные данные остаются в Docobrazec. |
| 4. Документы внутри mini app | Добавить раздел «Юридические документы» в Seller Helper mini app. | Пользователь проходит сценарий без ощущения ухода на сторонний ресурс; Docobrazec работает как встроенный модуль. |

### Таблица 45
| Приоритет | Задача | Что сделать | Definition of Done |
| --- | --- | --- | --- |
| P0 | Зафиксировать рабочий source of truth Seller Helper | Проверить /opt/helperbot/max_bot_polling.py и убедиться, что расчёт берёт /opt/newsbot_v2/data/unified_tariffs.db#clean_commissions. Устаревшую /opt/helperbot/data/unified_tariffs.db не использовать для боевых ответов. | Ozon использует только fee_type=marketplace_service_rate; Select не попадает в основной ответ; тестовые запросы WB/Ozon/Яндекс проходят. |
| P0 | Собрать MVP расчёта маржи | Добавить пользовательский сценарий: маркетплейс, товар/категория, цена продажи, себестоимость, налоговый режим. Ответ: цена, комиссия, сумма к выплате, налоговая база, налог, остаток. | Пользователь получает понятный расчёт по одной площадке с честным предупреждением о неучтённых расходах: логистика, хранение, возвраты, реклама, прочие удержания. |
| P0 | Стабилизировать контракт ответа Seller Helper | Описать обязательный формат: источник ставки, схема, категория, что учтено, что не учтено, налоговый нюанс, ограничения бесплатного слоя. | Ответ не вводит в заблуждение, не показывает специальные ставки как базовые и не раскрывает полное сравнение при широком бесплатном запросе. |
| P0 | Privacy-by-design до юридической интеграции | Зафиксировать минимизацию данных, раздельные согласия, запрет передачи паспорта/адресов в RAG, усиление кнопки «Стереть все данные». | Есть техническое ТЗ на данные и согласия до начала API-моста Docobrazec ↔ Seller Helper. |
| P0 | Инвентаризация Docobrazec | Проверить текущие таблицы/модели/поля/шаблоны: пользователи, анкеты, ФИО, паспорт, ФНС, ИП, реквизиты, документы, кнопка удаления. | Понятно, что уже можно использовать, какие поля добавить для селлера и где подключать API. |
| P1 | Селлерский блок Docobrazec | Добавить роли и сценарии: селлер, маркетплейс, покупатель маркетплейса; первый пакет шаблонов — претензия к маркетплейсу по удержанию/штрафу/невыплате/спорному возврату и ответ покупателю. | Docobrazec генерирует первый селлерский документ по детерминированной анкете без свободной генерации текста LLM. |
| P1 | Встроить Docobrazec в Seller Helper mini app | Добавить раздел «Юридические документы» и запуск юридической сессии через защищённый API-мост. | Пользователь из Seller Helper может начать сбор документа; персональные данные остаются в Docobrazec. |
| P1 | Ranking категорий и схем | WB: отделить базовые и специальные схемы; Яндекс: улучшить смысловой ranking; Ozon: закрепить marketplace_service_rate. | Комиссионный ответ стал надёжным основанием для расчёта маржи и будущего сравнения площадок. |
| P2 | Legal RAG: законы, оферты, судебные кейсы | После аудита источников подключить legal RAG как справочный слой: нормы, похожие кейсы, доказательственные чек-листы. | RAG помогает объяснять и подбирать доказательства, но не заменяет шаблон Docobrazec. |
| P2 | Сравнение площадок и платные сценарии | После стабильного расчёта по одной площадке сделать сравнение WB/Ozon/Яндекс и подготовить тарифы 49/99/299 ₽. | Платный сценарий не запускается, пока расчёт и источники не стабильны. |
| P3 | Offer Doctor и расширенные модули | После расчётного и юридического MVP встроить Offer Doctor как маркетинговый модуль, а дальше развивать подписку/админку/SEO-витрины. | Экосистема расширяется только после стабильного ядра, без перегруза NEWSBOT v2. |

### Таблица 46
| Компонент | Статус v6.3 | Правило дальше |
| --- | --- | --- |
| База комиссий | /opt/newsbot_v2/data/unified_tariffs.db#clean_commissions используется как source of truth. | Не использовать устаревшую /opt/helperbot/data/unified_tariffs.db для боевых ответов. |
| Ozon | В ответах должен использоваться fee_type=marketplace_service_rate. | Ozon Select остаётся test/reference и не возвращается в основной расчёт. |
| WB / Яндекс | Используется fee_type=commission_only. | Продолжить ranking схем и категорий, чтобы специальные ставки не выглядели как базовые. |
| Расчёт маржи | Работает простой расчёт: цена, себестоимость, комиссия, налог, НДС и остаток. | Называть расчёт черновым, пока не добавлены логистика, хранение, возвраты, реклама и эквайринг. |

### Таблица 47
| Сценарий | Поведение v6.3 | Статус |
| --- | --- | --- |
| Запрос по товару и площадке | Пользователь пишет, например: Ozon чайник или WB ботинки. Бот показывает комиссию/тариф и кнопку расчёта. | Работает |
| Кнопка «Рассчитать прибыль» | Запускает пошаговый сценарий расчёта маржи без команды /calc. | Работает |
| Выбор площадки | Кнопки/варианты: Ozon, Wildberries, Яндекс Маркет. | Работает |
| Цена и себестоимость | Пользователь вводит числа отдельными шагами. | Работает |
| Налог | Поддерживается УСН 6%, без налога/пока не считать, свой процент. | Работает |
| НДС | Поддерживается без НДС, 5%, 7%, 22% и свой процент. | Работает |
| Итог | Бот отдаёт черновой расчёт по схемам: комиссия, к выплате после комиссии, остаток после комиссии, себестоимости, налога и НДС. | Работает в MVP |

### Таблица 48
| Компонент | Статус | Причина / правило |
| --- | --- | --- |
| Логистика | Пока не включена | Требует отдельного слоя тарифов, схем и условий. Добавлять после подтверждения интереса к простому расчёту. |
| Габариты и вес | Отложено | Сильно утяжеляет пользовательский путь; для MVP лучше не заставлять селлера вводить сложные параметры. |
| Хранение / размещение | Пока не включено | Нужно разложить по marketplace_fee_components и датам действия. |
| Возвраты | Пока не включены | Зависят от схемы, категории и условий площадки. |
| Эквайринг / реклама / прочие удержания | Пока не включены | Показывать в предупреждении как неучтённые расходы. |
| Платное сравнение площадок | Не запущено | Сначала стабилизировать расчёт по одной площадке и проверить спрос через канал. |

### Таблица 49
| Параметр | Значение |
| --- | --- |
| Статус | Тестовая реклама запущена в VK Рекламе. |
| Что рекламируем | MAX-канал «Инсайдер Селлер», а не Seller Helper Bot напрямую. |
| Логика воронки | VK Реклама → MAX-канал «Инсайдер Селлер» → новости/аналитика/изменения правил → CTA-кнопки → Seller Helper Bot. |
| Позиционирование | Новости маркетплейсов для продавцов: комиссии, оферты, тарифы, риски и важные изменения без воды. |
| Роль Seller Helper | Дополнительный прикладной инструмент внутри экосистемы, а не главная точка входа рекламы. |
| Тестовый бюджет | Около 1600 ₽. |
| Аудитория | Россия; малый бизнес; B2B/IT для бизнеса; торговля; ИП/владельцы бизнеса; смежные характеристики. |

### Таблица 50
| Задача из roadmap | Новый статус v6.3 | Куда перенесено / что теперь делать |
| --- | --- | --- |
| Собрать MVP-калькулятор прибыли | Выполнено в простом варианте | Поддерживать как рабочий MVP; дальше улучшать объяснения и метрики. |
| Убрать вводящее “от 3%” по WB в похожих вариантах | Выполнено | Следующий этап — более аккуратный ranking базовых и специальных схем. |
| Добавить налоговый нюанс | Выполнено | Сохранять в каждом расчётном ответе: налог считается с цены продажи/дохода реализации. |
| Добавить НДС в расчётный сценарий | Выполнено | Пока НДС входит в пошаговый сценарий; дальше улучшать текстовое объяснение. |
| Сделать расчёт понятнее для пользователя | Частично выполнено | Добавлены кнопки; нужно ещё усилить приветствие, закреп и пояснения внутри бота. |
| Подключить рекламу после частичной готовности расчёта | Выполнено как тест | Реклама запущена на канал, не на бота; масштабировать только после анализа метрик. |
| Новый ежедневный монитор изменений | Выполнено ранее в v6 | Оставить наблюдение за cron и качеством вечерних отчётов. |
| Кнопка «Читать полностью» | Выполнено ранее в v5/v6.1 | Оставить мониторинг callback-worker и качества raw_text. |

### Таблица 51
| Старая формулировка / риск | Новый статус v6.3 | Почему важно | Правило дальше |
| --- | --- | --- | --- |
| Рекламировать Seller Helper Bot напрямую | Не использовать для текущего теста | Подписка на бота сама по себе не является ядром экосистемы. | Рекламировать MAX-канал, а Seller Helper показывать как инструмент внутри канала. |
| Реклама “расчитайте маржу” ведёт в новостной канал | Изменено | Пользователь может запутаться, если реклама обещает калькулятор, а открывается канал. | В рекламе обещать новости, комиссии, оферты, тарифы, риски; расчёт указывать как дополнительную функцию внутри. |
| Писать пользователю “напишите /calc” | Устарело | Обычный пользователь не будет писать команды и может не понимать слэши. | Использовать кнопку «Рассчитать прибыль» и кнопки выбора на следующих шагах. |
| Добавлять габариты и вес сразу | Отложено | Контур станет слишком тяжёлым для первого MVP. | Сначала проверить простой расчёт; логистику добавлять отдельным слоем позже. |
| Называть расчёт точным | Запрещено для текущего этапа | Не учтены логистика, хранение, возвраты, реклама и эквайринг. | Использовать формулировки “черновой расчёт”, “быстрая проверка”, “предварительная маржа”. |
| Считать рекламу масштабным запуском | Неверно | Это тест гипотезы и воронки, а не полноценный запуск продаж. | Смотреть метрики, не увеличивать бюджет без анализа. |
| Переносить персональные данные в RAG | Запрещено | Docobrazec должен оставаться владельцем ПДн. | RAG получает только обезличенный контекст. |

### Таблица 52
| Приоритет | Задача | Что сделать | Definition of Done |
| --- | --- | --- | --- |
| P0 | Проверить рекламную воронку | Смотреть показы, клики, переходы в MAX, прирост подписчиков, реакции, переходы в Helper и запуски расчёта. | Понятно, есть ли интерес к каналу и какой креатив/оффер работает. |
| P0 | Сделать закреп/онбординг в MAX-канале | Подготовить пост: кто мы, зачем подписываться, что публикуем, как перейти к Seller Helper и что считается в тестовом режиме. | Новый пользователь за 10 секунд понимает ценность канала. |
| P0 | Усилить пояснения Seller Helper | Добавить понятные блоки: что считается, что не считается, почему расчёт черновой, как нажать кнопку расчёта. | Пользователь не теряется после первого ответа и понимает, что делать дальше. |
| P0 | Метрики расчёта | Логировать запуски расчёта, завершения, частые товары, маркетплейсы, ошибки поиска и шаги отваливания. | Можно оценить не только клики, но и реальное использование Helper. |
| P1 | Ranking категорий и схем | WB: отделить специальные схемы; Яндекс: улучшить broad-запросы; Ozon: удерживать marketplace_service_rate. | Ответы не вводят селлера в заблуждение и лучше попадают в смысл товара. |
| P1 | Логистика без перегруза UX | Сначала подготовить слои тарифов; затем добавить простой вопрос по типу схемы/доставки, без сложных габаритов в первом экране. | Логистика добавлена как опциональный слой, а не ломает быстрый расчёт. |
| P1 | Админский статус источников | Показать unified_tariffs, clean_commissions, RAG Store, tariff_signals, signal_digest_runs, audio_digest, cleanup_audio. | Статусы видны без ручного просмотра консоли. |
| P2 | Docobrazec и Legal RAG | После расчётного MVP запустить селлерский юридический блок через API-мост и privacy-by-design. | Персональные данные остаются в Docobrazec; RAG получает обезличенный контекст. |

### Таблица 53
| Параметр | Решение v6.6 |
| --- | --- |
| Главная гипотеза | Сначала полезное действие: один тестовый расчёт товара. Потом — самостоятельные расчёты через Seller Helper для подписчиков канала. |
| Цель VK | Лид-форма / опрос / заполнение анкеты, а не переход по ссылке. |
| Оффер | «Сколько вы заработаете?» / проверка товара перед закупкой: комиссия, налог, НДС, остаток после основных удержаний. |
| Фильтр | Первый вопрос: «У вас есть аккаунт в МАКС?» или аналогичная мягкая формулировка. Ответ «нет» ведёт на стоп-экран. |
| Результат для лида | Заявка принята; предварительный расчёт отправим в МАКС. Для самостоятельных проверок — канал «Инсайдер Селлер» и Seller Helper. |
| Бюджет теста | Малый тест: ориентир 10 анкет и бюджет около 1000 ₽ из бонусного баланса VK. |
| Дата/период теста | Короткое окно теста до 09.05.2026, чтобы не тянуть бюджет бесконтрольно. |
| Статус | Кампания и форма настраиваются. До получения первых заявок не считать гипотезу подтверждённой. |

### Таблица 54
| Маркетплейс | Главный источник | Текущий рабочий слой | Ограничение |
| --- | --- | --- | --- |
| WB | API / экспорт / DB-справочники; Excel-загрузка как вспомогательная | commission_only, source_status=usable | Полная маржа пока не считается; специальные схемы нельзя использовать как “минимальную ставку” без пояснения |
| Яндекс Маркет | API / DB-справочник yandex_commissions.db | commission_only, source_status=usable | Схемы и дополнительные удержания пока не разложены; category_id не показывать пользователю |
| Ozon | Официальные Excel-документы, загружаемые вручную; плюс сигналы из новостей/статей | marketplace_service_rate, source_status=usable, valid_from=2026-04-01 | Ozon Select не использовать для боевого сравнения |

### Таблица 55
| Ozon слой | Статус | Использование |
| --- | --- | --- |
| marketplace-services-rates-01-04-2026.xlsx | usable / standard_marketplace_service_rate | Основной слой для расчёта Ozon по схемам FBY/FBS/EXPRESS/DBS |
| Ozon Select | test_only / commission_only | Не использовать в боевом сравнении; может оставаться как справочный/test_only слой |
| logistika-fbo-fbs | нужно разложить | Логистика FBO/FBS, будущий компонент маржи |
| return tariffs | нужно разложить | Возвраты, будущий компонент маржи |
| Сроки бесплатного размещения | нужно разложить | Хранение/размещение, будущий компонент маржи |
| koeffitsient-vozmeshcheniya | нужно разложить | Коэффициенты компенсации/возмещения |

### Таблица 56
| Зона мониторинга | Как отслеживать | Что сигнализировать |
| --- | --- | --- |
| WB | API / экспорт / обновление DB-справочников | Изменение комиссии, схемы, категории, даты действия |
| Яндекс Маркет | API / DB-справочник / обновление тарифных источников | Изменение ставки, категории, новых правил |
| Ozon | Официальные Excel-документы + новости/статьи об изменениях тарифов | Новый файл, новый слой, новая дата, изменение категорий/схем |

### Таблица 57
| Блок | Что зафиксировано | Статус / правило дальше |
| --- | --- | --- |
| Яндекс Маркет API | Проверен доступ к кабинету через API; подтверждён рабочий сценарий tariffs/calculate; импорт Яндекс Маркета в clean_commissions прошёл успешно. | Яндекс API становится рабочим источником обновления комиссий/тарифов. Старые DB-справочники считать резервом, а не главным свежим слоем. |
| Импорт Яндекс тарифов | В clean_commissions загружено 16282 строки: FBS — 8141, FBY — 8141; диапазон ставок 0.5–61; valid_from=2026-05-13; source_file=yandex_market_api_tariffs_calculate.json. | Слой использовать в Seller Helper после контроля схем и категорий. Пользователю не показывать category_id и технические детали API. |
| helperbot.service | После импорта Яндекс API helperbot.service перезапущен и активен. | Расчётный контур не трогать большими патчами без backup, py_compile, локальных тестов и проверки journalctl. |
| admin_alert.py | Удалён ежедневный шум про «официальный слой сегодня» и добавлен dedupe через admin_alert_state. | Админское предупреждение отправлять только при новой причине/новом fingerprint. Публичный канал не должен получать технические тревоги. |
| Ozon freshness | Сырые Ozon-сигналы после загрузки отфильтрованы как ложный ежедневный повод для alert; сухой прогон после фильтра показал статус «проверь свежесть Ozon-файла». | Ozon остаётся ручным контролем свежести официальных файлов. Alert не должен повторяться каждый день без нового события. |
| Текстовые дайджесты | Добавлены более предметные строки «Что проверить», усилена классификация условий/тарифов/операционных сигналов, уменьшена доля универсальных фраз. | Дайджест должен быть полезным для селлера: не просто ссылка, а конкретная проверка по цене, марже, возвратам, ПВЗ, отзывам или риску. |
| Аудиодайджест | Cron временно ставился на паузу, затем audio_digest_story_builder.py и audio_digest_text_cleaner.py доработаны и cron включён обратно на 22:45. | В аудио не должно быть обрезков «приобретаемые ч.», «самое вр.», «регистраци.» и повторов «Главный вопрос для селлера». Дубликаты одной темы не озвучивать. |
| publisher_v2.py | Добавлена семантическая защита от повторной публикации одинаковых тем; например WB return tariff/logistics объединяется в один topic key. | Дубликат новой публикации по уже раскрытой теме переводить в digest, а не публиковать заново. |
| formatters.py | Улучшен fallback format_news: убраны пересекающиеся обрывки summary, добавлены редакционные заголовки и более точный блок «что это значит». | Fallback должен быть пригоден, если LLM недоступен. LLM остаётся основным улучшателем поста, но не единственной точкой качества. |
| llm.py | После неудачной правки промпта файл был восстановлен из backup и снова компилируется. | Промпты менять только через безопасную замену цельного блока. Не вставлять многострочные строки фрагментами без проверки синтаксиса. |
| RAG и будущие модули | Зафиксировано: RAG должен копить не только тарифы/оферты, но и юридику, дизайн карточек, инфографику, тренды, AI-взаимодействие с маркетплейсами и выводы по продажам. | RAG становится общей памятью экосистемы для Seller Helper, Legal, Docobrazec и OfferDoctor. Персональные данные туда не передавать. |
| Рост канала | Канал застрял около 40 подписчиков; проблема не в упаковке продукта, а в слабой находимости MAX и отсутствии внешнего инфополя. | Ближайший план: аудит поиска MAX без id, заполнение инфополя ключами/тегами, закреп, кросспостинг и внешние точки входа. Накрутку ботами не использовать. |

### Таблица 58
| Параметр | Значение v6.7 |
| --- | --- |
| Источник | Яндекс Маркет API tariffs/calculate |
| Рабочие схемы | FBS и FBY |
| Всего строк | 16282 |
| Строк FBS | 8141 |
| Строк FBY | 8141 |
| Диапазон ставок | 0.5–61 |
| valid_from | 2026-05-13 |
| source_file | yandex_market_api_tariffs_calculate.json |
| Правило для Seller Helper | Брать из clean_commissions; не показывать пользователю технические category_id и API-варианты запроса. |

### Таблица 59
| Сущность | Роль | Правило безопасности |
| --- | --- | --- |
| user_id | Главный идентификатор пользователя/подписчика. | Все проверки подписки, allowlist, revoke и live_subscription_check привязывать к user_id. |
| chat_id | Адрес диалога, куда бот отправляет сообщение. | Не считать chat_id доказательством подписки. Он нужен для отправки ответа, но не для права доступа. |
| helper_chat_access | Будущая безопасная привязка chat_id → active user_id. | Создавать только после успешного gate по user_id. Использовать для callback fallback только если chat_id уже привязан к активному user_id. |
| chat_bound_allow | Допустимый fallback для callback-сценариев. | Разрешать только при ранее подтверждённой связке chat_id → active user_id из allowlist/live_subscription. Никогда не открывать доступ по одному chat_id. |

### Таблица 60
| Компонент | Новое правило v6.7 |
| --- | --- |
| admin_alert_state | Хранит alert_key, fingerprint, first_seen_at, last_seen_at, last_sent_at, sent_count. |
| official_rows_today | Не является самостоятельной причиной ежедневного алерта. Обновление официального слоя должно попадать в монитор/админку, а не спамить в личку. |
| Ozon-сигналы после загрузки | Считать поводом только после фильтра по реальным новым сигналам, а не по старым строкам/ложным повторам. |
| Публичный канал | Пишет редакционный монитор: что проверено, что подтверждено, что взято в наблюдение. |
| Личный MAX-чат админа | Получает только административные действия: проверить свежесть файла, новый fingerprint, ошибка источника, сбой импорта. |

### Таблица 61
| Тип новости / сигнала | Как должен звучать вывод |
| --- | --- |
| Изменение тарифа, возврата, комиссии | Проверить маржу, остатки, сроки вывоза, категории с низкой прибылью, влияние на расчёт Seller Helper. |
| Отзывы, карточка, склейка, рейтинг | Проверить слабые варианты товара внутри карточки, отзывы по цветам/размерам/SKU, влияние на конверсию. |
| ПВЗ, спорные выдачи, утилизация, возвраты | Проверить операции через ПВЗ, возвраты, спорные выдачи, документы и ответственность за товар. |
| Регуляторика, ФАС, скидки, НДС | Проверить влияние на цену, акции, маржу, документы и будущие условия площадок. |
| История ухода селлера в другой канал | Считать не мусором, а трендом по экономике продаж: давление комиссий, рекламы и логистики на малый бизнес. |
| Операционное улучшение без комиссии | Не писать, что меняются расчёты. Формулировать: это операционный сигнал, в марже ничего не менять без официального тарифного подтверждения. |

### Таблица 62
| Проблема | Решение v6.7 |
| --- | --- |
| Обрезанные хвосты: «приобретаемые ч.», «самое вр.», «регистраци.» | Усилена очистка текста и отбраковка плохих предложений. |
| Повтор «Главный вопрос для селлера» | Фраза не должна повторяться в каждом пункте; использовать только fallback и не более одного раза. |
| Одна тема как новость и как сигнал | audio_digest_story_builder должен исключать signal_items по event_key уже выбранных news_items. |
| Склейка заголовка и текста | Добавлять точку/границу между заголовком и началом описания; cleaner исправляет частые шаблоны. |
| Слишком длинный аудиотекст | Держать выпуск коротким: 2–3 главные новости + 0–2 сигнала, только если они не дублируют новости. |
| ffmpeg warning по WAV | Предупреждение packet corrupt сейчас не блокирует итоговый MP3, но его оставить в наблюдении; если появится обрезанное аудио, чинить Salute WAV/конвертацию. |

### Таблица 63
| RAG-слой | Что копить | Для какого модуля нужно |
| --- | --- | --- |
| official_tariffs | Официальные тарифные файлы, API-снимки, source_file, valid_from, схемы, min/max fee, статус импорта. | Seller Helper, вечерний монитор, админка. |
| official_legal | Оферты, правила, документы маркетплейсов, изменения условий, юридические фрагменты с датами. | Legal RAG, Docobrazec, монитор условий. |
| news_signal | Новости, TG-посты, официальные каналы, сигналы изменений, но с пониженным приоритетом относительно official/high. | NEWSBOT v2, дайджесты, монитор. |
| seller_decision | Фактический вывод редакции: publish/digest/drop, seller_relevance_score, actionability_score, «что проверить». | Обучение редакторского качества, будущий AI-редактор канала. |
| unit_economics | Кейсы по марже, комиссиям, возвратам, рекламе, цене, себестоимости, уходу товара в минус. | Seller Helper, OfferDoctor, платные отчёты. |
| card_design | Наблюдения по карточкам, отзывам, склейкам, инфографике, визуальным блокам, UX, влиянию на конверсию. | OfferDoctor и модуль анализа карточек. |
| ai_marketplace | AI-трафик, AI-ассистенты маркетплейсов, взаимодействие ИИ с карточками, поиском, рекомендациями и аналитикой. | OfferDoctor, трендовый блок, будущий МАРК-разведчик. |
| legal_cases | Судебные кейсы, претензии, доказательственные чек-листы, типовые ситуации селлер → маркетплейс. | Legal RAG, Docobrazec. |
| growth_marketing | Креативы, закрепы, кросспостинг, лидформы, конверсия подписки, поисковые теги MAX. | Рост канала, AI-редактор, продвижение. |

### Таблица 64
| Контур / программа | Роль в экосистеме | Статус / правило |
| --- | --- | --- |
| NEWSBOT v2 | Главный сборщик новостей, TG/RSS, сигналов, дайджестов, publisher и базы news_queue.db. | Рабочий core. Не плодить дублей рядом. |
| Seller Helper | Расчёты комиссий, налогов, НДС, риска, будущая история проверок товара. | Передавать в RAG только обезличенную аналитику и итоговые паттерны, не личные данные. |
| Yandex Market API | Актуальный источник тарифов/комиссий Яндекса. | Подключён как рабочий импорт v6.7; нужен регулярный контроль. |
| WB API / официальные источники | Комиссии, категории, логистика, возвраты и официальные сигналы WB. | Следующий слой после стабилизации Яндекса; не смешивать API-числа и TG-сигналы. |
| Ozon official files | Excel/PDF с комиссиями, логистикой, возвратами, storage и правилами. | Ручной/полуавтоматический контур; Select не боевой источник. |
| RAG Store SQLite/FTS | Базовый текстовый поиск и накопление документов. | Уже есть. Расширить теги и слои. |
| Vector DB: Qdrant/Chroma или аналог | Кандидат для смыслового поиска по длинным документам, кейсам, карточкам и дизайн-наблюдениям. | Не подключать вслепую. Сначала описать схему данных и критерии качества. |
| DeepSeek / GitHub Models / LLM-контур | Классификация, редактура, «что проверить», RAG-ответы, будущий AI-редактор канала. | LLM не является source of truth. Числа и правовые факты брать из базы/официальных документов. |
| SaluteSpeech | Озвучка аудиодайджеста. | Рабочий контур; следить за качеством WAV/MP3. |
| Playwright / screenshot pipeline | Скриншоты карточек, витрин, интерфейсов маркетплейсов для анализа OfferDoctor. | Будущий контур. Нужен для карточек и инфографики, не для расчётных тарифов. |
| Vision/CV-анализ карточек | Оценка читаемости инфографики, структуры визуалов, доверия, УТП, товарных фото. | Кандидат для OfferDoctor. Перед подключением — тест на 20–30 карточках. |
| GitHub scouting design analytics | Поиск open-source решений для визуальной аналитики, UI critique, visual regression, image similarity, dataset review. | Задача P0/P1: провести отдельную проверку GitHub, лицензий и пригодности. Пока не считать выбранным инструментом. |
| Docobrazec API bridge | Юридические документы и анкеты внутри Seller Helper. | Только через privacy-by-design; персональные данные остаются в Docobrazec. |
| OfferDoctor | Маркетинговый модуль: оффер, карточка, УТП, инфографика, конверсия. | Должен использовать накопленные RAG-инсайты о карточках, трендах, AI-трафике и продажах. |

### Таблица 65
| Зона | Что сделать |
| --- | --- |
| Название и варианты написания | Проверить «Инсайдер Селлер», «Insider Seller», «Инсайдер Селер», «Seller Helper», «Селлер Хелпер» без прямого id канала. |
| Описание канала | Добавить ясное SEO/поисковое описание: новости и расчёты для продавцов Ozon, Wildberries, Яндекс Маркета; комиссии, тарифы, оферты, возвраты, маржа, налоги, НДС. |
| Ключевые слова / теги | селлер, маркетплейсы, Ozon, Wildberries, WB, Яндекс Маркет, комиссии, тарифы, оферты, возвраты, ПВЗ, маржа, НДС, налог, расчёт прибыли, Seller Helper, товары, карточки. |
| Закреп | Опубликовать и закрепить пост «Патч от 13.05.2026» с объяснением, что сделано и зачем подписка. |
| Внешний слой | Кросспостинг в VK/TG/личные соцсети/партнёрские каналы; короткие посты с практическими проверками товара. |
| Покупка подписчиков | Не покупать ботов и fake-аудиторию. Если тестировать социальное доказательство, то только живых релевантных людей и как ограниченный эксперимент с риском испортить качество канала. |
| Метрики | Смотреть не только подписчиков, но и переходы в Helper, запуски расчёта, повторные обращения, реакции на дайджесты и сохранения постов. |

### Таблица 66
| Что устарело / опасно | Новое правило v6.7 |
| --- | --- |
| Ежедневно слать админу одинаковый alert по официальному слою. | Использовать fingerprint/dedupe. Повторный dry-run по той же причине должен давать no attention required. |
| Считать новость или TG-сигнал автоматическим изменением тарифа. | Новость создаёт сигнал/задачу проверки. Расчёт меняется только после официального источника/API/файла. |
| Озвучивать в аудио обрезанные фрагменты из raw_text. | Плохие хвосты и короткие мусорные предложения отбрасывать до TTS. |
| Повторять один и тот же вывод «Главный вопрос для селлера» в каждом пункте. | Для каждой темы давать конкретный вывод: цена, маржа, возврат, карточка, рейтинг, ПВЗ, налог, реклама. |
| Публиковать повтор WB-тарифа как новую новость, если тема уже раскрыта. | Использовать topic_key и переводить повтор в digest. |
| Патчить llm.py большими небезопасными вставками. | Менять цельные блоки, делать backup и py_compile до рестарта контуров. |
| Давать доступ к Seller Helper по chat_id. | Только user_id; chat_id можно использовать как адрес ответа и безопасный callback fallback после подтверждённой привязки. |
| Копить в RAG личные данные пользователей или заявки VK. | В RAG идут только обезличенные сценарии, выводы, темы и агрегированные паттерны. |
| Покупать ботов ради индексации. | Не использовать fake-аудиторию. Для роста сначала заполнить инфополе, проверить поиск MAX и усилить внешние живые каналы. |

### Таблица 67
| Приоритет | Задача | Definition of Done |
| --- | --- | --- |
| P0 | Проверить штатный cron после правок 13.05. | signal_digest, audio_digest и admin_alert проходят без дублей, без ежедневного админ-спама и без плохих аудиообрезков. |
| P0 | Опубликовать и закрепить пост «Патч от 13.05.2026». | Новый подписчик понимает, что канал даёт новости, мониторинг, расчёты и закрытый доступ к Seller Helper. |
| P0 | Проверить поиск MAX без прямого id. | Зафиксированы результаты по запросам «Инсайдер Селлер», «Seller Helper», «селлер», «маркетплейсы», «Ozon WB Яндекс комиссии». Понятно, где канал виден/не виден. |
| P0 | Заполнить инфополе канала и ключевые теги. | Описание канала содержит маркетплейсы, комиссии, тарифы, маржу, НДС, оферты, возвраты, Seller Helper и практическую пользу. |
| P0 | Закрепить схему регулярного Яндекс API-импорта. | Есть команда/скрипт/админ-действие, backup, отчёт по rows/schemes/fee range/source_file и безопасный restart только если нужен. |
| P0 | Сформировать RAG tagging schema v1. | Каждый документ/сигнал получает marketplace, source_type, trust_level, module, topic, valid_from, source_file/source_url и usable/test/archive статус. |
| P1 | GitHub scouting для design/card analytics. | Собран список open-source кандидатов, проверены лицензии, активность, зависимости и применимость к карточкам товаров/инфографике. Ничего не подключается без аудита. |
| P1 | OfferDoctor RAG-модуль по карточкам. | RAG хранит кейсы карточек, отзывы, инфографику, AI-трафик, склейки, рейтинги и связи с конверсией/маржой. |
| P1 | Legal RAG и Docobrazec. | Добавлены official/legal документы и кейсы без персональных данных. Docobrazec остаётся владельцем ПДн. |
| P1 | AI-редактор канала и кросспостинг. | Модуль готовит посты/дайджесты/перепаковку в VK/MAX/TG, но не меняет расчёты и не публикует без правил качества. |
| P2 | Полноценный category matching и сравнение площадок. | Сравнение WB/Ozon/Яндекс возвращается только после пользовательского уточнения категории и защиты от ложного «где выгоднее». |
| P2 | Платные сценарии и подписка. | Возвращать 49/99/299 ₽ или подписку только после подтверждения спроса, качества расчёта, метрик использования и стабильной воронки. |

### Таблица 68
| Наблюдение по MPSTATS | Решение для нашей экосистемы |
| --- | --- |
| Аналитика сильная, но перегруженная для начинающего селлера | Не копировать тяжёлый интерфейс; делать простые ответы на сложные вопросы |
| Многое завязано на личное API селлера / расширенные данные | Не требовать личный API от микробизнеса на первом этапе |
| Пользователю нужна прикладная экономика товара | Главный ответ: “сколько я получу при продаже товара по такой цене” |
| Полезны карточки и блоки с понятными метриками | Использовать как вдохновение для будущих простых аналитических карточек |
| Порог цены важен психологически | Ставить низкий вход: 49 ₽ / 99 ₽ / пакет 299 ₽; тестовый режим — бесплатно |

### Таблица 69
| Уровень | Содержание | Комментарий |
| --- | --- | --- |
| Бесплатный слой | Проверка комиссии/тарифа одной выбранной площадки, схемы, предупреждение о неучтённых расходах, налоговый нюанс | Нужен для доверия и входа из новостного канала |
| 49 ₽ | Полный расчёт одного товара на одной площадке | Цена низкого психологического входа |
| 99 ₽ | Сравнение одного товара на WB / Ozon / Яндекс | Главный платный сценарий “где выгоднее” |
| 299 ₽ | Пакет 15 расчётов для подбора товаров | Для микробизнеса и начинающих селлеров |
| Подписка | Мониторинг изменений, регулярные расчёты, история, юридические уведомления | Следующий этап после MVP |
| Консультации/лиды | Передача сложных кейсов специалисту | Юридические и финансовые кейсы |

### Таблица 70
| Компонент | Что сделано 17.05.2026 | Вывод/правило дальше |
| --- | --- | --- |
| run_regular_v2.sh | Удалён временный promote_publish_candidates.py из штатного wrapper. | Emergency bridge не должен оставаться в production. |
| db.py | Добавлен live-wrapper add_to_queue_batch: seller_filter пишет решения в БД и обновляет свежие дубли в пределах lookback. | Production-решение фильтра должно быть persisted, а не только logged. |
| .env / db.py | SELLER_FILTER_LIVE_LOOKBACK_HOURS=8; default в db.py также 8. | Старые новости не должны оживать как publish. |
| seller_filter.py | Добавлен hard-ignore рекламного/партнёрского мусора. | Реклама не должна проходить в publish из-за ключевых слов про НДС/тарифы. |
| publisher_v2.py | Добавлен stale publish guard перед get_pending_news. | Даже если stale publish вернётся, publisher сам припаркует его в digest. |
| audio_digest_story_builder.py / cleaner | Удалены навязчивые seller-check фразы, добавлены вариативные концовки и финальная очистка. | Аудио должно быть коротким, живым и без одинаковых канцелярских вставок. |

### Таблица 71
| Проверка | Норма v7.1 |
| --- | --- |
| grep live-кода | В боевой цепочке не должно быть seller_filter_dryrun и promote_publish_candidates.py. |
| collector через wrapper | Запускать ./run_collector_v2.sh, а не прямой collector без .env; иначе TG JSON может быть 0. |
| DB-check | После collector проверять seller_decision=publish/digest/ignore и свежесть created_at. |
| publisher-check | publisher_v2.py должен писать Stale publish guard applied и затем pending loaded=N. |
| log-check | Исторический collector.log может содержать старые строки dry-run; смотреть время строк и проверять живой код. |

### Таблица 72
| Сценарий | Правильное поведение |
| --- | --- |
| Есть свежие publish | Публиковать по обычной логике publisher_v2.py. |
| Publish нет, квота не выполнена | Брать strong digest/evergreen/backlog с защитой от мусора и дублей. |
| Сырьё есть, публикаций нет 2-3 часа | Watchdog отправляет админский alert с причиной и последними метриками. |
| Сырья нет | Алерт по source health: tg_posts.json, RSS, GitHub fetcher, TG_JSON_LIMIT, ошибки fetch. |
| Ночная/старая очередь | Stale guard паркует старые publish в digest, чтобы не выпустить вчерашнее без проверки. |
