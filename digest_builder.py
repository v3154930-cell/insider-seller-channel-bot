#!/usr/bin/env python3
"""
Сборщик дайджестов для publisher.py --mode=morning_digest и final_digest
"""
import sqlite3
import os
import sys
from datetime import datetime, timedelta

DB_PATH = '/opt/newsbot/news.db'

def get_news(hours_back=12, limit=15):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cutoff = datetime.now() - timedelta(hours=hours_back)
        cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("""
            SELECT title, source, created_at
            FROM items 
            WHERE status = 'published' 
            AND created_at > ?
            ORDER BY created_at DESC
            LIMIT ?
        """, (cutoff_str, limit))
        
        news = cursor.fetchall()
        conn.close()
        return news
    except Exception as e:
        print(f"DB error: {e}")
        return []

def build_morning_digest():
    news = get_news(12, 15)
    digest = f"🌅 **УТРЕННИЙ ДАЙДЖЕСТ**\n📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
    digest += "**📰 Главное за ночь:**\n\n"
    if news:
        for title, source, _ in news:
            digest += f"• **[{source}]** {title}\n"
    else:
        digest += "✨ За ночь новых важных новостей нет\n"
    digest += f"\n---\n📊 Всего постов за ночь: {len(news)}"
    return digest

def build_final_digest():
    news = get_news(24, 20)
    digest = f"🌙 **ВЕЧЕРНИЙ ДАЙДЖЕСТ**\n📅 {datetime.now().strftime('%d.%m.%Y')}\n\n"
    digest += "**📰 Главное за день:**\n\n"
    if news:
        for title, source, _ in news:
            digest += f"• **[{source}]** {title}\n"
    else:
        digest += "✨ За день новых важных новостей нет\n"
    digest += f"\n---\n📊 Всего постов за день: {len(news)}"
    return digest

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "morning"
    if mode == "morning" or mode == "morning_digest":
        print(build_morning_digest())
    elif mode == "final" or mode == "final_digest":
        print(build_final_digest())
    else:
        print("Использование: python digest_builder.py [morning|final]")
