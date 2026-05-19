#!/usr/bin/env python3
import os
import sys

# Добавляем текущую директорию в путь, чтобы импортировать publisher
sys.path.insert(0, '/opt/newsbot_v2')

try:
    from publisher import send_message
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    sys.exit(1)

# Получаем токен и ID канала
token = os.getenv('MAX_BOT_TOKEN')
channel_id = os.getenv('CHANNEL_ID')

if not token:
    print("Ошибка: переменная MAX_BOT_TOKEN не найдена")
    sys.exit(1)

if not channel_id:
    print("Ошибка: переменная CHANNEL_ID не найдена")
    sys.exit(1)

print(f"Токен найден: {token[:10]}... (первые 10 символов)")
print(f"ID канала: {channel_id}")

# Отправляем сообщение
result = send_message(
    token=token,
    channel_id=channel_id,
    text='📢 **Новостей нет, все на паузе**\n\n🇷🇺 Друзья-селлеры, сегодня праздник!\n\n🔥 Отдыхайте, жарьте шашлык и делитесь им с ближними.\n\n🟢 Мы вернёмся с новостями, комиссиями и дайджестами завтра.\n\n🌿 Хороших выходных и зелёных продаж!\n\n#ИнсайдерСеллер #Майские #Шашлык',
    add_full_article_button=False
)

print(f"\n--- РЕЗУЛЬТАТ ---")
print(result)
print("-----------------")

if result and result.startswith('mid.'):
    print("✅ СООБЩЕНИЕ УСПЕШНО ОТПРАВЛЕНО В КАНАЛ!")
else:
    print("❌ Ошибка при отправке. Результат не является mid.")
