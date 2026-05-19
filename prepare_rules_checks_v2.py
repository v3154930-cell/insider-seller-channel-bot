from db import init_db, _fetch_all, _execute

def main():
    init_db()

    rows = _fetch_all("""
        SELECT id, news_id, marketplace
        FROM rules_signals
        WHERE is_digest_candidate = 1
        ORDER BY id DESC
    """)

    inserted = 0

    for r in rows:
        signal_id = r[0]
        news_id = r[1]
        marketplace = r[2]

        _execute("""
            INSERT OR IGNORE INTO rules_checks
            (signal_id, news_id, marketplace)
            VALUES (?, ?, ?)
        """, (signal_id, news_id, marketplace))

        inserted += 1

    print("prepared rules checks:", inserted)

    print("\n=== CHECKS NEED REVIEW ===")
    rows = _fetch_all("""
        SELECT rc.id, rc.signal_id, rc.news_id, rc.marketplace, rc.check_status, rc.confirmation_level, rs.title, rs.source
        FROM rules_checks rc
        JOIN rules_signals rs ON rs.id = rc.signal_id
        WHERE rc.check_status = 'needs_review'
        ORDER BY rc.id DESC
        LIMIT 20
    """)

    for r in rows:
        print(r)

if __name__ == "__main__":
    main()
