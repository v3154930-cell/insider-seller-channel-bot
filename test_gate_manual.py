import sys
sys.path.insert(0, '.')
from staging.preview_staging import evaluate_item_relevance

test_cases = []

# Test 1: No URL
item1 = {'title': 'Test', 'description': 'Desc', 'raw_text': 'Text', 'url': ''}
r1 = evaluate_item_relevance(item1)
test_cases.append(('No URL', r1['passed'] == False, f"passed={r1['passed']}"))

# Test 2: Short text
item2 = {'title': 'A', 'description': 'B', 'raw_text': 'C', 'url': 'https://a.com'}
r2 = evaluate_item_relevance(item2)
test_cases.append(('Short text', r2['passed'] == False, f"passed={r2['passed']}"))

# Test 3: Strong relevance
item3 = {'title': 'Ozon повысил комиссию на 5%',
         'description': 'Комиссия повышена',
         'raw_text': 'Ozon объявил о повышении комиссии с 15% до 20%. Это важное изменение для всех селлеров. Новые тарифы действуют с 1 мая.',
         'url': 'https://ozon.ru/info'}
r3 = evaluate_item_relevance(item3)
test_cases.append(('Strong relevance', r3['passed'] == True, f"passed={r3['passed']}, score={r3['score']}"))

# Test 4: Blacklist domain
item4 = {'title': 'Article', 'description': 'Desc', 'raw_text': 'Text', 'url': 'https://vc.ru/news'}
r4 = evaluate_item_relevance(item4)
test_cases.append(('Blacklist', r4['passed'] == False, f"passed={r4['passed']}"))

# Test 5: Stop signal
item5 = {'title': 'Поздравляем победителей',
         'description': 'Рейтинг опубликован',
         'raw_text': 'Поздравляем всех победителей рейтинга! Это большое событие.',
         'url': 'https://awards.ru'}
r5 = evaluate_item_relevance(item5)
test_cases.append(('Stop signal', r5['passed'] == False, f"passed={r5['passed']}"))

# Test 6: No marketplace context
item6 = {'title': 'Погода хорошая',
         'description': 'Солнечно',
         'raw_text': 'Погода отличная сегодня',
         'url': 'https://weather.ru'}
r6 = evaluate_item_relevance(item6)
test_cases.append(('No context', r6['passed'] == False, f"passed={r6['passed']}"))

# Test 7: No impact
item7 = {'title': 'Ozon открыл новый офис',
         'description': 'Офис открыт',
         'raw_text': 'Ozon открыл новый офис в Казани',
         'url': 'https://ozon.ru/office'}
r7 = evaluate_item_relevance(item7)
test_cases.append(('No impact', r7['passed'] == False, f"passed={r7['passed']}"))

with open('test_manual.txt', 'w', encoding='utf-8') as f:
    passed = 0
    failed = 0
    for name, ok, detail in test_cases:
        status = 'PASS' if ok else 'FAIL'
        if ok:
            passed += 1
        else:
            failed += 1
        f.write(f"{status}: {name} - {detail}\n")
    f.write(f"\nTotal: {passed} passed, {failed} failed\n")

print("Done")
