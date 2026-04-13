#!/usr/bin/env python3
"""Preview tool for digest templates - prints to console without publishing to MAX."""

from message_templates import (
    get_morning_empty_template,
    get_morning_fallback_template,
    get_evening_empty_template,
    get_evening_fallback_template,
    get_evening_no_critical_template,
)

def main():
    print("=" * 60)
    print("PREVIEW ШАБЛОНОВ ДАЙДЖЕСТОВ")
    print("=" * 60)
    
    print("\n--- УТРЕННЯЯ СВОДКА: Пустая (нет новостей) ---")
    print(get_morning_empty_template())
    
    print("\n--- УТРЕННЯЯ СВОДКА: С примерами новостей ---")
    sample_items = "• Ozon повысил комиссию на электронику на 3%\n• Wildberries запустил новый логистический хаб в Казани"
    print(get_morning_fallback_template(sample_items))
    
    print("\n--- ВЕЧЕРНЯЯ СВОДКА: Пустая (нет новостей) ---")
    print(get_evening_empty_template("13.04.2026"))
    
    print("\n--- ВЕЧЕРНЯЯ СВОДКА: С критичными новостями ---")
    sample_critical = "[*] Суд оштрафовал селлера на 500 тыс. руб. за нарушение товарного знака\n[*] Ozon заблокировал 200 аккаунтов за нарушение документов"
    print(get_evening_fallback_template("13.04.2026", sample_critical, 15))
    
    print("\n--- ВЕЧЕРНЯЯ СВОДКА: Без критичных (обычный день) ---")
    print(get_evening_no_critical_template("13.04.2026", 8))
    
    print("\n" + "=" * 60)
    print("Preview завершён — данные не отправлены, MAX API не вызван")
    print("=" * 60)

if __name__ == "__main__":
    main()