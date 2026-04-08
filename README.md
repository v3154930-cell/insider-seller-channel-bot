# Insider Seller Bot

Бот для автоматического сбора и публикации новостей для селлеров в канале MAX мессенджера.

## Возможности

- Сбор новостей из RSS-лент (Retail.ru, Оборот.ру, Клерк.ру, MySeldon)
- Парсинг HTML-страниц (Инсалес Журнал, Сетка, Дelo Модульбанк)
- Фильтрация важных новостей по ключевым словам
- Игнорирование нерелевантных новостей
- Форматирование постов для канала
- Работа через GitHub Actions (каждые 2 часа)

## Структура проекта

```
insider-seller-bot/
├── .github/workflows/post.yml  # GitHub Actions workflow
├── channel_bot.py              # Основной скрипт
├── config.py                   # Конфигурация
├── filters.py                  # Фильтрация новостей
├── parsers.py                  # Парсеры RSS и HTML
├── formatters.py               # Форматирование постов
├── requirements.txt            # Зависимости
└── README.md                   # Документация
```

## Установка локально

```bash
pip install -r requirements.txt
```

## Настройка

### Переменные окружения

- `MAX_BOT_TOKEN` — токен бота из MAX Business
- `MAX_CHANNEL_ID` — ID канала для постов

### Пример запуска локально

```bash
export MAX_BOT_TOKEN="your_token_here"
export MAX_CHANNEL_ID="your_channel_id"
python channel_bot.py
```

## Деплой на GitHub

### 1. Создайте репозиторий на GitHub

### 2. Добавьте секреты в репозиторий

Перейдите в `Settings` → `Secrets and variables` → `Actions` и добавьте:

- `MAX_BOT_TOKEN` — токен вашего бота из MAX Business
- `MAX_CHANNEL_ID` — ID канала (получить можно через @getidsbot или из URL канала)

### 3. Запустите бота

- Бот автоматически запускается каждые 2 часа по расписанию
- Можно запустить вручную: `Actions` → `Post News to MAX Channel` → `Run workflow`

## Получение ID канала

1. Добавьте бота в канал как администратора
2. Откройте канал в веб-версии MAX
3. Скопируйте ID из URL (например, `chat/771812324702_biz`)
4. Или используйте @getidsbot в MAX

## Примеры постов

### Новость маркетплейса
```
📦 Ozon

**Заголовок новости**

Краткое описание...

[Читать полностью](ссылка)
```

### Судебный кейс
```
⚖️ СУДЕБНЫЙ КЕЙС | Название суда

**Суть дела:** ...

📊 Результат: Взыскано ...

📌 Вывод: ...

🔗 Источник
```

### История селлера
```
💡 ИСТОРИЯ УСПЕХА

**Заголовок**

Ключевая выжимка...

📊 Результат: ...

🎯 Урок: ...

🔗 Подробнее
```

## Требования

- Python 3.12
- feedparser, requests, beautifulsoup4, lxml

## Техническая документация

### Current Status: Production-Ready Fallback MVP

Бот работает в production. Текущая версия - стабильный fallback-MVP.

### Что работает

- ✅ LLM (GitHub Models gpt-4o)
- ✅ SQLite очередь с антидублями
- ✅ Лимит 1 пост за запуск
- ✅ Scheduler (morning/evening digest)
- ✅ General RSS pipeline (Retail.ru, Oborot.ru, vc.ru, CNews, RBC)
- ✅ Sales fallback classification из общего RSS
- ✅ Legal fallback classification из общего RSS
- ✅ GitHub Actions workflow

### Primary Sources (Broken)

Следующие RSS-источники **нестабильны** и не дают данных:
- Retail.ru Акции (пустой/ошибки)
- E-Pepper (пустой/ошибки)
- МосГорСуд RSS (пустой/ошибки)
- МособлСуд RSS (пустой/ошибки)
- Право.ru (пустой/ошибки)

### Fallback Sources (Active)

Вместо сломанных RSS используется классификация из общего потока:

**Sales classification keywords:**
```
акция, распродажа, скидк, бонус, cashback, промокод, купон, спецпредложение
```

**Legal classification keywords:**
```
суд, арбитраж, иск, взыскание, убытки, компенсация, штраф, решение суда
```

### Pipeline Flow

```
1. Parse RSS (5 sources)
2. Classify Sales from RSS (keyword matching)
3. Classify Legal from RSS (keyword matching)
4. Save to SQLite with deduplication
5. Send 1 pending post per run
6. LLM enhancement (if USE_LLM=true)
```

### GitHub Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| MAX_BOT_TOKEN | ✅ | Bot token for MAX |
| CHANNEL_ID | ✅ | Channel ID |
| USE_LLM | ❌ | Set to "true" for LLM |
| GITHUB_TOKEN | ❌ | For GitHub Models |

### Technical Debt

1. **Court parser** - требует HTML/API парсинг, RSS сломан
2. **Dedicated sales feeds** - требуют замены на рабочие RSS
3. **Quality layer** - scoring/prioritization, better classification

### Logs Expected

```
RSS total: N items
Sales dedicated feeds: N
Sales from RSS: N
Sales total: N
Legal fallback feeds: N  
Court feeds: N
Legal/Court total: N
Queue: N pending
Sending N posts this run
LLM enabled: true/false
LLM SUCCESS / fallback used
```