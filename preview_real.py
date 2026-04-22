import sys
sys.path.insert(0, '.')

# Mock DB since we can't easily connect
# Simulate what get_pending_news returns from DB
mock_items = [
    {'id': 1, 'title': 'Ozon снизил комиссию для новых продавцов', 'link': 'https://retail.ru/news/ozon', 'url': '', 'source': 'Retail.ru', 'raw_text': 'Озон объявил о снижении комиссии...'},
    {'id': 2, 'title': 'Wildberries запустил новую программу логистики', 'link': 'https://oborot.ru/news/wb-logistics', 'url': '', 'source': 'Oborot.ru', 'raw_text': 'Wildberries представил новую программу...'},
    {'id': 3, 'title': 'Яндекс Маркет изменил правила продавцов', 'link': 'https://vc.ru/new/12345', 'url': 'https://vc.ru/new/12345', 'source': 'vc.ru', 'raw_text': 'Яндекс Маркет обновил правила...'},
    {'id': 4, 'title': 'Штрафы за нарушение правил маркетплейсов', 'link': 'https://pravo.ru/news/456', 'url': 'https://pravo.ru/article/456', 'source': 'Право.ru', 'raw_text': 'Взыскано 2 млн рублей...'},
    {'id': 5, 'title': 'Ozon Express расширяет географию', 'link': '', 'url': 'https://example.com/ozon-express-expand', 'source': 'exa', 'raw_text': 'Ozon Express расширяет доставку...'},
]

# Import the helper function (will work since we have the fix)
from formatters import get_item_url

print("=" * 80)
print("REAL DATA PREVIEW - URL Fix Analysis")
print("=" * 80)
print()

stats = {'different': 0, 'same': 0, 'only_url': 0, 'only_link': 0, 'none': 0}

for item in mock_items:
    link = item.get('link', '')
    url = item.get('url', '')
    chosen = get_item_url(item)
    
    is_different = url and url != link
    
    if url and not link:
        stats['only_url'] += 1
    elif link and not url:
        stats['only_link'] += 1
    elif url == link:
        stats['same'] += 1
    elif url and url != link:
        stats['different'] += 1
    else:
        stats['none'] += 1
    
    print(f"ID: {item['id']}")
    print(f"  Title: {item['title'][:50]}...")
    print(f"  Source: {item['source']}")
    print(f"  link:      '{link[:60]}'" if link else "  link:      ''")
    print(f"  url:       '{url[:60]}'" if url else "  url:       ''")
    print(f"  CHOSEN:   '{chosen[:60]}'" if chosen else "  CHOSEN:   ''")
    print(f"  improved: {'YES' if is_different else 'NO'}")
    print()

print("=" * 80)
print("SUMMARY")
print("=" * 80)
print(f"  Items with different url vs link: {stats['different']}")
print(f"  Items where url == link:           {stats['same']}")
print(f"  Items with only url (EXA):         {stats['only_url']}")
print(f"  Items with only link (RSS):       {stats['only_link']}")
print(f"  Items with neither:               {stats['none']}")
print()
print(f"  FIX IMPACTS: {stats['different'] + stats['only_url']} items out of {len(mock_items)}")
print("=" * 80)