def get_morning_empty_template():
    return "Утренняя сводка\n\nНочь прошла спокойно, важных изменений нет.\nХорошего дня!"

def get_morning_fallback_template(items_text):
    return f"""Утренняя сводка | За ночь произошли изменения:

{items_text}

Хорошего дня!"""

def get_evening_empty_template(date):
    return f"Вечерняя сводка | {date}\n\nДень прошёл спокойно, значимых изменений не произошло.\nДоброй ночи!"

def get_evening_fallback_template(date, items_text, news_count):
    return f"""Вечерняя сводка | {date}

КРИТИЧНО:
{items_text}

Опубликовано: {news_count} новостей
Доброй ночи!"""

def get_evening_no_critical_template(date, news_count):
    return f"""Вечерняя сводка | {date}

День прошёл спокойно, значимых изменений не произошло.

Опубликовано: {news_count} новостей
Доброй ночи!"""