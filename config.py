import os

MAX_API_URL = "https://platform-api.max.ru"
RSS_FEEDS = [
    {"name": "Retail.ru - Новости", "url": "https://www.retail.ru/rss/news/", "category": "marketplace"},
    {"name": "Оборот.ру", "url": "https://oborot.ru/rss/", "category": "seller"},
    {"name": "Клерк.ру", "url": "https://www.klerk.ru/blogs/rss/", "category": "seller"},
    {"name": "MySeldon", "url": "https://myseldon.com/ru/news/rss", "category": "news"},
]

PARSER_URLS = [
    {"name": "Инсалес Журнал", "url": "https://journal.insales.ru/blogs/opinion/", "category": "seller_story"},
    {"name": "Сетка", "url": "https://setka.ru/posts", "category": "seller_story"},
    {"name": "Делo Модульбанк", "url": "https://delo.modulbank.ru/marketplaces/", "category": "marketplace"},
    {"name": "Мосгорсуд", "url": "https://mos-gorsud.ru/rs/", "category": "court"},
    {"name": "Арбитражный суд Москвы", "url": "https://msk.arbitr.ru/", "category": "court"},
]

IMPORTANT_KEYWORDS = [
    "комиссия", "тариф", "логистика", "штраф", "изменение правил",
    "убытки", "взыскание", "защита прав", "суд", "судебн",
    "кейс", "опыт", "история", "масштабирование", "оборот", "миллион",
    "289-ФЗ", "закон о маркетплейсах", "рекламн", "формат",
    "закрыт", "открыт инструмент", "нововведение", "правило",
    "аккаунт", "блокировка", "бан", "площадка"
]

IGNORE_KEYWORDS = [
    "открытие склада", "новый склад", "назначение директора",
    "иммерсивность", "зелёный свет", "благотворительн",
    "спортивн", "культурн", "выставка", "конференция",
    "недвижимость", "hr", "карьера", "приём на работу"
]

POSTED_LINKS_FILE = "posted_links.txt"

DEFAULT_IMAGE_URL = "https://example.com/default_news.jpg"

def get_token():
    return os.environ.get("MAX_BOT_TOKEN", DEFAULT_TOKEN)

def get_channel_id():
    return os.environ.get("MAX_CHANNEL_ID", DEFAULT_CHANNEL_ID)

def get_sent_links():
    try:
        with open(POSTED_LINKS_FILE, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()

def save_link(link):
    with open(POSTED_LINKS_FILE, "a", encoding="utf-8") as f:
        f.write(link + "\n")


ENABLE_EXA = os.getenv("ENABLE_EXA", "false").lower() == "true"
EXA_MODE = os.getenv("EXA_MODE", "shadow")
EXA_API_KEY = os.getenv("EXA_API_KEY") or os.getenv("EXA_API_TOKEN")
ENABLE_EXA_IN_DIGEST = os.getenv("ENABLE_EXA_IN_DIGEST", "false").lower() == "true"
EXA_MAX_ITEMS_PER_QUERY = int(os.getenv("EXA_MAX_ITEMS_PER_QUERY", "5"))
EXA_MAX_TOTAL_ITEMS = int(os.getenv("EXA_MAX_TOTAL_ITEMS", "30"))
EXA_MAX_ITEMS_FOR_DIGEST = int(os.getenv("EXA_MAX_ITEMS_FOR_DIGEST", "2"))
