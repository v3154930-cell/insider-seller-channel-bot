#!/usr/bin/env bash
set -u

cd /opt/newsbot_v2 || exit 1

# Загружаем .env, чтобы MAX_BOT_TOKEN и прочие переменные были доступны
if [ -f /opt/newsbot_v2/.env ]; then
  set -a
  source /opt/newsbot_v2/.env
  set +a
fi

# Сначала страхуем маршрутизацию ignore -> publish
/opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/safety_promote_ignored_to_publish_v1.py >> /opt/newsbot_v2/logs/safety_promote.log 2>&1 || true

# Потом обычный publisher
exec /opt/newsbot_v2/venv/bin/python /opt/newsbot_v2/publisher_v2.py
