from db import init_db, _execute

init_db()

_execute("""
CREATE TABLE IF NOT EXISTS rules_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL UNIQUE,
    news_id INTEGER,
    marketplace TEXT,
    check_status TEXT DEFAULT 'needs_auto_check',
    confirmation_level TEXT DEFAULT 'unconfirmed',
    matched_document_id INTEGER,
    matched_document TEXT,
    match_score INTEGER DEFAULT 0,
    effective_date TEXT,
    change_summary TEXT,
    seller_impact TEXT,
    seller_action TEXT,
    can_publish INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

_execute("CREATE INDEX IF NOT EXISTS idx_rules_checks_status ON rules_checks(check_status)")
_execute("CREATE INDEX IF NOT EXISTS idx_rules_checks_marketplace ON rules_checks(marketplace)")
_execute("CREATE INDEX IF NOT EXISTS idx_rules_checks_publish ON rules_checks(can_publish)")
_execute("CREATE INDEX IF NOT EXISTS idx_rules_checks_confirmation ON rules_checks(confirmation_level)")

print("rules_checks table ready")
