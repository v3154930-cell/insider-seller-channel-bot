from db import init_db, _execute

init_db()

_execute("""
CREATE TABLE IF NOT EXISTS rules_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    news_id INTEGER NOT NULL UNIQUE,
    marketplace TEXT,
    signal_type TEXT,
    confidence INTEGER DEFAULT 0,
    title TEXT NOT NULL,
    source TEXT,
    link TEXT,
    reason TEXT,
    status TEXT DEFAULT 'new',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

_execute("CREATE INDEX IF NOT EXISTS idx_rules_signals_status ON rules_signals(status)")
_execute("CREATE INDEX IF NOT EXISTS idx_rules_signals_marketplace ON rules_signals(marketplace)")
_execute("CREATE INDEX IF NOT EXISTS idx_rules_signals_created_at ON rules_signals(created_at)")

print("rules_signals table ready")
