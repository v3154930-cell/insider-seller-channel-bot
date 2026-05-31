#!/usr/bin/env python3
import argparse, sqlite3
from datetime import datetime, timedelta

def main():
    p=argparse.ArgumentParser(); p.add_argument('--db',default='news_queue.db'); args=p.parse_args()
    try:
        conn=sqlite3.connect(args.db); conn.row_factory=sqlite3.Row
    except Exception:
        print('SOURCE_COVERAGE_STATUS=BROKEN'); return 1
    rows=conn.execute("select source,max(created_at) last_seen,count(*) c from news group by source").fetchall()
    tg=[r for r in rows if str(r['source']).startswith('TG:')]
    rss=[r for r in rows if any(x in str(r['source']).lower() for x in ['rbc','retail','oborot','cnews','vc.ru','data insight'])]
    def off(k):
        m=[r for r in rows if k in str(r['source']).lower()]
        return m[0]['last_seen'] if m else ''
    wb,oz,y=off('wb'),off('ozon'),off('yandex')
    status='OK'
    if not y: status='WARN'
    print(f"SOURCE_COVERAGE_STATUS={status}")
    print(f"telegram_sources_count={len(tg)}\ntelegram_sources_recent={len(tg)}")
    print(f"rss_sources_count={len(rss)}\nrss_sources_recent={len(rss)}")
    print(f"official_wb_status={'OK' if wb else 'WARN'}\nofficial_ozon_status={'OK' if oz else 'WARN'}\nofficial_yandex_status={'OK' if y else 'WARN'}")
    print(f"official_wb_last_seen={wb}\nofficial_ozon_last_seen={oz}\nofficial_yandex_last_seen={y}")
    print(f"missing_sources={'official_yandex' if not y else ''}\nstale_sources=\nrecommended_action=verify_official_sources")

if __name__=='__main__': raise SystemExit(main())
