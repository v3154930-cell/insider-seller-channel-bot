#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "/opt/newsbot/data/wb_commissions.db"

def get_night_changes():
    """Возвращает изменения комиссий за ночь (между последними двумя сборами)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Получаем две последние даты сбора
    cursor.execute("""
        SELECT DISTINCT DATE(collected_at) as date
        FROM commissions
        ORDER BY date DESC
        LIMIT 2
    """)
    dates = [row[0] for row in cursor.fetchall()]
    
    if len(dates) < 2:
        conn.close()
        return []
    
    today, yesterday = dates[0], dates[1]
    
    # Комиссии за сегодня
    cursor.execute("""
        SELECT category, commission
        FROM commissions
        WHERE DATE(collected_at) = ?
    """, (today,))
    today_data = {row[0]: row[1] for row in cursor.fetchall()}
    
    # Комиссии за вчера
    cursor.execute("""
        SELECT category, commission
        FROM commissions
        WHERE DATE(collected_at) = ?
    """, (yesterday,))
    yesterday_data = {row[0]: row[1] for row in cursor.fetchall()}
    
    conn.close()
    
    changes = []
    for category, rate in today_data.items():
        old_rate = yesterday_data.get(category)
        if old_rate and abs(rate - old_rate) > 0.1:
            changes.append({
                'category': category,
                'old': old_rate,
                'new': rate,
                'diff': round(rate - old_rate, 1)
            })
    
    changes.sort(key=lambda x: abs(x['diff']), reverse=True)
    return changes

def format_changes(changes, period="ночь"):
    """Форматирует изменения для вставки в дайджест"""
    if not changes:
        return ""
    
    up = [c for c in changes if c['diff'] > 0][:5]
    down = [c for c in changes if c['diff'] < 0][:5]
    
    result = f"\n📊 **ИЗМЕНЕНИЯ КОМИССИЙ WILDBERRIES ЗА {period.upper()}:**\n\n"
    
    if up:
        result += "🔺 **Повысились:**\n"
        for c in up:
            result += f"  • {c['category'][:35]}: {c['old']}% → {c['new']}% (+{c['diff']}%)\n"
        result += "\n"
    
    if down:
        result += "🔻 **Понизились:**\n"
        for c in down:
            result += f"  • {c['category'][:35]}: {c['old']}% → {c['new']}% ({c['diff']}%)\n"
        result += "\n"
    
    if len(changes) > 10:
        result += f"_и ещё {len(changes) - 10} изменений_\n"
    
    return result

if __name__ == "__main__":
    changes = get_night_changes()
    print(format_changes(changes, "ночь"))

def get_day_changes():
    """Возвращает изменения комиссий за день (между утренним и вечерним сбором)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Получаем два последних сбора за сегодня
    cursor.execute("""
        SELECT collected_at, category, commission
        FROM commissions
        WHERE DATE(collected_at) = DATE('now')
        ORDER BY collected_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if len(rows) < 2:
        return []
    
    # Группируем по времени сбора
    morning_data = {}
    evening_data = {}
    
    first_time = rows[0][0]  # последний сбор (вечер)
    for row in rows:
        if row[0] == first_time:
            evening_data[row[1]] = row[2]
        else:
            morning_data[row[1]] = row[2]
    
    changes = []
    for category, rate in evening_data.items():
        old_rate = morning_data.get(category)
        if old_rate and abs(rate - old_rate) > 0.1:
            changes.append({
                'category': category,
                'old': old_rate,
                'new': rate,
                'diff': round(rate - old_rate, 1)
            })
    
    changes.sort(key=lambda x: abs(x['diff']), reverse=True)
    return changes
