def get_morning_empty_template():
    return "Morning digest: nothing important happened overnight. Have a good day!"

def get_morning_fallback_template(items_text):
    return f"""Morning digest | What changed overnight:

{items_text}

Have a good day!"""

def get_evening_empty_template(date):
    return f"EVENING DIGEST | {date}\n\nDay was quiet, no important changes. Good night!"

def get_evening_fallback_template(date, items_text, news_count):
    return f"""EVENING DIGEST | {date}

CRITICAL:
{items_text}

Total published: {news_count} news
Good night!"""

def get_evening_no_critical_template(date, news_count):
    return f"""EVENING DIGEST | {date}

Day was quiet, no important changes.

Total published: {news_count} news
Good night!"""