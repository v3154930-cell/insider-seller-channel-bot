#!/usr/bin/env python3
"""
Preview: URL Fix for Regular Post
Shows before/after for 4 cases:
- 2 posts without links (LLM path)
- 2 posts with Oborot main page link
"""

# Simulate 4 real cases as described in the bug report

test_cases = [
    {
        "case": "1. Post without link (LLM generated)",
        "title": "Ozon снизил комиссию для новых продавцов",
        "link": "https://retail.ru/news/ozon-commission",
        "url": "",
        "llm_enhanced": """📦 Ozon

🔹 Комиссия для новых селлеров — 5% вместо 12%

Ozon объявил о снижении комиссии для новых продавцов. Изменение действует с 1 мая.

🎯 Выгода: регистрируйтесь как новый продавец и экономьте 7% с каждой продажи""",
    },
    {
        "case": "2. Post without link (LLM generated)",
        "title": "Wildberries изменил правила возвратов",
        "link": "https://vc.ru/new/wb-returns",
        "url": "",
        "llm_enhanced": """📦 Wildberries

🔹 Новые правила возвратов — срок сокращен до 7 дней

WB обновил политику возвратов. Теперь покупатель может вернуть товар за 7 дней вместо 14.

🎯 Риск: готовьтесь к увеличению отказов в первую неделю""",
    },
    {
        "case": "3. Oborot main page link",
        "title": "Oborot news about Ozon",
        "link": "https://oborot.ru/",  # RSS returned main page, not article
        "url": "",
        "llm_enhanced": """📦 Оборот.ру

🔹 Ozon анонсировал новую программу логистики

Озон представил обновленную систему доставки для селлеров.

🎯 Возможность: подключайте FBO и получайте приоритетную обработку""",
    },
    {
        "case": "4. Oborot main page link",
        "title": "Oborot news about WB tariffs",
        "link": "https://oborot.ru/feed/",  # RSS feed link
        "url": "",
        "llm_enhanced": """📦 Оборот.ру

🔹 Wildberries повышает комиссию на 3%

С 1 июня WB увеличивает тарифы для части категорий.

🎯 Рост затрат: пересчитайте маржинальность в затронутых категориях""",
    }
]


def get_item_url(item):
    """Current helper - get URL with fallback"""
    return item.get('url') or item.get('link', '')


def append_source_line(message: str, link: str) -> str:
    """
    Append plain source URL to message.
    Always adds "Источник:" line at the end, with the actual URL.
    """
    if not link:
        # No link available - add note but don't fail
        return message.rstrip() + "\n\n⚠️ Источник: ссылка недоступна"
    
    return message.rstrip() + f"\n\nИсточник:\n{link}"


print("=" * 80)
print("URL FIX PREVIEW - Append Source Line")
print("=" * 80)
print()

for tc in test_cases:
    chosen_url = get_item_url(tc)
    
    # Current: LLM output (may or may not have link)
    current = tc["llm_enhanced"]
    
    # After fix: append source line
    after_fix = append_source_line(current, chosen_url)
    
    print("=" * 60)
    print(tc["case"])
    print("=" * 60)
    print()
    print(f"Title: {tc['title']}")
    print(f"Link from DB: {tc['link']}")
    print(f"Chosen URL: {chosen_url}")
    print()
    print("--- CURRENT (before fix) ---")
    print(current)
    print()
    print("--- AFTER FIX ---")
    print(after_fix)
    print()
    print("-" * 40)
    print(f"Has source line: {'YES' if 'Источник:' in after_fix else 'NO'}")
    print("-" * 40)
    print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print()
print("Changes:")
print("1. All posts now have 'Источник:' line at the bottom")
print("2. Plain URL (not HTML anchor) - more reliable for MAX")
print("3. Works for both LLM and fallback paths")
print("4. If no link available - shows 'ссылка недоступна'")
print()
print("Files to change:")
print("- publisher.py: add append_source_line() call after formatting")
print("- formatters.py: optional - can also add there for consistency")
print()
print("Safety: Minimal change, only adds text at the end, no HTML/DB changes")
print("=" * 80)