from db import init_db, _execute

init_db()

_execute("""
CREATE TABLE IF NOT EXISTS rules_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    marketplace TEXT NOT NULL,
    document_name TEXT,
    section TEXT,
    topic TEXT,
    rule_text TEXT NOT NULL,
    effective_date TEXT,
    source_url TEXT,
    content_hash TEXT UNIQUE,
    loaded_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

_execute("CREATE INDEX IF NOT EXISTS idx_rules_documents_marketplace ON rules_documents(marketplace)")
_execute("CREATE INDEX IF NOT EXISTS idx_rules_documents_topic ON rules_documents(topic)")
_execute("CREATE INDEX IF NOT EXISTS idx_rules_documents_effective_date ON rules_documents(effective_date)")

print("rules_documents table ready")
