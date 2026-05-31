# Admin migration

- v2 service: `newsbot-admin.service`
- v2 command: `/opt/newsbot_v2/venv/bin/python -m uvicorn admin_app:app --host 0.0.0.0 --port 8088`
- v3 requirement: admin actions auditable in `admin_actions`, read-only mode required.
