def build_full_article(news:dict)->str:
    return f"{news.get('title','')}\n\n{news.get('full_text',news.get('text',''))}\n\nИсточник: {news.get('source_name','unknown')}\nОригинал: {news.get('link','n/a')}"
