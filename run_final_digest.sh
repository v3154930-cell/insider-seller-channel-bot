#!/bin/bash
cd /opt/newsbot || exit 1
set -a
source /opt/newsbot/.env
set +a

# Собираем вечерний дайджест с комиссиями WB
/opt/newsbot/venv/bin/python -c "
from digest_builder import build_evening_digest
from wb_commission_diff import get_day_changes, format_changes
from channel_bot import send_message

# Получаем новостную часть
digest = build_evening_digest()

# Добавляем блок комиссий WB (изменения за день)
changes = get_day_changes()
wb_block = format_changes(changes, 'день')
if wb_block:
    digest += wb_block

# Отправляем
send_message(digest)
print('Evening digest with WB commissions sent')
" >> /opt/newsbot/logs/publisher.log 2>&1
